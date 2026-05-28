from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Callable, Protocol

from app.domain.activity_taxonomy import ACTIVITY_TAXONOMY
from app.domain.factor_intents import FactorIntent
from app.domain.material_ontology import (
    material_is_broader_match,
    material_matches,
    method_matches,
)
from app.domain.models import CarbonEvent, FactorCandidate
from app.pipeline_v2.retrieval_diagnostics import build_factor_diagnostics
from app.pipeline_v2.validator import (
    MIN_ACCEPTED_FACTOR_SCORE,
    FactorCompatibilityValidator,
)
from app.services.climatiq_api import get_activity_metadata_records, search_activity_ids


MIN_ACCEPTED_SCORE = MIN_ACCEPTED_FACTOR_SCORE
NORMAL_ACCEPTED_SCORE = 0.75


class FactorRetriever(Protocol):
    def retrieve(
        self,
        event: CarbonEvent,
        parameters: dict,
        limit: int = 5,
        intent: FactorIntent | None = None,
    ) -> list[FactorCandidate]:
        """Return compatible Climatiq activity IDs ordered by match quality."""


@dataclass(frozen=True)
class RetrievalResult:
    candidates: list[FactorCandidate]
    diagnostics: dict


class ClimatiqFactorRetriever:
    """Ranks compatible Climatiq factors using taxonomy-declared event evidence."""

    def __init__(
        self,
        local_records_provider: Callable[[], list[dict]] | None = None,
        remote_search: Callable[..., list[dict]] | None = None,
        semantic_scorer: Callable[[CarbonEvent, dict, dict], float] | None = None,
        validator: FactorCompatibilityValidator | None = None,
    ) -> None:
        self.local_records_provider = local_records_provider or get_activity_metadata_records
        self.remote_search = remote_search or search_activity_ids
        self.semantic_scorer = semantic_scorer
        self.validator = validator or FactorCompatibilityValidator()

    def retrieve(
        self,
        event: CarbonEvent,
        parameters: dict,
        limit: int = 5,
        intent: FactorIntent | None = None,
    ) -> list[FactorCandidate]:
        return self.retrieve_with_diagnostics(event, parameters, limit, intent).candidates

    def retrieve_with_diagnostics(
        self,
        event: CarbonEvent,
        parameters: dict,
        limit: int = 5,
        intent: FactorIntent | None = None,
    ) -> RetrievalResult:
        local_rejections: list[dict] = []
        local_records = self.local_records_provider()
        local_candidates = _rank_records(
            event,
            parameters,
            local_records,
            intent=intent,
            semantic_scorer=self.semantic_scorer,
            validator=self.validator,
            rejections=local_rejections,
        )
        identity_evidence = _identity_evidence(event, parameters)

        if not _local_retrieval_is_weak(local_candidates, bool(identity_evidence)):
            selected = local_candidates[:limit]
            return RetrievalResult(
                candidates=selected,
                diagnostics=build_factor_diagnostics(
                    intent=intent,
                    search_query=_factor_query(event, parameters, intent),
                    selector_filters=_selector_filters(event, intent),
                    candidate_count=len(local_records),
                    selected=selected[0] if selected else None,
                    rejections=local_rejections,
                ),
            )

        remote_rejections: list[dict] = []
        remote_records = self._remote_records(event, parameters, limit, intent)
        remote_candidates = _rank_records(
            event,
            parameters,
            remote_records,
            intent=intent,
            semantic_scorer=self.semantic_scorer,
            validator=self.validator,
            rejections=remote_rejections,
        )
        merged = _merge_candidates(local_candidates, remote_candidates)[:limit]
        return RetrievalResult(
            candidates=merged,
            diagnostics=build_factor_diagnostics(
                intent=intent,
                search_query=_factor_query(event, parameters, intent),
                selector_filters=_selector_filters(event, intent),
                candidate_count=len(local_records) + len(remote_records),
                selected=merged[0] if merged else None,
                rejections=[*local_rejections, *remote_rejections],
            ),
        )

    def _remote_records(
        self,
        event: CarbonEvent,
        parameters: dict,
        limit: int,
        intent: FactorIntent | None = None,
    ) -> list[dict]:
        metadata = ACTIVITY_TAXONOMY[event.activity_type]
        records: list[dict] = []
        unit_types = (intent.unit_type,) if intent is not None else metadata.get("compatible_unit_types", ())
        for unit_type in unit_types:
            records.extend(
                self._remote_candidates(
                    _factor_query(event, parameters, intent),
                    limit,
                    str(unit_type),
                    _expected_sector(event, intent),
                )
            )
        return records

    def _remote_candidates(
        self,
        query: str,
        limit: int,
        unit_type: str,
        sector: str,
    ) -> list[dict]:
        try:
            return self.remote_search(
                query,
                limit,
                unit_type=unit_type,
                sector=sector,
            )
        except TypeError:
            # Keeps simple injected search doubles usable in offline tests.
            return self.remote_search(query, limit)


