from __future__ import annotations

import json
import re
from collections.abc import Mapping
from typing import Any

from pydantic import ConfigDict, Field, ValidationError, model_validator

from app.domain.activity_taxonomy import (
    ACTIVITY_TAXONOMY,
    GOODS_SERVICES_TAXONOMY,
    WASTE_TAXONOMY,
)
from app.domain.material_ontology import (
    detect_waste_disposal_method,
    detect_waste_material_classes,
    normalize_waste_material,
)
from app.domain.models import (
    ActivityType,
    CarbonEvent,
    Category,
    Confidence,
    PreprocessedJournal,
    Quantity,
    QuantityDimension,
    StrictBaseModel,
)
from app.pipeline_v2.quantity_normalizer import QuantityNormalizer


UNTRUSTED_EVENT_FIELDS = {
    "activity_id",
    "activity_name",
    "assumption_code",
    "assumption_codes",
    "assumptions",
    "co2e",
    "co2e_kg",
    "confidence",
    "emission_factor",
    "emissions",
    "estimate",
    "factor",
    "factor_id",
    "factor_metadata",
    "final_confidence",
    "issue_code",
    "issue_codes",
    "issues",
    "source",
    "status",
    "unit",
}
ALLOWED_ENTITY_FIELDS = {
    "device",
    "disposal_method",
    "explicit_fuel_type",
    "fuel_type",
    "item",
    "material",
    "material_class",
    "material_description",
    "passenger_class",
    "power_source",
    "product_class",
    "product_description",
    "purchase_context",
    "route_type",
    "transport_mode",
    "vehicle_class",
    "vehicle_description",
    "vehicle_make",
    "vehicle_model",
    "vehicle_size",
    "vehicle_type",
}
UNTRUSTED_ENTITY_FIELDS = UNTRUSTED_EVENT_FIELDS | {
    "activity",
    "activity_factor",
    "assumption",
    "factor_score",
}
CONTROLLED_GENERIC_ENTITY_FIELD = "additional_entity_context"
SAFE_STRING_LENGTH = 160


class LLMQuantityCandidate(StrictBaseModel):
    model_config = ConfigDict(extra="forbid")

    value: float
    unit: str
    dimension: QuantityDimension
    surface: str | None = None
    evidence: str | None = None


class LLMEventCandidate(StrictBaseModel):
    model_config = ConfigDict(extra="forbid")

    raw_text: str = Field(..., min_length=1, max_length=500)
    category: Category
    activity_type: ActivityType
    quantities: list[LLMQuantityCandidate] = Field(default_factory=list)
    entities: dict[str, str | float | int | bool | None] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_taxonomy_match(self) -> "LLMEventCandidate":
        metadata = ACTIVITY_TAXONOMY.get(self.activity_type)
        if metadata is None:
            raise ValueError("activity_type is not in the controlled taxonomy")
        if metadata.get("category") != self.category:
            raise ValueError("activity_type does not belong to category")
        return self


def parse_llm_events_json(payload: str, journal: PreprocessedJournal) -> list[CarbonEvent]:
    raw_events = _load_event_objects(payload)
    events: list[CarbonEvent] = []
    for raw_event in raw_events:
        candidate = _validate_candidate_event(raw_event)
        if candidate is None:
            continue
        event = _candidate_to_carbon_event(candidate, journal)
        if event is not None:
            events.append(event)
    return events


def _load_event_objects(payload: str) -> list[Any]:
    data = json.loads(payload)
    if not isinstance(data, dict):
        raise ValueError("LLM extraction payload must be a JSON object")
    if set(data.keys()) != {"events"}:
        raise ValueError("LLM extraction payload must contain only an events key")
    events = data["events"]
    if not isinstance(events, list):
        raise ValueError("LLM extraction events field must be a list")
    return events


def _validate_candidate_event(raw_event: Any) -> LLMEventCandidate | None:
    if not isinstance(raw_event, Mapping):
        return None
    sanitized = _sanitize_event_mapping(raw_event)
    try:
        return LLMEventCandidate.model_validate(sanitized)
    except (TypeError, ValidationError, ValueError):
        return None


