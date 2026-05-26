from __future__ import annotations

import re
from typing import Callable, Protocol

from app.domain.activity_taxonomy import ACTIVITY_TAXONOMY
from app.domain.models import CarbonEvent, FactorCandidate
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
    ) -> list[FactorCandidate]:
        """Return compatible Climatiq activity IDs ordered by match quality."""


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
    ) -> list[FactorCandidate]:
        local_candidates = _rank_records(
            event,
            parameters,
            self.local_records_provider(),
            semantic_scorer=self.semantic_scorer,
            validator=self.validator,
        )
        identity_evidence = _identity_evidence(event, parameters)

        if not _local_retrieval_is_weak(local_candidates, bool(identity_evidence)):
            return local_candidates[:limit]

        remote_candidates = _rank_records(
            event,
            parameters,
            self._remote_records(event, parameters, limit),
            semantic_scorer=self.semantic_scorer,
            validator=self.validator,
        )
        return _merge_candidates(local_candidates, remote_candidates)[:limit]

    def _remote_records(
        self,
        event: CarbonEvent,
        parameters: dict,
        limit: int,
    ) -> list[dict]:
        metadata = ACTIVITY_TAXONOMY[event.activity_type]
        records: list[dict] = []
        for unit_type in metadata.get("compatible_unit_types", ()):
            records.extend(
                self._remote_candidates(
                    _factor_query(event, parameters),
                    limit,
                    str(unit_type),
                    _expected_sector(event),
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
    semantic_scorer: Callable[[CarbonEvent, dict, dict], float] | None = None,
    validator: FactorCompatibilityValidator | None = None,
) -> list[FactorCandidate]:
    metadata = ACTIVITY_TAXONOMY[event.activity_type]
    match_terms = tuple(str(term).lower() for term in metadata.get("factor_match_terms", ()))
    required_terms = tuple(
        str(term).lower() for term in metadata.get("factor_required_terms", ())
    )
    preferred_terms = _preferred_terms(event, metadata, parameters)
    excluded_terms = tuple(
        str(term).lower() for term in metadata.get("factor_excluded_terms", ())
    )
    identity_evidence = _identity_evidence(event, parameters)
    validator = validator or FactorCompatibilityValidator()
    candidates: list[FactorCandidate] = []

    for record in records:
        activity_id = str(record.get("activity_id") or "").strip()
        text = _record_text(record)
        validation = validator.validate_record(event, parameters, record)
        if not activity_id or not validation.compatible:
            continue
        if required_terms and not any(
            _contains_phrase(text, term) for term in required_terms
        ):
            continue
        if any(_contains_phrase(text, term) for term in excluded_terms):
            continue
        if _has_authoritative_trait_conflict(event, metadata, parameters, text):
            continue

        specificity_match = _matches_identity_evidence(identity_evidence, text)
        metadata_score, metadata_reasons = _metadata_score(event, record, validation.match_reasons)
        semantic_score, semantic_reasons = _semantic_score(
            event,
            parameters,
            record,
            text,
            semantic_scorer,
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
) -> tuple[float, list[str]]:
    if semantic_scorer is not None:
        score = _bounded_score(semantic_scorer(event, parameters, record))
        return score, [f"semantic provider score: {score:.2f}"]
    for key in ("semantic_score", "vector_score", "similarity"):
        if key in record:
            score = _bounded_score(record[key])
            return score, [f"record {key} score: {score:.2f}"]

    query_tokens = set(_meaningful_tokens(_factor_query(event, parameters)))
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
    if specificity_match:
        score += 0.40
        values = ", ".join(value for _, value in identity_evidence)
        reasons.append(f"specific supplied description matched factor metadata: {values}")
    return min(score, 1.0), reasons


def _source_quality_score(record: dict) -> tuple[float, list[str]]:
    for key in ("source_quality_score", "data_quality_score"):
        if key in record:
            score = _bounded_score(record[key])
            return score, [f"{key} from factor metadata: {score:.2f}"]
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
    values = [
        record.get("activity_id"),
        record.get("name"),
        record.get("category"),
        record.get("sector"),
        record.get("source"),
        record.get("unit_type"),
        record.get("description"),
    ]
    text = " ".join(str(value or "") for value in values).lower()
    return _normalized_text(text)


def _normalized_text(value: object) -> str:
    text = re.sub(r"[^a-z0-9]+", " ", str(value or "").lower())
    return re.sub(r"\s+", " ", text).strip()


def _expected_sector(event: CarbonEvent) -> str:
    return "Energy" if event.category == "energy" else "Transport"


def _factor_query(event: CarbonEvent, parameters: dict) -> str:
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
        *_preferred_terms(event, metadata, parameters),
        *values,
    ]
    return " ".join(dict.fromkeys(term.strip() for term in query_terms if term.strip()))


def _category_mentions_event(category: str, event_category: str) -> bool:
    markers = {
        "energy": ("energy", "electricity", "power"),
        "transport": ("transport", "vehicle", "travel", "passenger"),
    }
    return any(marker in category for marker in markers.get(event_category, (event_category,)))


def _bounded_score(value: object) -> float:
    try:
        return min(max(float(value), 0.0), 1.0)
    except (TypeError, ValueError):
        return 0.0


def _preferred_terms(event: CarbonEvent, metadata: dict, parameters: dict) -> tuple[str, ...]:
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