def _rank_records(
    event: CarbonEvent,
    parameters: dict,
    records: list[dict],
    *,
    intent: FactorIntent | None = None,
    semantic_scorer: Callable[[CarbonEvent, dict, dict], float] | None = None,
    validator: FactorCompatibilityValidator | None = None,
    rejections: list[dict] | None = None,
) -> list[FactorCandidate]:
    metadata = ACTIVITY_TAXONOMY[event.activity_type]
    match_terms = _match_terms(metadata, intent)
    required_terms = tuple(
        str(term).lower() for term in metadata.get("factor_required_terms", ())
    )
    preferred_terms = _preferred_terms(event, metadata, parameters, intent)
    excluded_terms = _excluded_terms(metadata, intent)
    identity_evidence = _identity_evidence(event, parameters)
    validator = validator or FactorCompatibilityValidator()
    candidates: list[FactorCandidate] = []

    for record in records:
        activity_id = str(record.get("activity_id") or "").strip()
        text = _record_text(record)
        validation = validator.validate_record(event, parameters, record, intent=intent)
        if not activity_id or not validation.compatible:
            _record_rejection(
                rejections,
                record,
                validation.errors[0] if validation.errors else "factor metadata is incompatible",
            )
            continue
        if required_terms and not any(
            _contains_phrase(text, term) for term in required_terms
        ):
            _record_rejection(
                rejections,
                record,
                "required taxonomy terms were not present in factor metadata",
            )
            continue
        if any(_contains_phrase(text, term) for term in excluded_terms):
            _record_rejection(
                rejections,
                record,
                "factor metadata contained terms excluded by the resolved intent",
            )
            continue
        if _has_authoritative_trait_conflict(event, metadata, parameters, text):
            _record_rejection(
                rejections,
                record,
                "factor metadata conflicts with explicit user or verified trait evidence",
            )
            continue

        specificity_match = _matches_identity_evidence(identity_evidence, text)
        metadata_score, metadata_reasons = _metadata_score(event, record, validation.match_reasons)
        semantic_score, semantic_reasons = _semantic_score(
            event,
            parameters,
            record,
            text,
            semantic_scorer,
            intent,
        )
        if identity_evidence and not specificity_match:
            semantic_score *= 0.60
            semantic_reasons.append(
                "supplied identity was not present in factor metadata; "
                "reduced specificity relevance"
            )
        keyword_score, keyword_reasons = _keyword_score(
            metadata,
            parameters,
            text,
            match_terms,
            preferred_terms,
            identity_evidence,
            specificity_match,
            intent,
        )
        source_quality_score, source_reasons = _source_quality_score(record)
        score = round(
            metadata_score * 0.35
            + semantic_score * 0.35
            + keyword_score * 0.20
            + source_quality_score * 0.10,
            2,
        )
        if score < MIN_ACCEPTED_SCORE:
            _record_rejection(
                rejections,
                record,
                f"factor fit score {score:.2f} was below the {MIN_ACCEPTED_SCORE:.2f} threshold",
            )
            continue
        reasons = [
            *metadata_reasons,
            *semantic_reasons,
            *keyword_reasons,
            *source_reasons,
        ]
        candidates.append(
            FactorCandidate(
                activity_id=activity_id,
                name=str(record.get("name") or activity_id),
                sector=str(record.get("sector") or "") or None,
                category=str(record.get("category") or "") or None,
                unit_type=validation.unit_type or "",
                score=score,
                match_reasons=reasons,
                specificity_match=specificity_match,
                metadata_text=text,
            )
        )

    return sorted(candidates, key=lambda candidate: (-candidate.score, candidate.activity_id))


def _local_retrieval_is_weak(
    candidates: list[FactorCandidate],
    identity_requested: bool,
) -> bool:
    if not candidates or candidates[0].score < NORMAL_ACCEPTED_SCORE:
        return True
    return identity_requested and not any(candidate.specificity_match for candidate in candidates)


