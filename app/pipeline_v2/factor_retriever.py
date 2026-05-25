from __future__ import annotations

import re
from typing import Callable, Protocol

from app.domain.activity_taxonomy import ACTIVITY_TAXONOMY
from app.domain.models import CarbonEvent, FactorCandidate
from app.services.climatiq_api import get_activity_metadata_records, search_activity_ids


class FactorRetriever(Protocol):
    def retrieve(
        self,
        event: CarbonEvent,
        parameters: dict,
        limit: int = 5,
    ) -> list[FactorCandidate]:
        """Return compatible Climatiq activity IDs ordered by match quality."""


class ClimatiqFactorRetriever:
    """Finds Climatiq factor activity IDs from the preloaded catalogue before API search."""

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
        local_candidates = _rank_records(
            event,
            parameters,
            self.local_records_provider(),
        )
        if local_candidates:
            return local_candidates[:limit]

        remote_records: list[dict] = []
        metadata = ACTIVITY_TAXONOMY[event.activity_type]
        for unit_type in metadata.get("compatible_unit_types", ()):
            remote_records.extend(
                self._remote_candidates(
                    _factor_query(event, parameters),
                    limit,
                    unit_type,
                    _expected_sector(event),
                )
            )
        return _rank_records(event, parameters, remote_records)[:limit]

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
            or not any(term in text for term in match_terms)
            or any(term in text for term in excluded_terms)
        ):
            continue

        reasons = [
            f"compatible Climatiq unit type: {sorted(compatible_units.intersection(unit_types))[0]}",
            f"sector matched {expected_sector}",
        ]
        score = 0.60
        matched_terms = [term for term in match_terms if term in text]
        score += min(0.14, 0.07 * len(matched_terms))
        if matched_terms:
            reasons.append(f"activity terms matched: {', '.join(matched_terms)}")

        preferred_matches = [term for term in preferred_terms if term in text]
        score += min(0.12, 0.04 * len(preferred_matches))
        if preferred_matches:
            reasons.append(f"preferred metadata matched: {', '.join(preferred_matches)}")

        trait_score, trait_reasons = _trait_score(parameters, text)
        score += trait_score
        reasons.extend(trait_reasons)
        candidates.append(
            FactorCandidate(
                activity_id=activity_id,
                name=str(record.get("name") or activity_id),
                sector=sector or None,
                category=str(record.get("category") or "") or None,
                unit_type=_best_unit_type(metadata, unit_types),
                score=round(min(score, 1.0), 2),
                match_reasons=reasons,
            )
        )

    return sorted(candidates, key=lambda candidate: (-candidate.score, candidate.activity_id))


def _trait_score(parameters: dict, text: str) -> tuple[float, list[str]]:
    score = 0.0
    reasons: list[str] = []
    fuel_type = str(parameters.get("fuel_type") or "").lower()
    fuel_terms = {
        "petrol": ("petrol", "gasoline"),
        "diesel": ("diesel",),
        "electric": ("electric", "bev"),
        "hybrid": ("hybrid", "hev"),
    }.get(fuel_type, ())
    if fuel_terms and any(term in text for term in fuel_terms):
        score += 0.10
        reasons.append(f"fuel type matched {fuel_type}")

    vehicle_size = str(parameters.get("vehicle_size") or "").lower()
    if vehicle_size and vehicle_size in text:
        score += 0.06
        reasons.append(f"vehicle size matched {vehicle_size}")
        if vehicle_size == "medium" and any(
            term in text for term in ("lower medium", "upper medium")
        ):
            score -= 0.03
    return score, reasons


def _record_text(record: dict) -> str:
    values = [record.get("activity_id"), record.get("name"), record.get("category")]
    text = " ".join(str(value or "") for value in values).lower()
    return re.sub(r"[-_]+", " ", text)


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
    query = str(metadata.get("climatiq_factor_query", event.activity_type))
    traits = [
        str(parameters[key])
        for key in ("fuel_type", "vehicle_size", "vehicle_class")
        if parameters.get(key)
    ]
    return " ".join([query, *traits]).strip()
