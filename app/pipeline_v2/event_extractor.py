from __future__ import annotations

import re

from app.domain.models import (
    CarbonEvent,
    Confidence,
    Issue,
    PreprocessedJournal,
    PreprocessingCorrection,
)


HEATER_RE = re.compile(r"\b(space\s+heater|heater|heating)\b", re.IGNORECASE)
ELECTRICITY_RE = re.compile(r"\b(electricity|kwh|kilowatt\s+hours?)\b", re.IGNORECASE)
TRAIN_RE = re.compile(r"\b(train|rail)\b", re.IGNORECASE)
BUS_RE = re.compile(r"\bbus\b", re.IGNORECASE)
CAR_RE = re.compile(r"\b(drive|drove|driving|ride|trip|commute|commuted)\b", re.IGNORECASE)
PETROL_RE = re.compile(r"\b(petrol|gasoline)\b", re.IGNORECASE)
DIESEL_RE = re.compile(r"\bdiesel\b", re.IGNORECASE)
ELECTRIC_RE = re.compile(r"\b(electric|ev)\b", re.IGNORECASE)
HYBRID_RE = re.compile(r"\bhybrid\b", re.IGNORECASE)
TOYOTA_CAMRY_RE = re.compile(r"\btoyota\s+camry\b", re.IGNORECASE)
TESLA_MODEL_3_RE = re.compile(r"\btesla\s+model\s*3\b", re.IGNORECASE)
TESLA_RE = re.compile(r"\btesla\b", re.IGNORECASE)
SUV_RE = re.compile(r"\bsuv\b", re.IGNORECASE)
CLAUSE_SPLIT_RE = re.compile(r"\s*(?:[.;]|\bthen\b|\band\b)\s+", re.IGNORECASE)


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

            transport_event = _unsupported_transport_event(clause, journal.corrections)
            if transport_event is not None:
                events.append(transport_event)

        return events


def _candidate_clauses(text: str) -> list[str]:
    clauses = [clause.strip(" ,") for clause in CLAUSE_SPLIT_RE.split(text)]
    return [clause for clause in clauses if clause]


def _unsupported_transport_event(
    clause: str,
    corrections: list[PreprocessingCorrection],
) -> CarbonEvent | None:
    if TRAIN_RE.search(clause):
        activity_type = "train_ride"
    elif BUS_RE.search(clause):
        activity_type = "bus_ride"
    elif CAR_RE.search(clause):
        return _car_ride_event(clause, corrections)
    else:
        return None

    return CarbonEvent(
        raw_text=clause,
        category="transport",
        activity_type=activity_type,
        confidence=Confidence.from_score(0.55),
        issues=[
            Issue(
                code="transport.not_implemented",
                message=(
                    "Detected a transport activity, but V2 transport estimation is not implemented yet."
                ),
                severity="warning",
            )
        ],
    )


def _car_ride_event(
    clause: str,
    corrections: list[PreprocessingCorrection],
) -> CarbonEvent:
    entities = _transport_entities(clause, corrections)
    issues = _vehicle_correction_issues(clause, corrections)
    confidence_score = 0.86 - (0.05 if issues else 0.0)

    return CarbonEvent(
        raw_text=clause,
        category="transport",
        activity_type="car_ride",
        entities=entities,
        confidence=Confidence.from_score(confidence_score),
        issues=issues,
    )


def _transport_entities(
    clause: str,
    corrections: list[PreprocessingCorrection],
) -> dict[str, str | float | int | bool | None]:
    entities: dict[str, str | float | int | bool | None] = {"vehicle_type": "car"}

    explicit_fuel = _explicit_fuel_type(clause)
    if explicit_fuel:
        entities["explicit_fuel_type"] = explicit_fuel

    if TOYOTA_CAMRY_RE.search(clause):
        entities["vehicle_make"] = "toyota"
        entities["vehicle_model"] = "camry"
    elif TESLA_MODEL_3_RE.search(clause):
        entities["vehicle_make"] = "tesla"
        entities["vehicle_model"] = "model 3"
    elif TESLA_RE.search(clause):
        entities["vehicle_make"] = "tesla"
        entities["vehicle_model"] = ""

    if SUV_RE.search(clause):
        entities["vehicle_size"] = "large"
        entities["vehicle_class"] = "suv"

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