def _metadata_score(
    event: CarbonEvent,
    record: dict,
    validation_reasons: tuple[str, ...],
) -> tuple[float, list[str]]:
    score = 0.60
    sector = _normalized_text(record.get("sector"))
    category = _normalized_text(record.get("category"))
    if sector:
        score += 0.30
    if category and _category_mentions_event(category, event.category):
        score += 0.10
    reasons = [*validation_reasons, f"metadata compatibility score: {min(score, 1.0):.2f}"]
    return min(score, 1.0), reasons


def _semantic_score(
    event: CarbonEvent,
    parameters: dict,
    record: dict,
    text: str,
    semantic_scorer: Callable[[CarbonEvent, dict, dict], float] | None,
    intent: FactorIntent | None = None,
) -> tuple[float, list[str]]:
    if semantic_scorer is not None:
        score = _bounded_score(semantic_scorer(event, parameters, record))
        return score, [f"semantic provider score: {score:.2f}"]
    for key in ("semantic_score", "vector_score", "similarity"):
        if key in record:
            score = _bounded_score(record[key])
            return score, [f"record {key} score: {score:.2f}"]

    query_tokens = set(_meaningful_tokens(_factor_query(event, parameters, intent)))
    record_tokens = set(_meaningful_tokens(text))
    matches = sorted(query_tokens.intersection(record_tokens))
    score = len(matches) / len(query_tokens) if query_tokens else 0.0
    reasons = []
    if matches:
        reasons.append(
            "structured query terms matched for semantic proxy: " + ", ".join(matches)
        )
    return score, reasons


def _keyword_score(
    metadata: dict,
    parameters: dict,
    text: str,
    match_terms: tuple[str, ...],
    preferred_terms: tuple[str, ...],
    identity_evidence: list[tuple[str, str]],
    specificity_match: bool,
    intent: FactorIntent | None = None,
) -> tuple[float, list[str]]:
    reasons: list[str] = []
    score = 0.0
    matched_terms = [term for term in match_terms if _contains_phrase(text, term)]
    if match_terms:
        score += 0.45 * len(matched_terms) / len(match_terms)
    if matched_terms:
        reasons.append("activity metadata terms matched: " + ", ".join(matched_terms))

    preferred_matches = [term for term in preferred_terms if _contains_phrase(text, term)]
    if preferred_terms:
        score += 0.20 * len(preferred_matches) / len(preferred_terms)
    if preferred_matches:
        reasons.append("preferred metadata terms matched: " + ", ".join(preferred_matches))

    trait_score, trait_reasons = _trait_evidence_score(metadata, parameters, text)
    score += trait_score
    reasons.extend(trait_reasons)
    intent_score, intent_reasons = _intent_evidence_score(intent, text)
    score += intent_score
    reasons.extend(intent_reasons)
    if specificity_match:
        score += 0.40
        values = ", ".join(value for _, value in identity_evidence)
        reasons.append(f"specific supplied description matched factor metadata: {values}")
    return min(score, 1.0), reasons


def _source_quality_score(record: dict) -> tuple[float, list[str]]:
    for key in ("source_quality_score", "data_quality_score"):
        if key in record:
            score = _bounded_score(record[key])
            source = "enriched factor metadata" if record.get("source_note") else "factor metadata"
            return score, [f"{key} from {source}: {score:.2f}"]
    return 0.50, ["source quality unavailable; applied neutral score: 0.50"]


def _identity_evidence(event: CarbonEvent, parameters: dict) -> list[tuple[str, str]]:
    metadata = ACTIVITY_TAXONOMY[event.activity_type]
    evidence = []
    for field in metadata.get("factor_identity_fields", ()):
        value = _normalized_text(parameters.get(str(field)))
        if value:
            evidence.append((str(field), value))
    return evidence


def _matches_identity_evidence(evidence: list[tuple[str, str]], text: str) -> bool:
    if not evidence:
        return False
    return any(
        bool(_meaningful_tokens(value))
        and all(token in text.split() for token in _meaningful_tokens(value))
        for _, value in evidence
    )


def _meaningful_tokens(value: str) -> list[str]:
    return [
        token
        for token in value.split()
        if token not in {"the", "a", "an", "vehicle", "car", "item"}
    ]


