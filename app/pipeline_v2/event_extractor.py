from __future__ import annotations

import re

from app.domain.activity_taxonomy import TRANSPORT_TAXONOMY
from app.domain.models import (
    CarbonEvent,
    Confidence,
    Issue,
    PreprocessedJournal,
    PreprocessingCorrection,
)


HEATER_RE = re.compile(r"\b(space\s+heater|heater|heating)\b", re.IGNORECASE)
ELECTRICITY_RE = re.compile(r"\b(electricity|kwh|kilowatt\s+hours?)\b", re.IGNORECASE)
PETROL_RE = re.compile(r"\b(petrol|gasoline)\b", re.IGNORECASE)
DIESEL_RE = re.compile(r"\bdiesel\b", re.IGNORECASE)
ELECTRIC_RE = re.compile(r"\b(electric|ev)\b", re.IGNORECASE)
HYBRID_RE = re.compile(r"\bhybrid\b", re.IGNORECASE)
VEHICLE_DESCRIPTION_IN_RE = re.compile(
    r"\bin\s+(?:(?:my|a|an|the)\s+)?(?P<description>[^,.;]+?)"
    r"(?=\s+(?:for|using)\b|\s+to\b|[,.;]|$)",
    re.IGNORECASE,
)
VEHICLE_DESCRIPTION_MY_RE = re.compile(
    r"\b(?:drive|drove|driving)\s+my\s+(?P<description>[^,.;]+?)"
    r"(?=\s+(?:for|using|to)\b|[,.;]|$)",
    re.IGNORECASE,
)
VEHICLE_CLASSES = (
    ("suv", "large", re.compile(r"\b(suv|4wd|four[- ]wheel[- ]drive|crossover)\b", re.I)),
    ("ute", "large", re.compile(r"\b(ute|pickup|pick-up)\b", re.I)),
    ("van", "large", re.compile(r"\bvan\b", re.I)),
    ("sedan", "medium", re.compile(r"\bsedan\b", re.I)),
    ("hatchback", "medium", re.compile(r"\bhatchback\b", re.I)),
    ("wagon", "medium", re.compile(r"\bwagon\b", re.I)),
    ("coupe", "medium", re.compile(r"\bcoupe\b", re.I)),
)
VEHICLE_TRAIT_RE = re.compile(
    r"\b(?:my|a|an|the|petrol|gasoline|diesel|electric|ev|hybrid|car|vehicle|"
    r"passenger|small|medium|large|suv|4wd|four[- ]wheel[- ]drive|crossover|"
    r"ute|pickup|pick-up|van|sedan|hatchback|wagon|coupe)\b",
    re.IGNORECASE,
)
VEHICLE_YEAR_RE = re.compile(r"\b(?P<year>(?:19|20)\d{2})\b")
CLAUSE_SPLIT_RE = re.compile(r"\s*(?:[.;]|\bthen\b|\band\b)\s+", re.IGNORECASE)
TRANSPORT_MATCH_PRIORITY = (
    "walking",
    "bicycle_ride",
    "bus_ride",
    "train_ride",
    "rideshare",
    "flight",
    "car_ride",
    "generic_transport",
)
TRANSPORT_MODE_PATTERNS = {
    activity_type: re.compile(
        rf"\b(?:{'|'.join(re.escape(term) for term in metadata['mode_synonyms'])})\b",
        re.IGNORECASE,
    )
    for activity_type, metadata in TRANSPORT_TAXONOMY.items()
}


class JournalEventExtractor:
    def extract(self, journal: PreprocessedJournal) -> list[CarbonEvent]:
        events: list[CarbonEvent] = []

        for clause in _candidate_clauses(journal.cleaned_journal):
            if HEATER_RE.search(clause):
                events.append(
                    CarbonEvent(
                        raw_text=clause,
                        category="energy",
                        activity_type="space_heater_use",
                        entities={"device": "heater", "power_source": "electricity"},
                        confidence=Confidence.from_score(0.80),
                    )
                )
                continue

            if ELECTRICITY_RE.search(clause):
                events.append(
                    CarbonEvent(
                        raw_text=clause,
                        category="energy",
                        activity_type="electricity_use",
                        entities={"power_source": "electricity"},
                        confidence=Confidence.from_score(0.85),
                    )
                )
                continue

            transport_event = _transport_event(clause, journal.corrections)
            if transport_event is not None:
                events.append(transport_event)

        return events


