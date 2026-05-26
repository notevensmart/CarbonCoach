from __future__ import annotations

from dataclasses import dataclass
import re

from app.domain.activity_taxonomy import ACTIVITY_TAXONOMY
from app.domain.models import CarbonEvent, FactorCandidate


MIN_ACCEPTED_FACTOR_SCORE = 0.55

_UNIT_PARAMETER_REQUIREMENTS = {
    "energy": ("energy", "energy_unit", "kwh"),
    "distance": ("distance", "distance_unit", "km"),
    "passengeroverdistance": ("distance", "distance_unit", "km"),
}

_CATEGORY_MARKERS = {
    "energy": {"energy", "electricity", "power"},
    "transport": {"transport", "vehicle", "vehicles", "travel", "passenger"},
    "waste": {"waste"},
    "goods_services": {"goods", "services", "purchase"},
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
    ) -> FactorValidation:
        return self._validate(
            event,
            parameters,
            unit_type=record.get("unit_type"),
            sector=record.get("sector"),
            category=record.get("category"),
        )

    def validate_candidate(
        self,
        event: CarbonEvent,
        parameters: dict,
        candidate: FactorCandidate,
    ) -> FactorValidation:
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
        )

    def _validate(
        self,
        event: CarbonEvent,
        parameters: dict,
        *,
        unit_type: object,
        sector: object,
        category: object,
    ) -> FactorValidation:
        taxonomy = ACTIVITY_TAXONOMY.get(event.activity_type)
        if taxonomy is None:
            return FactorValidation(
                compatible=False,
                errors=(f"No factor taxonomy exists for {event.activity_type}.",),
            )

        required_dimensions = tuple(taxonomy.get("required_quantity_dimensions", ()))
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

        compatible_units = {
            _normalized_text(value)
            for value in taxonomy.get("compatible_unit_types", ())
        }
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

        expected_sector = event.category
        normalized_sector = _normalized_text(sector)
        if normalized_sector and normalized_sector != expected_sector:
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
        if normalized_sector:
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