def _trait_evidence_score(metadata: dict, parameters: dict, text: str) -> tuple[float, list[str]]:
    score = 0.0
    reasons: list[str] = []
    aliases_by_field = metadata.get("factor_value_aliases", {})
    conflicts_by_field = metadata.get("factor_value_conflicts", {})
    fields_with_values = [
        field
        for field in metadata.get("factor_trait_fields", ())
        if _normalized_text(parameters.get(str(field)))
    ]
    for field in fields_with_values:
        value = _normalized_text(parameters.get(str(field)))
        aliases = tuple(aliases_by_field.get(field, {}).get(value, (value,)))
        if not any(_contains_phrase(text, str(alias)) for alias in aliases):
            continue
        score += 0.25 / len(fields_with_values)
        reasons.append(f"normalized {field} matched: {value}")
        conflicts = tuple(conflicts_by_field.get(field, {}).get(value, ()))
        if any(_contains_phrase(text, str(conflict)) for conflict in conflicts):
            score -= 0.05
            reasons.append(f"broader {field} variant matched less precisely: {value}")
    return max(score, 0.0), reasons


def _has_authoritative_trait_conflict(
    event: CarbonEvent,
    metadata: dict,
    parameters: dict,
    text: str,
) -> bool:
    aliases_by_field = metadata.get("factor_value_aliases", {})
    required_fields = set(metadata.get("factor_required_authoritative_traits", ()))
    for field in metadata.get("factor_trait_fields", ()):
        source = event.entities.get(f"{field}_source")
        if source not in {"user", "vehicle_metadata"}:
            continue
        requested_value = _normalized_text(parameters.get(str(field)))
        if not requested_value:
            continue
        field_aliases = aliases_by_field.get(field, {})
        requested_aliases = field_aliases.get(requested_value, (requested_value,))
        if field in required_fields and not any(
            _contains_phrase(text, str(alias)) for alias in requested_aliases
        ):
            return True
        declared_values = {
            value
            for value, aliases in field_aliases.items()
            if any(_contains_phrase(text, str(alias)) for alias in aliases)
        }
        if declared_values and requested_value not in declared_values:
            return True
    return False


def _merge_candidates(*candidate_lists: list[FactorCandidate]) -> list[FactorCandidate]:
    by_activity_id: dict[str, FactorCandidate] = {}
    for candidate in (candidate for candidates in candidate_lists for candidate in candidates):
        existing = by_activity_id.get(candidate.activity_id)
        if existing is None or candidate.score > existing.score:
            by_activity_id[candidate.activity_id] = candidate
    return sorted(
        by_activity_id.values(),
        key=lambda candidate: (-candidate.score, candidate.activity_id),
    )


def _record_text(record: dict) -> str:
    values = list(_record_scalar_values(record))
    text = " ".join(str(value or "") for value in values).lower()
    return _normalized_text(text)


def _normalized_text(value: object) -> str:
    text = re.sub(r"[^a-z0-9]+", " ", str(value or "").lower())
    return re.sub(r"\s+", " ", text).strip()


def _expected_sector(event: CarbonEvent, intent: FactorIntent | None = None) -> str:
    if intent is not None and intent.selector_filters.get("sector"):
        return intent.selector_filters["sector"]
    return {
        "energy": "Energy",
        "transport": "Transport",
        "goods_services": "Goods",
        "waste": "Waste",
    }[event.category]


def _selector_filters(event: CarbonEvent, intent: FactorIntent | None = None) -> dict:
    if intent is not None:
        return dict(intent.selector_filters)
    return {
        "unit_type": "",
        "sector": _expected_sector(event),
    }


def _factor_query(
    event: CarbonEvent,
    parameters: dict,
    intent: FactorIntent | None = None,
) -> str:
    if intent is not None:
        return intent.search_query
    metadata = ACTIVITY_TAXONOMY[event.activity_type]
    values = [
        str(parameters[field])
        for field in (
            *metadata.get("factor_identity_fields", ()),
            *metadata.get("factor_trait_fields", ()),
        )
        if parameters.get(field)
    ]
    query_terms = [
        str(metadata.get("climatiq_factor_query", event.activity_type)),
        *metadata.get("factor_match_terms", ()),
        *_preferred_terms(event, metadata, parameters, intent),
        *values,
    ]
    return " ".join(dict.fromkeys(term.strip() for term in query_terms if term.strip()))