def _sanitize_event_mapping(raw_event: Mapping[str, Any]) -> dict[str, Any]:
    sanitized: dict[str, Any] = {}
    for key, value in raw_event.items():
        if key in UNTRUSTED_EVENT_FIELDS:
            continue
        sanitized[key] = value
    return sanitized


def _candidate_to_carbon_event(
    candidate: LLMEventCandidate,
    journal: PreprocessedJournal,
) -> CarbonEvent | None:
    raw_text = _trimmed_text(candidate.raw_text)
    if not _span_is_in_journal(raw_text, journal):
        return None
    if candidate.category == "waste" and not _has_waste_context(raw_text):
        return None

    base_event = CarbonEvent(
        raw_text=raw_text,
        category=candidate.category,
        activity_type=candidate.activity_type,
        entities={},
        confidence=Confidence.from_score(0.75),
    )
    quantities = _trusted_quantity_hints(candidate, base_event)
    entities = _safe_entities(candidate, raw_text)
    return base_event.model_copy(update={"quantities": quantities, "entities": entities})


def _trusted_quantity_hints(
    candidate: LLMEventCandidate,
    event: CarbonEvent,
) -> list[Quantity]:
    deterministic = QuantityNormalizer().normalize(candidate.raw_text, event)
    accepted: list[Quantity] = []
    seen: set[tuple[str, str | None]] = set()
    for hint in candidate.quantities:
        if not hint.surface:
            continue
        if not _contains_text(candidate.raw_text, hint.surface):
            continue
        match = _matching_deterministic_quantity(hint, deterministic)
        if match is None:
            continue
        key = (match.dimension, _normalized_text(match.surface or ""))
        if key in seen:
            continue
        seen.add(key)
        accepted.append(match)
    return accepted


def _matching_deterministic_quantity(
    hint: LLMQuantityCandidate,
    deterministic: list[Quantity],
) -> Quantity | None:
    surface = _normalized_text(hint.surface or "")
    for quantity in deterministic:
        if quantity.dimension != hint.dimension:
            continue
        quantity_surface = _normalized_text(quantity.surface or "")
        if quantity_surface and (
            quantity_surface in surface or surface in quantity_surface
        ):
            return quantity
    return None


def _safe_entities(
    candidate: LLMEventCandidate,
    raw_text: str,
) -> dict[str, str | float | int | bool | None]:
    safe: dict[str, str | float | int | bool | None] = {}
    additional_context: list[str] = []
    for key, value in candidate.entities.items():
        normalized_key = _safe_key(key)
        if not normalized_key or normalized_key in UNTRUSTED_ENTITY_FIELDS:
            continue
        safe_value = _safe_entity_value(value)
        if safe_value is None:
            continue
        if normalized_key in ALLOWED_ENTITY_FIELDS:
            safe[normalized_key] = safe_value
        else:
            additional_context.append(f"{normalized_key}={safe_value}")
    if additional_context:
        safe[CONTROLLED_GENERIC_ENTITY_FIELD] = "; ".join(additional_context)[:240]

    _apply_activity_entity_defaults(safe, candidate, raw_text)
    return safe


def _apply_activity_entity_defaults(
    entities: dict[str, str | float | int | bool | None],
    candidate: LLMEventCandidate,
    raw_text: str,
) -> None:
    if candidate.category == "energy":
        _apply_energy_entities(entities, candidate, raw_text)
    elif candidate.category == "goods_services":
        _apply_goods_entities(entities, candidate, raw_text)
    elif candidate.category == "waste":
        _apply_waste_entities(entities, candidate, raw_text)
    elif candidate.category == "transport":
        entities["transport_mode"] = candidate.activity_type


def _apply_energy_entities(
    entities: dict[str, str | float | int | bool | None],
    candidate: LLMEventCandidate,
    raw_text: str,
) -> None:
    if candidate.activity_type == "space_heater_use":
        entities["device"] = "heater"
        if re.search(r"\b(?:natural\s+gas|gas)\b", raw_text, re.IGNORECASE):
            entities["power_source"] = "natural_gas"
        else:
            entities["power_source"] = "electricity"
    elif candidate.activity_type == "generic_energy_use":
        device = _entity_string(entities.get("device"))
        if re.search(r"\b(?:pc|computer|desktop)\b", f"{raw_text} {device}", re.IGNORECASE):
            entities["device"] = "personal_computer"
        elif device:
            entities["device"] = device