def _candidate_clauses(text: str) -> list[str]:
    clauses = [clause.strip(" ,") for clause in CLAUSE_SPLIT_RE.split(text)]
    return [clause for clause in clauses if clause]


def _transport_event(
    clause: str,
    corrections: list[PreprocessingCorrection],
) -> CarbonEvent | None:
    activity_type = next(
        (
            candidate
            for candidate in TRANSPORT_MATCH_PRIORITY
            if TRANSPORT_MODE_PATTERNS[candidate].search(clause)
        ),
        None,
    )
    if activity_type is None:
        return None
    entities = _transport_entities(clause, corrections, activity_type)
    issues = _vehicle_correction_issues(clause, corrections)
    confidence_score = 0.86 if activity_type != "generic_transport" else 0.50
    confidence_score -= 0.05 if issues else 0.0

    return CarbonEvent(
        raw_text=clause,
        category="transport",
        activity_type=activity_type,
        entities=entities,
        confidence=Confidence.from_score(confidence_score),
        issues=issues,
    )


def _transport_entities(
    clause: str,
    corrections: list[PreprocessingCorrection],
    activity_type: str,
) -> dict[str, str | float | int | bool | None]:
    entities: dict[str, str | float | int | bool | None] = {"transport_mode": activity_type}
    if activity_type in {"car_ride", "rideshare"}:
        entities["vehicle_type"] = "car"

    explicit_fuel = _explicit_fuel_type(clause)
    if explicit_fuel:
        entities["explicit_fuel_type"] = explicit_fuel

    if activity_type in {"car_ride", "rideshare"}:
        vehicle_description = _unknown_vehicle_description(clause)
        if vehicle_description:
            entities["vehicle_description"] = vehicle_description
            year_match = VEHICLE_YEAR_RE.search(vehicle_description)
            if year_match:
                entities["vehicle_year"] = int(year_match.group("year"))

    for vehicle_class, vehicle_size, pattern in VEHICLE_CLASSES:
        if pattern.search(clause):
            entities["vehicle_size"] = vehicle_size
            entities["vehicle_class"] = vehicle_class
            entities["vehicle_size_source"] = "user"
            entities["vehicle_class_source"] = "user"
            break

    if _has_vehicle_typo_correction(clause, corrections):
        entities["vehicle_typo_corrected"] = True

    return entities


def _explicit_fuel_type(clause: str) -> str | None:
    if DIESEL_RE.search(clause):
        return "diesel"
    if ELECTRIC_RE.search(clause):
        return "electric"
    if HYBRID_RE.search(clause):
        return "hybrid"
    if PETROL_RE.search(clause):
        return "petrol"
    return None


def _unknown_vehicle_description(clause: str) -> str | None:
    match = VEHICLE_DESCRIPTION_IN_RE.search(clause) or VEHICLE_DESCRIPTION_MY_RE.search(clause)
    if match is None:
        return None
    description = VEHICLE_TRAIT_RE.sub(" ", match.group("description"))
    description = re.sub(r"\s+", " ", description).strip(" ,")
    return description or None


def _vehicle_correction_issues(
    clause: str,
    corrections: list[PreprocessingCorrection],
) -> list[Issue]:
    issues: list[Issue] = []
    lower_clause = clause.lower()
    for correction in corrections:
        if correction.type != "spelling" or correction.to.lower() not in lower_clause:
            continue
        code = f"preprocessing.vehicle_typo.{_code_token(correction.from_text)}"
        message = (
            f'Corrected "{correction.from_text}" to "{correction.to}" '
            "before vehicle matching."
        )
        issues.append(Issue(code=code, message=message, severity="info"))
    return issues


def _has_vehicle_typo_correction(
    clause: str,
    corrections: list[PreprocessingCorrection],
) -> bool:
    lower_clause = clause.lower()
    return any(
        correction.type == "spelling" and correction.to.lower() in lower_clause
        for correction in corrections
    )


def _code_token(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