def _category_mentions_event(category: str, event_category: str) -> bool:
    markers = {
        "energy": ("energy", "electricity", "power"),
        "transport": ("transport", "vehicle", "travel", "passenger"),
        "goods_services": ("goods", "services", "purchase", "food"),
        "waste": ("waste", "recycling", "landfill", "compost"),
    }
    return any(marker in category for marker in markers.get(event_category, (event_category,)))


def _bounded_score(value: object) -> float:
    try:
        return min(max(float(value), 0.0), 1.0)
    except (TypeError, ValueError):
        return 0.0


def _preferred_terms(
    event: CarbonEvent,
    metadata: dict,
    parameters: dict,
    intent: FactorIntent | None = None,
) -> tuple[str, ...]:
    if intent is not None:
        return tuple(str(term).lower() for term in intent.preferred_terms)
    terms = tuple(str(term).lower() for term in metadata.get("factor_preferred_terms", ()))
    authoritative_fields = {
        str(field)
        for field in metadata.get("factor_required_authoritative_traits", ())
        if parameters.get(str(field))
        and event.entities.get(f"{field}_source") in {"user", "vehicle_metadata"}
    }
    if not authoritative_fields:
        return terms
    if "fuel_type" not in authoritative_fields:
        return terms
    return tuple(term for term in terms if term not in {"average", "fuel source na"})


def _contains_phrase(text: str, phrase: str) -> bool:
    normalized_phrase = _normalized_text(phrase)
    if not normalized_phrase:
        return False
    return f" {normalized_phrase} " in f" {text} "


def _match_terms(metadata: dict, intent: FactorIntent | None) -> tuple[str, ...]:
    terms = [str(term).lower() for term in metadata.get("factor_match_terms", ())]
    if intent is not None:
        terms.extend(str(term).lower() for term in intent.preferred_terms)
        terms.extend(str(value).replace("_", " ").lower() for value in intent.semantic_dimensions.values())
    return tuple(dict.fromkeys(term for term in terms if term))


def _excluded_terms(metadata: dict, intent: FactorIntent | None) -> tuple[str, ...]:
    terms = [str(term).lower() for term in metadata.get("factor_excluded_terms", ())]
    if intent is not None:
        terms.extend(str(term).lower() for term in intent.excluded_terms)
    return tuple(dict.fromkeys(term for term in terms if term))


def _intent_evidence_score(
    intent: FactorIntent | None,
    text: str,
) -> tuple[float, list[str]]:
    if intent is None:
        return 0.0, []
    score = 0.0
    reasons: list[str] = []
    method = intent.semantic_dimensions.get("disposal_method")
    if method and method_matches(method, text):
        score += 0.18
        reasons.append(f"intent disposal method matched: {method}")
    material = intent.semantic_dimensions.get("material_class")
    if material and material_matches(material, text):
        score += 0.18
        reasons.append(f"intent material matched: {material}")
    elif material and material_is_broader_match(material, text):
        score += 0.10
        reasons.append(f"broader material factor matched intent: {material}")
    product = intent.semantic_dimensions.get("product_class")
    if product and _contains_phrase(text, product.replace("_", " ")):
        score += 0.25
        reasons.append(f"intent product class matched: {product}")
    if intent.unit_type and _contains_phrase(text, intent.unit_type):
        score += 0.06
        reasons.append(f"intent unit type matched in metadata text: {intent.unit_type}")
    return min(score, 0.45), reasons


def _record_rejection(rejections: list[dict] | None, record: dict, reason: str) -> None:
    if rejections is None:
        return
    rejections.append(
        {
            "activity_id": str(record.get("activity_id") or ""),
            "name": str(record.get("name") or record.get("activity_id") or ""),
            "reason": reason,
        }
    )


def _record_scalar_values(record: dict):
    for key, value in record.items():
        if key in {
            "excluded_terms",
            "source_urls",
            "calculation_boundary",
            "source_note",
        }:
            continue
        yield from _flatten_record_value(value)


def _flatten_record_value(value):
    if isinstance(value, (str, int, float)):
        yield value
    elif isinstance(value, (list, tuple, set)):
        for item in value:
            yield from _flatten_record_value(item)
    elif isinstance(value, dict):
        for item_key, item in value.items():
            if item_key in {
                "excluded_terms",
                "source_urls",
                "calculation_boundary",
                "source_note",
            }:
                continue
            yield from _flatten_record_value(item)