def _apply_goods_entities(
    entities: dict[str, str | float | int | bool | None],
    candidate: LLMEventCandidate,
    raw_text: str,
) -> None:
    product_class = _matched_goods_product_class(candidate.activity_type, raw_text)
    if product_class:
        entities["product_class"] = product_class
    if not _entity_string(entities.get("product_description")):
        item = _entity_string(entities.get("item"))
        entities["product_description"] = item if item and _contains_text(raw_text, item) else raw_text
    if re.search(r"\bdelivery\s+app\b", raw_text, re.IGNORECASE):
        entities["delivery_context"] = True
    purchase_context = _entity_string(entities.get("purchase_context"))
    if purchase_context in {"delivery", "delivery_app"}:
        entities["delivery_context"] = True


def _apply_waste_entities(
    entities: dict[str, str | float | int | bool | None],
    candidate: LLMEventCandidate,
    raw_text: str,
) -> None:
    disposal_method = _waste_disposal_method(candidate.activity_type, raw_text)
    entities["disposal_method"] = disposal_method
    material_classes = _material_classes(raw_text, candidate.activity_type)
    if len(material_classes) == 1:
        entities["material_class"] = next(iter(material_classes))
    elif len(material_classes) > 1:
        entities["material_class"] = "mixed"
    else:
        controlled_material = _controlled_material_class(
            _entity_string(entities.get("material_class"))
            or _entity_string(entities.get("material")),
            candidate.activity_type,
            raw_text,
        )
        entities["material_class"] = controlled_material or "unknown"
    entities["material_description"] = raw_text


def _matched_goods_product_class(activity_type: str, text: str) -> str | None:
    metadata = GOODS_SERVICES_TAXONOMY.get(activity_type, {})
    for product_class, synonyms in metadata.get("product_synonyms", {}).items():
        if product_class == "unspecified_takeaway":
            continue
        if any(re.search(rf"\b{re.escape(term)}\b", text, re.IGNORECASE) for term in synonyms):
            return str(product_class)
    if activity_type == "restaurant_meal" and re.search(
        r"\b(?:takeaway|takeout|restaurant|meal|delivery\s+app)\b",
        text,
        re.IGNORECASE,
    ):
        return "unspecified_takeaway"
    return None


def _controlled_material_class(
    proposed: str,
    activity_type: str,
    raw_text: str,
) -> str | None:
    return normalize_waste_material(proposed, raw_text)


def _material_classes(raw_text: str, activity_type: str) -> set[str]:
    return detect_waste_material_classes(raw_text)


def _waste_disposal_method(activity_type: str, raw_text: str) -> str:
    detected = detect_waste_disposal_method(raw_text)
    if detected is not None:
        return detected
    if activity_type in {"recycling", "composting"}:
        return str(WASTE_TAXONOMY[activity_type]["disposal_method"])
    return "unknown"


def _has_waste_context(raw_text: str) -> bool:
    return bool(
        re.search(
            r"\b(?:recycled|recycle|recycling\s+bin|composted|compost|compost\s+bin|"
            r"landfill\s+bin|general\s+rubbish|general\s+waste|threw\s+away|"
            r"discarded|disposed\s+of|took\s+out)\b",
            raw_text,
            re.IGNORECASE,
        )
    )


def _span_is_in_journal(raw_text: str, journal: PreprocessedJournal) -> bool:
    return _contains_text(journal.raw_journal, raw_text) or _contains_text(
        journal.cleaned_journal,
        raw_text,
    )


def _contains_text(container: str, fragment: str) -> bool:
    return _normalized_text(fragment) in _normalized_text(container)


def _normalized_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def _trimmed_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip(" \t\r\n,.;")


def _safe_key(key: str) -> str:
    return re.sub(r"[^a-z0-9_]+", "_", str(key).strip().lower()).strip("_")


def _safe_entity_value(value: object) -> str | float | int | bool | None:
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        cleaned = _trimmed_text(value)
        return cleaned[:SAFE_STRING_LENGTH] if cleaned else None
    return None


def _entity_string(value: object) -> str:
    if isinstance(value, str):
        return value.strip().lower()
    return ""
