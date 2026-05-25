from __future__ import annotations

import re
from typing import Callable, Protocol

from app.domain.activity_taxonomy import ACTIVITY_TAXONOMY
from app.domain.models import CarbonEvent, FactorCandidate
from app.services.climatiq_api import get_activity_metadata_records, search_activity_ids


MIN_ACCEPTED_SCORE = 0.55


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
    ) -> None:
        self.local_records_provider = local_records_provider or get_activity_metadata_records
        self.remote_search = remote_search or search_activity_ids

    def retrieve(
        self,
        event: CarbonEvent,
        parameters: dict,
        limit: int = 5,
    ) -> list[FactorCandidate]:
        local_candidates = _rank_records(event, parameters, self.local_records_provider())
        identity_evidence = _identity_evidence(event, parameters)

        # A preserved identifier (for example a model or named material) warrants
        # checking the current Climatiq catalogue even when generic local factors exist.
        if identity_evidence and not any(
            candidate.specificity_match for candidate in local_candidates
        ):
            remote_candidates = _rank_records(
                event,
                parameters,
                self._remote_records(event, parameters, limit),
            )
            candidates = _merge_candidates(local_candidates, remote_candidates)
            if candidates:
                return candidates[:limit]

        if local_candidates:
            return local_candidates[:limit]

        return _rank_records(
            event,
            parameters,
            self._remote_records(event, parameters, limit),
        )[:limit]

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
) -> list[FactorCandidate]:
    metadata = ACTIVITY_TAXONOMY[event.activity_type]
    compatible_units = {
        str(unit_type).lower() for unit_type in metadata.get("compatible_unit_types", ())
    }
    expected_sector = _expected_sector(event).lower()
    match_terms = tuple(str(term).lower() for term in metadata.get("factor_match_terms", ()))
    preferred_terms = tuple(
        str(term).lower() for term in metadata.get("factor_preferred_terms", ())
    )
    excluded_terms = tuple(
        str(term).lower() for term in metadata.get("factor_excluded_terms", ())
    )
    identity_evidence = _identity_evidence(event, parameters)
    candidates: list[FactorCandidate] = []

    for record in records:
        activity_id = str(record.get("activity_id") or "").strip()
        text = _record_text(record)
        unit_types = _unit_types(record.get("unit_type"))
        sector = str(record.get("sector") or "").strip()
        if (
            not activity_id
            or not compatible_units.intersection(unit_types)
            or (sector and sector.lower() != expected_sector)
            or (match_terms and not any(term in text for term in match_terms))
            or any(term in text for term in excluded_terms)
            or _has_authoritative_trait_conflict(event, metadata, parameters, text)
        ):
            continue

        reasons = [
            f"compatible Climatiq unit type: {sorted(compatible_units.intersection(unit_types))[0]}",
            f"sector matched {expected_sector}",
        ]
        score = 0.56
        matched_terms = [term for term in match_terms if term in text]
        score += min(0.14, 0.07 * len(matched_terms))
        if matched_terms:
            reasons.append(f"activity terms matched: {', '.join(matched_terms)}")

        preferred_matches = [term for term in preferred_terms if term in text]
        score += min(0.12, 0.04 * len(preferred_matches))
        if preferred_matches:
            reasons.append(f"preferred metadata matched: {', '.join(preferred_matches)}")

        specificity_match = _matches_identity_evidence(identity_evidence, text)
        if specificity_match:
            score += 0.30
            values = ", ".join(value for _, value in identity_evidence)
            reasons.append(f"specific supplied description matched Climatiq metadata: {values}")

        evidence_score, evidence_reasons = _trait_evidence_score(metadata, parameters, text)
        score += evidence_score
        reasons.extend(evidence_reasons)
        score = round(min(score, 1.0), 2)
        if score < MIN_ACCEPTED_SCORE:
            continue
        candidates.append(
            FactorCandidate(
                activity_id=activity_id,
                name=str(record.get("name") or activity_id),
                sector=sector or None,
                category=str(record.get("category") or "") or None,
                unit_type=_best_unit_type(metadata, unit_types),
                score=score,
                match_reasons=reasons,
                specificity_match=specificity_match,
            )
        )

    return sorted(candidates, key=lambda candidate: (-candidate.score, candidate.activity_id))


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
    for field in metadata.get("factor_trait_fields", ()):
        value = _normalized_text(parameters.get(str(field)))
        if not value:
            continue
        aliases = tuple(aliases_by_field.get(field, {}).get(value, (value,)))
        if not any(alias in text for alias in aliases):
            continue
        score += 0.06
        reasons.append(f"normalized {field} matched: {value}")
        conflicts = tuple(conflicts_by_field.get(field, {}).get(value, ()))
        if any(conflict in text for conflict in conflicts):
            score -= 0.03
            reasons.append(f"broader {field} variant matched less precisely: {value}")
    return score, reasons


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
            str(alias) in text for alias in requested_aliases
        ):
            return True
        declared_values = {
            value
            for value, aliases in field_aliases.items()
            if any(str(alias) in text for alias in aliases)
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
        record.get("description"),
    ]
    text = " ".join(str(value or "") for value in values).lower()
    return _normalized_text(text)


def _normalized_text(value: object) -> str:
    text = re.sub(r"[^a-z0-9]+", " ", str(value or "").lower())
    return re.sub(r"\s+", " ", text).strip()


def _unit_types(value: object) -> set[str]:
    return {
        token.strip().lower()
        for token in str(value or "").split(",")
        if token.strip()
    }


def _best_unit_type(metadata: dict, record_units: set[str]) -> str:
    for unit_type in metadata.get("compatible_unit_types", ()):
        if str(unit_type).lower() in record_units:
            return str(unit_type)
    return next(iter(record_units))


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
    query_terms = [str(metadata.get("climatiq_factor_query", event.activity_type)), *values]
    return " ".join(dict.fromkeys(term.strip() for term in query_terms if term.strip()))
