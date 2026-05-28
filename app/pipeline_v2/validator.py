from __future__ import annotations

from dataclasses import dataclass
import re

from app.domain.factor_intents import FactorIntent
from app.domain.material_ontology import (
    material_conflicts,
    material_matches,
    method_conflicts,
    method_matches,
)
from app.domain.activity_taxonomy import ACTIVITY_TAXONOMY
from app.domain.models import CarbonEvent, FactorCandidate


MIN_ACCEPTED_FACTOR_SCORE = 0.55

_UNIT_PARAMETER_REQUIREMENTS = {
    "energy": ("energy", "energy_unit", "kwh"),
    "distance": ("distance", "distance_unit", "km"),
    "passengeroverdistance": ("distance", "distance_unit", "km"),
    "number": ("number", "number_unit", "item"),
    "weight": ("weight", "weight_unit", "kg"),
    "money": ("money", "money_unit", "usd"),
}

_CATEGORY_MARKERS = {
    "energy": {"energy", "electricity", "power"},
    "transport": {"transport", "vehicle", "vehicles", "travel", "passenger"},
    "waste": {
        "waste",
        "recycling",
        "recycle",
        "landfill",
        "compost",
        "composting",
        "disposal",
        "municipal",
        "end",
        "life",
    },
    "goods_services": {
        "goods",
        "services",
        "purchase",
        "food",
        "coffee",
        "beverage",
        "restaurant",
        "meal",
        "grocery",
        "groceries",
    },
}


@dataclass(frozen=True)
class FactorValidation:
    compatible: bool
    unit_type: str | None = None
    match_reasons: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()


class FactorCompatibilityValidator:
    """Validates factor metadata against normalized event parameters."""

    def validate_record(
        self,
        event: CarbonEvent,
        parameters: dict,
        record: dict,
        intent: FactorIntent | None = None,
    ) -> FactorValidation:
        return self._validate(
            event,
            parameters,
            unit_type=record.get("unit_type"),
            sector=record.get("sector"),
            category=record.get("category"),
            intent=intent,
            semantic_text=_record_text(record),
        )

    def validate_candidate(
        self,
        event: CarbonEvent,
        parameters: dict,
        candidate: FactorCandidate,
        intent: FactorIntent | None = None,
    ) -> FactorValidation:
        if not candidate.activity_id.strip():
            return FactorValidation(
                compatible=False,
                errors=("Factor activity_id is required before a Climatiq request.",),
            )
        if candidate.score < MIN_ACCEPTED_FACTOR_SCORE:
            return FactorValidation(
                compatible=False,
                errors=(
                    f"Factor score {candidate.score:.2f} is below the "
                    f"{MIN_ACCEPTED_FACTOR_SCORE:.2f} acceptance threshold.",
                ),
            )
        return self._validate(
            event,
            parameters,
            unit_type=candidate.unit_type,
            sector=candidate.sector,
            category=candidate.category,
            intent=intent,
            semantic_text=_record_text(
                {
                    "activity_id": candidate.activity_id,
                    "name": candidate.name,
                    "sector": candidate.sector,
                    "category": candidate.category,
                    "unit_type": candidate.unit_type,
                }
            ),
        )

    def _validate(
        self,
        event: CarbonEvent,
        parameters: dict,
        *,
        unit_type: object,
        sector: object,
        category: object,
        intent: FactorIntent | None = None,
        semantic_text: str = "",
    ) -> FactorValidation:
        taxonomy = ACTIVITY_TAXONOMY.get(event.activity_type)
        if taxonomy is None:
            return FactorValidation(
                compatible=False,
                errors=(f"No factor taxonomy exists for {event.activity_type}.",),
            )

        required_dimensions = _required_dimensions(taxonomy, intent)
        missing_dimensions = [
            dimension for dimension in required_dimensions if dimension not in parameters
        ]
        if missing_dimensions:
            return FactorValidation(
                compatible=False,
                errors=(
                    "Missing normalized parameters for required dimensions: "
                    + ", ".join(missing_dimensions),
                ),
            )

        compatible_units = _compatible_units(taxonomy, intent)
        supplied_units = _unit_types(unit_type)
        matched_units = compatible_units.intersection(supplied_units)
        if not matched_units:
            return FactorValidation(
                compatible=False,
                errors=(
                    f"Factor unit type {unit_type!s} is incompatible with "
                    f"{event.activity_type}.",
                ),
            )

        semantic_error = _semantic_constraint_error(intent, semantic_text)
        if semantic_error:
            return FactorValidation(compatible=False, errors=(semantic_error,))

        selected_unit = next(
            (
                str(value)
                for value in taxonomy.get("compatible_unit_types", ())
                if _normalized_text(value) in matched_units
            ),
            str(unit_type),
        )
        required = _UNIT_PARAMETER_REQUIREMENTS.get(_normalized_text(selected_unit))
        if required is None:
            return FactorValidation(
                compatible=False,
                errors=(f"Unsupported Climatiq unit type: {selected_unit}.",),
            )
        quantity_key, unit_key, expected_unit = required
        if quantity_key not in parameters or unit_key not in parameters:
            return FactorValidation(
                compatible=False,
                errors=(
                    f"Factor unit type {selected_unit} requires {quantity_key} "
                    f"and {unit_key} parameters.",
                ),
            )
        if _normalized_text(parameters[unit_key]) != expected_unit:
            return FactorValidation(
                compatible=False,
                errors=(
                    f"Parameter {unit_key}={parameters[unit_key]!s} is incompatible "
                    f"with {selected_unit}.",
                ),
            )

        normalized_sector = _normalized_text(sector)
        sector_family = _category_family(sector)
        if normalized_sector and sector_family != event.category:
            return FactorValidation(
                compatible=False,
                errors=(
                    f"Factor sector {sector!s} is incompatible with {event.category}.",
                ),
            )

        category_family = _category_family(category)
        if category_family and category_family != event.category:
            return FactorValidation(
                compatible=False,
                errors=(
                    f"Factor category {category!s} is incompatible with {event.category}.",
                ),
            )

        reasons = [
            f"unit_type matched required {required_dimensions[0]} parameters: {selected_unit}"
        ]
        if sector_family == event.category:
            reasons.append(f"sector matched category: {event.category}")
        if category_family == event.category:
            reasons.append(f"factor category supports {event.category}")
        return FactorValidation(
            compatible=True,
            unit_type=selected_unit,
            match_reasons=tuple(reasons),
        )


