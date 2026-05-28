from __future__ import annotations

import re

from app.domain.activity_taxonomy import (
    ACTIVITY_TAXONOMY,
    GOODS_SERVICES_TAXONOMY,
    TRANSPORT_TAXONOMY,
    WASTE_TAXONOMY,
)
from app.domain.material_ontology import (
    WASTE_MATERIAL_SYNONYMS,
    detect_waste_disposal_method,
    detect_waste_material_classes,
)
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
CLOTHING_PURCHASE_RE = re.compile(
    r"\b(?:bought|purchased|ordered)\b[^,.;]*\b(?:shirts?|t-?shirts?|clothes|clothing|jeans|jackets?|dress(?:es)?|shoes)\b",
    re.IGNORECASE,
)
ELECTRONICS_PURCHASE_RE = re.compile(
    r"\b(?:bought|purchased|ordered)\b[^,.;]*\b(?:laptops?|phones?|smartphones?|computers?|monitors?|televisions?|tvs?|headphones?)\b",
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
CLAUSE_SPLIT_RE = re.compile(
    r"\s*(?:[.;!?]|\bthen\b|\bwhile\b|"
    r",(?=\s*(?:and\s+)?(?:i\s+)?(?:grabbed|bought|purchased|ordered|spent|got|"
    r"picked\s+up|disposed|worked|drove|"
    r"travelled|traveled|commuted|caught|took|used|ran|turned|recycled|"
    r"composted|put|threw|walked|read|studied|gaming|played))|"
    r"\band\b(?=\s+(?:i\s+)?(?:grabbed|bought|purchased|ordered|spent|got|"
    r"picked\s+up|disposed|worked|drove|"
    r"travelled|traveled|commuted|caught|took|used|ran|turned|recycled|"
    r"composted|put|threw|walked|read|studied|gaming|played)))\s+",
    re.IGNORECASE,
)
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
RUNNING_LATE_RE = re.compile(r"\brunn?ing\s+late\b", re.IGNORECASE)
RUN_WORD_RE = re.compile(r"\b(?:run|ran|running)\b", re.IGNORECASE)
FOOD_DELIVERY_CONTEXT_RE = re.compile(
    r"\b(?:uber\s+eats|doordash|deliveroo|menulog|delivery\s+app)\b",
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
            events.extend(_everyday_events(raw_clause))

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
        entities = {"detection_policy": policy}
        if activity_type == "generic_energy_use" and re.search(
            r"\b(?:pc|computer|desktop)\b", clause, re.IGNORECASE
        ):
            entities["device"] = "personal_computer"
        events.append(
            CarbonEvent(
                raw_text=clause,
                category=metadata["category"],
                activity_type=activity_type,
                entities=entities,
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
    if explicit_mode == "walking" and RUNNING_LATE_RE.search(clause):
        return None
    if (
        explicit_mode == "walking"
        and RUN_WORD_RE.search(clause)
        and not EXPLICIT_DISTANCE_RE.search(clause)
    ):
        return None
    if explicit_mode == "rideshare" and FOOD_DELIVERY_CONTEXT_RE.search(clause):
        return None
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


def _everyday_events(clause: str) -> list[CarbonEvent]:
    positioned = [
        *_goods_events(clause),
        *_waste_events(clause),
        *_unsupported_goods_events(clause),
    ]
    after = re.search(r"\bafter\b", clause, re.IGNORECASE)
    if after and any(position < after.start() for position, _ in positioned) and any(
        position > after.end() for position, _ in positioned
    ):
        positioned.sort(key=lambda candidate: (candidate[0] < after.start(), candidate[0]))
    else:
        positioned.sort(key=lambda candidate: candidate[0])
    return [event for _, event in positioned]


def _goods_events(clause: str) -> list[tuple[int, CarbonEvent]]:
    if not _goods_purchase_context(clause):
        return []
    delivery_context = bool(FOOD_DELIVERY_CONTEXT_RE.search(clause))
    positioned: list[tuple[int, CarbonEvent]] = []
    occupied: list[tuple[int, int]] = []
    for activity_type in ("coffee_purchase", "restaurant_meal", "food_purchase"):
        metadata = GOODS_SERVICES_TAXONOMY[activity_type]
        for product_class, synonyms in metadata.get("product_synonyms", {}).items():
            for synonym in sorted(synonyms, key=len, reverse=True):
                for match in re.finditer(rf"\b{re.escape(synonym)}\b", clause, re.IGNORECASE):
                    if any(_spans_overlap(match.span(), span) for span in occupied):
                        continue
                    if product_class == "unspecified_takeaway" and any(
                        event.activity_type in {"coffee_purchase", "restaurant_meal"}
                        for _, event in positioned
                    ):
                        continue
                    if product_class == "milk" and _milk_is_coffee_modifier(
                        clause,
                        match.span(),
                    ):
                        continue
                    selected_class = product_class
                    if activity_type == "coffee_purchase" and any(
                        re.search(rf"\b{re.escape(term)}\b", clause, re.IGNORECASE)
                        for term in metadata.get("unsupported_variant_terms", ())
                    ):
                        selected_class = "unsupported_coffee_variant"
                    positioned.append(
                        (
                            match.start(),
                            CarbonEvent(
                                raw_text=_component_fragment(clause, match.span()),
                                category="goods_services",
                                activity_type=activity_type,
                                entities={
                                    "product_class": selected_class,
                                    "product_description": match.group(0),
                                    "delivery_context": delivery_context,
                                },
                                confidence=Confidence.from_score(0.78),
                            ),
                        )
                    )
                    occupied.append(match.span())
    return positioned


def _unsupported_goods_events(clause: str) -> list[tuple[int, CarbonEvent]]:
    candidates = (
        (
            "clothing_purchase",
            CLOTHING_PURCHASE_RE,
            re.compile(r"\b(?:shirts?|t-?shirts?|clothes|clothing|jeans|jackets?|dress(?:es)?|shoes)\b", re.I),
        ),
        (
            "electronics_purchase",
            ELECTRONICS_PURCHASE_RE,
            re.compile(r"\b(?:laptops?|phones?|smartphones?|computers?|monitors?|televisions?|tvs?|headphones?)\b", re.I),
        ),
    )
    events = []
    for activity_type, pattern, item_pattern in candidates:
        match = pattern.search(clause)
        if match is None:
            continue
        item_match = item_pattern.search(clause, match.start(), match.end())
        item_span = item_match.span() if item_match is not None else match.span()
        events.append(
            (
                item_span[0],
                CarbonEvent(
                    raw_text=_component_fragment(clause, item_span),
                    category="goods_services",
                    activity_type=activity_type,
                    confidence=Confidence.from_score(0.60),
                    issues=[
                        Issue(
                            code="goods_services.estimation.not_implemented",
                            message=(
                                f"Detected {activity_type}, but no validated V2 "
                                "factor pathway is configured for it yet."
                            ),
                            severity="warning",
                        )
                    ],
                ),
            )
        )
    return events


def _milk_is_coffee_modifier(clause: str, span: tuple[int, int]) -> bool:
    nearby = clause[max(0, span[0] - 12) : min(len(clause), span[1] + 24)]
    return bool(re.search(r"\b(?:oat\s+)?milk\s+coffee\b", nearby, re.IGNORECASE))


def _waste_events(clause: str) -> list[tuple[int, CarbonEvent]]:
    matched_method = _waste_method(clause)
    if matched_method is None:
        if not re.search(
            r"\b(?:took\s+out|disposed\s+of)\b[^,.;]*\b(?:bag\s+of\s+)?(?:rubbish|trash|garbage|waste)\b",
            clause,
            re.IGNORECASE,
        ):
            return []
        activity_type, disposal_method, position = "landfill_waste", "unknown", 0
    else:
        activity_type, disposal_method, position = matched_method
    component_events = _waste_component_events(
        clause,
        activity_type,
        disposal_method,
        position,
    )
    if component_events:
        return component_events
    material_classes = _specific_material_classes(_material_classes(clause, activity_type))
    material_class = (
        next(iter(material_classes))
        if len(material_classes) == 1
        else "mixed" if material_classes else "unknown"
    )
    return [
        (
            position,
            CarbonEvent(
                raw_text=clause,
                category="waste",
                activity_type=activity_type,
                entities={
                    "disposal_method": disposal_method,
                    "material_class": material_class,
                    "material_description": clause,
                },
                confidence=Confidence.from_score(0.78 if disposal_method != "unknown" else 0.45),
            ),
        )
    ]


def _waste_component_events(
    clause: str,
    activity_type: str,
    disposal_method: str,
    method_position: int,
) -> list[tuple[int, CarbonEvent]]:
    material_matches = _waste_material_matches(clause)
    if len({material for material, _, _ in material_matches}) < 2:
        return []

    method_match = _waste_method_match(clause, activity_type, disposal_method)
    method_surface = method_match.group(0) if method_match else ""
    component_source = clause
    method_is_prefix = bool(method_match and method_match.start() <= material_matches[0][1][0])
    if method_match and method_is_prefix:
        component_source = clause[method_match.end() :]
    elif method_match:
        component_source = clause[: method_match.start()]

    components = _split_waste_components(component_source)
    positioned: list[tuple[int, CarbonEvent]] = []
    for component_start, component in components:
        material_classes = _specific_material_classes(
            detect_waste_material_classes(component)
        )
        if len(material_classes) != 1:
            continue
        material_class = next(iter(material_classes))
        raw_text = _waste_component_raw_text(
            method_surface,
            component,
            method_is_prefix,
        )
        if not re.search(r"\b(?:\d|half\s+(?:a\s+)?kilogram)\b", raw_text, re.I):
            raw_text = _waste_component_raw_text(
                method_surface,
                _nearest_weight_component(clause, component_start, component),
                method_is_prefix,
            )
        positioned.append(
            (
                component_start + (method_match.end() if method_match and method_is_prefix else 0),
                CarbonEvent(
                    raw_text=raw_text,
                    category="waste",
                    activity_type=activity_type,
                    entities={
                        "disposal_method": disposal_method,
                        "material_class": material_class,
                        "material_description": raw_text,
                    },
                    confidence=Confidence.from_score(
                        0.80 if disposal_method != "unknown" else 0.45
                    ),
                ),
            )
        )
    return positioned if len(positioned) >= 2 else []


def _waste_component_raw_text(
    method_surface: str,
    component: str,
    method_is_prefix: bool,
) -> str:
    component = component.strip(" ,")
    if not method_surface:
        return component
    if method_is_prefix:
        return f"{method_surface} {component}".strip()
    return f"{component} {method_surface}".strip()


def _split_waste_components(text: str) -> list[tuple[int, str]]:
    pieces: list[tuple[int, str]] = []
    start = 0
    for match in re.finditer(r"\s*(?:,|\band\b|\bplus\b|&)\s+", text, re.IGNORECASE):
        piece = text[start : match.start()].strip(" ,")
        if piece:
            pieces.append((start, piece))
        start = match.end()
    tail = text[start:].strip(" ,")
    if tail:
        pieces.append((start, tail))
    return pieces


def _nearest_weight_component(clause: str, component_start: int, component: str) -> str:
    if re.search(r"\b(?:\d|half\s+(?:a\s+)?kilogram)\b", component, re.I):
        return component
    window_start = max(0, component_start - 24)
    prefix = clause[window_start:component_start]
    weight_match = re.search(
        r"(?:\d+(?:\.\d+)?\s*(?:kg|kilograms?|g|grams?)|half\s+(?:a\s+)?kilogram)\s*(?:of\s+)?$",
        prefix,
        re.IGNORECASE,
    )
    if weight_match:
        return f"{weight_match.group(0).strip()} {component}".strip()
    return component


def _waste_material_matches(clause: str) -> list[tuple[str, tuple[int, int], str]]:
    matches: list[tuple[str, tuple[int, int], str]] = []
    for material_class, synonyms in WASTE_MATERIAL_SYNONYMS.items():
        for synonym in sorted(synonyms, key=len, reverse=True):
            for match in re.finditer(rf"\b{re.escape(synonym)}\b", clause, re.IGNORECASE):
                matches.append((material_class, match.span(), match.group(0)))
    matches.sort(key=lambda item: (item[1][0], -(item[1][1] - item[1][0])))
    selected: list[tuple[str, tuple[int, int], str]] = []
    for candidate in matches:
        if any(_spans_overlap(candidate[1], existing[1]) for existing in selected):
            continue
        selected.append(candidate)
    return selected


def _specific_material_classes(material_classes: set[str]) -> set[str]:
    classes = set(material_classes)
    specific = classes - {"general_waste", "mixed_packaging"}
    if specific:
        return specific
    if len(classes) > 1 and "general_waste" in classes:
        classes.discard("general_waste")
    return classes


def _waste_method_match(clause: str, activity_type: str, disposal_method: str):
    synonyms = WASTE_TAXONOMY.get(activity_type, {}).get("disposal_synonyms", ())
    matches = [
        match
        for term in synonyms
        for match in [re.search(rf"\b{re.escape(term)}\b", clause, re.IGNORECASE)]
        if match
    ]
    if matches:
        return sorted(matches, key=lambda match: match.start())[0]
    method_match = re.search(rf"\b{re.escape(disposal_method)}\b", clause, re.IGNORECASE)
    return method_match


def _waste_method(clause: str) -> tuple[str, str, int] | None:
    detected_method = detect_waste_disposal_method(clause)
    if detected_method is not None:
        activity_type = {
            "landfill": "landfill_waste",
            "recycling": "recycling",
            "composting": "composting",
        }.get(detected_method)
        if activity_type:
            first_position = min(
                (
                    match.start()
                    for term in WASTE_TAXONOMY[activity_type]["disposal_synonyms"]
                    for match in [re.search(rf"\b{re.escape(term)}\b", clause, re.IGNORECASE)]
                    if match
                ),
                default=0,
            )
            return activity_type, detected_method, first_position
    for activity_type in ("recycling", "composting", "landfill_waste"):
        metadata = WASTE_TAXONOMY[activity_type]
        for term in metadata["disposal_synonyms"]:
            match = re.search(rf"\b{re.escape(term)}\b", clause, re.IGNORECASE)
            if match:
                return activity_type, str(metadata["disposal_method"]), match.start()
    return None


def _material_classes(clause: str, activity_type: str) -> set[str]:
    return detect_waste_material_classes(clause)


def _goods_purchase_context(clause: str) -> bool:
    verbs = {
        verb
        for metadata in GOODS_SERVICES_TAXONOMY.values()
        for verb in metadata.get("purchase_verbs", ())
    }
    has_verb = any(re.search(rf"\b{re.escape(verb)}\b", clause, re.IGNORECASE) for verb in verbs)
    spent_on = bool(re.search(r"\bspent\b[^,.;]*\bon\b", clause, re.IGNORECASE))
    return has_verb or spent_on


def _component_fragment(clause: str, span: tuple[int, int]) -> str:
    left = list(re.finditer(r"\s+\band\b\s+|,\s+", clause[: span[0]], re.IGNORECASE))
    start = left[-1].end() if left else 0
    right = re.search(r"\s+\band\b\s+|,\s+", clause[span[1] :], re.IGNORECASE)
    end = span[1] + right.start() if right else len(clause)
    fragment = clause[start:end].strip(" ,")
    return re.sub(r"^(?:and|plus)\s+", "", fragment, flags=re.IGNORECASE)


def _spans_overlap(first: tuple[int, int], second: tuple[int, int]) -> bool:
    return first[0] < second[1] and second[0] < first[1]


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
