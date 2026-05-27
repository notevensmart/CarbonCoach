from __future__ import annotations

import re

from app.domain.activity_taxonomy import ACTIVITY_TAXONOMY, TRANSPORT_TAXONOMY
from app.domain.models import (
    CarbonEvent,
    Confidence,
    Issue,
    PreprocessedJournal,
    PreprocessingCorrection,
)


HEATER_RE = re.compile(r"\b(space\s+heater|heater|heating)\b", re.IGNORECASE)
AIR_CONDITIONER_RE = re.compile(
    r"\b(air\s+condition(?:er|ing)|a/c|ac)\b",
    re.IGNORECASE,
)
ELECTRICITY_RE = re.compile(r"\b(electricity|kwh|kilowatt\s+hours?)\b", re.IGNORECASE)
NATURAL_GAS_RE = re.compile(r"\b(natural\s+gas|gas)\b", re.IGNORECASE)
PETROL_RE = re.compile(r"\b(petrol|gasoline)\b", re.IGNORECASE)
DIESEL_RE = re.compile(r"\bdiesel\b", re.IGNORECASE)
ELECTRIC_RE = re.compile(r"\b(electric|ev)\b", re.IGNORECASE)
HYBRID_RE = re.compile(r"\bhybrid\b", re.IGNORECASE)
FLIGHT_ROUTE_RE = re.compile(
    r"\b(domestic(?:ally)?|international(?:ly)?|overseas)\b",
    re.IGNORECASE,
)
FLIGHT_CLASS_RE = re.compile(
    r"\b(premium\s+economy|business(?:\s+class)?|first(?:\s+class)?|economy)\b",
    re.IGNORECASE,
)
POWERED_BICYCLE_RE = re.compile(
    r"\b(?:e[- ]?bike|electric\s+bicycle|electric\s+bike|pedal[- ]?assist(?:ed)?\s+bike)\b",
    re.IGNORECASE,
)
RECYCLING_RE = re.compile(
    r"\b(?:recycle(?:d|ing)?|sorted)\b[^,.;]*\b(?:plastic|bottles?|cans?|glass|paper|cardboard|packaging)\b"
    r"|\b(?:plastic|bottles?|cans?|glass|paper|cardboard|packaging)\b[^,.;]*\brecycl(?:e|ed|ing)\b",
    re.IGNORECASE,
)
COMPOSTING_RE = re.compile(r"\b(?:compost(?:ed|ing)?|compost\s+bin)\b", re.IGNORECASE)
LANDFILL_WASTE_RE = re.compile(
    r"\b(?:threw|throw|discarded|disposed\s+of|put)\b[^,.;]*\b(?:trash|rubbish|garbage|landfill|general\s+waste)\b"
    r"|\b(?:landfill|general\s+waste)\b",
    re.IGNORECASE,
)
CLOTHING_PURCHASE_RE = re.compile(
    r"\b(?:bought|purchased|ordered)\b[^,.;]*\b(?:shirts?|t-?shirts?|clothes|clothing|jeans|jackets?|dress(?:es)?|shoes)\b",
    re.IGNORECASE,
)
ELECTRONICS_PURCHASE_RE = re.compile(
    r"\b(?:bought|purchased|ordered)\b[^,.;]*\b(?:laptops?|phones?|smartphones?|computers?|monitors?|televisions?|tvs?|headphones?)\b",
    re.IGNORECASE,
)
COFFEE_PURCHASE_RE = re.compile(
    r"\b(?:bought|purchased|ordered|spent\b[^,.;]*\bon)\b[^,.;]*\bcoffee\b",
    re.IGNORECASE,
)
RESTAURANT_MEAL_RE = re.compile(
    r"\b(?:ate|dined|had|ordered)\b[^,.;]*\b(?:restaurant|takeaway|takeout)\b"
    r"|\b(?:restaurant|takeaway|takeout)\b[^,.;]*\b(?:meal|dinner|lunch|order(?:ed)?)\b",
    re.IGNORECASE,
)
FOOD_PURCHASE_RE = re.compile(
    r"\b(?:bought|purchased)\b[^,.;]*\b(?:groceries|grocery|food)\b",
    re.IGNORECASE,
)
VEHICLE_DISTANCE_SUFFIX = r"\s+\d+(?:\.\d+)?\s*(?:k|kms?|kilometers?|kilometres?)\b"
VEHICLE_DESCRIPTION_IN_RE = re.compile(
    r"\bin\s+(?:(?:my|a|an|the)\s+)?(?P<description>[^,.;]+?)"
    rf"(?=\s+(?:for|using)\b|\s+to\b|{VEHICLE_DISTANCE_SUFFIX}|[,.;]|$)",
    re.IGNORECASE,
)
VEHICLE_DESCRIPTION_MY_RE = re.compile(
    r"\b(?:drive|drove|driving)\s+my\s+(?P<description>[^,.;]+?)"
    rf"(?=\s+(?:for|using|to)\b|{VEHICLE_DISTANCE_SUFFIX}|[,.;]|$)",
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
CLAUSE_SPLIT_RE = re.compile(r"\s*(?:[,.;!?]|\bthen\b|\band\b)\s+", re.IGNORECASE)
ROAD_MOVEMENT_RE = re.compile(
    r"\b(?:drive|drove|driving|went|travelled|traveled|commuted?)\b",
    re.IGNORECASE,
)
DIRECT_DRIVING_RE = re.compile(r"\b(?:drive|drove|driving)\b", re.IGNORECASE)
EXPLICIT_DISTANCE_RE = re.compile(
    r"\b\d+(?:\.\d+)?\s*(?:k|kms?|kilometers?|kilometres?)\b",
    re.IGNORECASE,
)
ROAD_VEHICLE_RE = re.compile(
    r"\b(?:car|suv|4wd|four[- ]wheel[- ]drive|crossover|ute|pickup|pick-up|"
    r"van|sedan|hatchback|wagon|coupe)\b",
    re.IGNORECASE,
)
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

        for raw_clause, clause in _candidate_clause_pairs(journal):
            recognized_event = None
            if HEATER_RE.search(clause):
                power_source = (
                    "natural_gas" if NATURAL_GAS_RE.search(clause) else "electricity"
                )
                recognized_event = CarbonEvent(
                    raw_text=clause,
                    category="energy",
                    activity_type="space_heater_use",
                    entities={"device": "heater", "power_source": power_source},
                    confidence=Confidence.from_score(0.80),
                )
            elif AIR_CONDITIONER_RE.search(clause):
                recognized_event = CarbonEvent(
                    raw_text=clause,
                    category="energy",
                    activity_type="air_conditioner_use",
                    entities={"device": "air_conditioner", "power_source": "electricity"},
                    confidence=Confidence.from_score(0.80),
                )
            elif ELECTRICITY_RE.search(clause):
                recognized_event = CarbonEvent(
                    raw_text=clause,
                    category="energy",
                    activity_type="electricity_use",
                    entities={"power_source": "electricity"},
                    confidence=Confidence.from_score(0.85),
                )
            else:
                recognized_event = _policy_event(clause, "unresolved")
                if recognized_event is None:
                    recognized_event = _transport_event(clause, journal.corrections)

            if recognized_event is not None:
                events.append(recognized_event.model_copy(update={"raw_text": raw_clause}))

            events.extend(
                event.model_copy(update={"raw_text": raw_clause})
                for event in _policy_events(clause, "unresolved")
                if recognized_event is None or event.activity_type != recognized_event.activity_type
            )
            events.extend(
                event.model_copy(update={"raw_text": raw_clause})
                for event in _policy_events(clause, "not_estimated")
            )
            events.extend(
                event.model_copy(update={"raw_text": raw_clause})
                for event in _known_unsupported_events(clause)
            )

        return events


def _candidate_clauses(text: str) -> list[str]:
    clauses = [clause.strip(" ,") for clause in CLAUSE_SPLIT_RE.split(text)]
    return [clause for clause in clauses if clause]


def _candidate_clause_pairs(journal: PreprocessedJournal) -> list[tuple[str, str]]:
    raw_clauses = _candidate_clauses(journal.raw_journal)
    cleaned_clauses = _candidate_clauses(journal.cleaned_journal)
    if len(raw_clauses) == len(cleaned_clauses):
        return list(zip(raw_clauses, cleaned_clauses))
    return [(clause, clause) for clause in cleaned_clauses]


def _transport_event(
    clause: str,
    corrections: list[PreprocessingCorrection],
) -> CarbonEvent | None:
    activity_type = _transport_activity_type(clause)
    if activity_type is None:
        return None
    if activity_type == "bicycle_ride" and POWERED_BICYCLE_RE.search(clause):
        activity_type = "generic_transport"
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


def _policy_event(clause: str, policy: str) -> CarbonEvent | None:
    return next(iter(_policy_events(clause, policy)), None)


def _policy_events(clause: str, policy: str) -> list[CarbonEvent]:
    events = []
    for activity_type, metadata in ACTIVITY_TAXONOMY.items():
        if metadata.get("estimate_policy") != policy:
            continue
        patterns = metadata.get("detection_patterns", ())
        if not any(re.search(pattern, clause, re.IGNORECASE) for pattern in patterns):
            continue
        events.append(
            CarbonEvent(
                raw_text=clause,
                category=metadata["category"],
                activity_type=activity_type,
                entities={"detection_policy": policy},
                confidence=Confidence.from_score(0.90 if policy == "not_estimated" else 0.30),
            )
        )
    return events


def _transport_activity_type(clause: str) -> str | None:
    description = _unknown_vehicle_description(clause)
    mode_terms = {
        term.lower()
        for metadata in TRANSPORT_TAXONOMY.values()
        for term in metadata["mode_synonyms"]
    }
    explicit_mode = next(
        (
            candidate
            for candidate in TRANSPORT_MATCH_PRIORITY
            if TRANSPORT_MODE_PATTERNS[candidate].search(clause)
        ),
        None,
    )
    has_road_vehicle_context = bool(
        description and description.lower() not in mode_terms or ROAD_VEHICLE_RE.search(clause)
    )
    if (
        has_road_vehicle_context
        and DIRECT_DRIVING_RE.search(clause)
        and EXPLICIT_DISTANCE_RE.search(clause)
    ):
        return "car_ride"
    if explicit_mode in {
        "walking",
        "bicycle_ride",
        "bus_ride",
        "train_ride",
        "rideshare",
        "flight",
    }:
        return explicit_mode
    is_named_driven_vehicle = bool(
        has_road_vehicle_context
        and ROAD_MOVEMENT_RE.search(clause)
        and EXPLICIT_DISTANCE_RE.search(clause)
    )
    if is_named_driven_vehicle:
        return "car_ride"
    return explicit_mode


def _known_unsupported_events(clause: str) -> list[CarbonEvent]:
    candidates = (
        ("waste", "recycling", RECYCLING_RE),
        ("waste", "composting", COMPOSTING_RE),
        ("waste", "landfill_waste", LANDFILL_WASTE_RE),
        ("goods_services", "clothing_purchase", CLOTHING_PURCHASE_RE),
        ("goods_services", "electronics_purchase", ELECTRONICS_PURCHASE_RE),
        ("goods_services", "coffee_purchase", COFFEE_PURCHASE_RE),
        ("goods_services", "restaurant_meal", RESTAURANT_MEAL_RE),
        ("goods_services", "food_purchase", FOOD_PURCHASE_RE),
    )
    return [
        CarbonEvent(
            raw_text=clause,
            category=category,
            activity_type=activity_type,
            confidence=Confidence.from_score(0.60),
            issues=[
                Issue(
                    code=f"{category}.estimation.not_implemented",
                    message=(
                        f"Detected {activity_type}, but no validated V2 emission "
                        "factor pathway is configured for this activity yet."
                    ),
                    severity="warning",
                )
            ],
        )
        for category, activity_type, pattern in candidates
        if pattern.search(clause)
    ]


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
        entities["fuel_type"] = explicit_fuel
        entities["fuel_type_source"] = "user"
    elif POWERED_BICYCLE_RE.search(clause):
        entities["explicit_fuel_type"] = "electric"
        entities["fuel_type"] = "electric"
        entities["fuel_type_source"] = "user"
        entities["transport_description"] = "electric_bicycle"

    if activity_type == "flight":
        route_match = FLIGHT_ROUTE_RE.search(clause)
        if route_match:
            entities["route_type"] = _normalized_flight_route(route_match.group(1))
            entities["route_type_source"] = "user"
        class_match = FLIGHT_CLASS_RE.search(clause)
        if class_match:
            entities["passenger_class"] = _normalized_flight_class(class_match.group(1))
            entities["passenger_class_source"] = "user"

    for field, values in TRANSPORT_TAXONOMY[activity_type].get(
        "entity_value_synonyms",
        {},
    ).items():
        for value, terms in values.items():
            if any(re.search(rf"\b{re.escape(term)}\b", clause, re.IGNORECASE) for term in terms):
                entities[field] = value
                entities[f"{field}_source"] = "user"
                break

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


def _normalized_flight_class(surface: str) -> str:
    return surface.lower().replace(" class", "").replace(" ", "_")


def _normalized_flight_route(surface: str) -> str:
    if surface.lower() in {"international", "internationally", "overseas"}:
        return "international"
    return "domestic"


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