def _unit_types(value: object) -> set[str]:
    return {
        _normalized_text(token)
        for token in str(value or "").split(",")
        if token.strip()
    }


def _required_dimensions(taxonomy: dict, intent: FactorIntent | None) -> tuple[str, ...]:
    if intent is None:
        return tuple(taxonomy.get("required_quantity_dimensions", ()))
    return tuple(
        key
        for key in intent.required_parameters
        if key in {"energy", "distance", "number", "weight", "money"}
    )


def _compatible_units(taxonomy: dict, intent: FactorIntent | None) -> set[str]:
    if intent is not None:
        return {_normalized_text(intent.unit_type)}
    return {_normalized_text(value) for value in taxonomy.get("compatible_unit_types", ())}


def _category_family(category: object) -> str | None:
    tokens = set(_normalized_text(category).split())
    if not tokens:
        return None
    matches = [
        family for family, markers in _CATEGORY_MARKERS.items() if markers.intersection(tokens)
    ]
    return matches[0] if len(matches) == 1 else None


def _normalized_text(value: object) -> str:
    text = re.sub(r"[^a-z0-9]+", " ", str(value or "").lower())
    return re.sub(r"\s+", " ", text).strip()


def _record_text(record: dict) -> str:
    return _normalized_text(
        " ".join(
            str(value or "")
            for value in _record_scalar_values(record)
        )
    )


def _semantic_constraint_error(intent: FactorIntent | None, text: str) -> str | None:
    if intent is None:
        return None
    constraints = intent.hard_constraints
    requested_method = constraints.get("disposal_method")
    if requested_method:
        conflicting_method = method_conflicts(requested_method, text)
        if conflicting_method:
            return (
                f"{conflicting_method} method conflicts with "
                f"{requested_method} disposal intent."
            )
        if not method_matches(requested_method, text):
            return f"Factor metadata does not show {requested_method} disposal method."
    requested_material = constraints.get("material_class")
    if requested_material:
        conflicting_material = material_conflicts(requested_material, text)
        if conflicting_material:
            return (
                f"{conflicting_material} material conflicts with "
                f"{requested_material} material intent."
            )
        if not material_matches(requested_material, text):
            return f"Factor metadata does not show {requested_material} material."
    requested_product = constraints.get("product_class")
    if requested_product:
        conflicting_product = _product_conflict(requested_product, text)
        if conflicting_product:
            return (
                f"{conflicting_product} product conflicts with "
                f"{requested_product} product intent."
            )
        if not _product_matches(requested_product, text):
            return f"Factor metadata does not show {requested_product} product."
    return None


def _product_conflict(requested_product: str, text: str) -> str | None:
    detected = _detected_products(text)
    if not detected or requested_product in detected:
        return None
    return sorted(detected)[0]


def _product_matches(requested_product: str, text: str) -> bool:
    return requested_product in _detected_products(text)


def _detected_products(text: str) -> set[str]:
    tokens = set(text.split())
    detected = set()
    if {"coffee", "coffees", "beverage", "latte"}.intersection(tokens) or (
        "flat" in tokens and "white" in tokens
    ):
        detected.add("coffee")
    if "burrito" in tokens:
        detected.add("beef_burrito" if "beef" in tokens else "burrito")
    elif "beef" in tokens:
        detected.add("beef")
    if {"groceries", "grocery"}.intersection(tokens):
        detected.add("groceries")
    return detected


def _record_scalar_values(record: dict):
    for value in record.values():
        if isinstance(value, (str, int, float)):
            yield value
        elif isinstance(value, (list, tuple, set)):
            for item in value:
                if isinstance(item, (str, int, float)):
                    yield item
        elif isinstance(value, dict):
            for item in value.values():
                if isinstance(item, (str, int, float)):
                    yield item
