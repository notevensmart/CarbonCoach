from __future__ import annotations

from app.domain.assumptions import (
    VEHICLE_MODEL_DEFAULTS,
    explicit_fuel_override_assumption,
    generic_car_default_assumption,
    generic_car_size_default_assumption,
    vehicle_model_default_assumption,
)
from app.domain.models import Assumption, CarbonEvent, Issue


class EntityEnricher:
    def enrich(self, event: CarbonEvent) -> CarbonEvent:
        if event.category != "transport" or event.activity_type != "car_ride":
            return event
        return self._enrich_car_ride(event)

    def _enrich_car_ride(self, event: CarbonEvent) -> CarbonEvent:
        entities = dict(event.entities)
        assumptions = list(event.assumptions)
        issues = list(event.issues)

        make = _entity_text(entities.get("vehicle_make"))
        model = _entity_text(entities.get("vehicle_model"))
        explicit_fuel = _entity_text(entities.get("explicit_fuel_type"))
        default = _vehicle_default(make, model)

        if default is not None:
            _apply_model_default(
                entities=entities,
                assumptions=assumptions,
                issues=issues,
                default=default,
                explicit_fuel=explicit_fuel,
                typo_corrected=bool(entities.get("vehicle_typo_corrected")),
            )
        else:
            _apply_generic_defaults(entities, assumptions, explicit_fuel)

        entities.setdefault("vehicle_type", "car")
        entities.setdefault("vehicle_confidence", 0.60)

        return event.model_copy(
            update={
                "entities": entities,
                "assumptions": assumptions,
                "issues": issues,
            }
        )


def _apply_model_default(
    entities: dict,
    assumptions: list[Assumption],
    issues: list[Issue],
    default: dict,
    explicit_fuel: str,
    typo_corrected: bool,
) -> None:
    default_fuel = str(default["fuel_type"])
    display_name = str(default["display_name"])

    entities["vehicle_type"] = default["vehicle_type"]
    entities["vehicle_size"] = default["vehicle_size"]
    entities["vehicle_default_code"] = default["assumption_code"]
    entities["vehicle_name"] = display_name

    if explicit_fuel and _is_strong_model_fuel_contradiction(display_name, explicit_fuel):
        entities["fuel_type"] = default_fuel
        entities["fuel_type_source"] = "model_default"
        entities["vehicle_confidence"] = 0.50
        assumptions.append(
            vehicle_model_default_assumption(
                str(default["assumption_code"]),
                display_name,
            )
        )
        issues.append(
            Issue(
                code="vehicle.fuel_type.contradiction",
                message=(
                    f"The journal mentions {explicit_fuel}, but {display_name} is mapped "
                    f"to {default_fuel}. Used the model default and lowered confidence."
                ),
                severity="warning",
            )
        )
        return

    if explicit_fuel:
        entities["fuel_type"] = explicit_fuel
        entities["fuel_type_source"] = "user"
        entities["vehicle_confidence"] = 0.85
        if explicit_fuel != default_fuel:
            assumptions.append(
                explicit_fuel_override_assumption(display_name, default_fuel, explicit_fuel)
            )
        return

    entities["fuel_type"] = default_fuel
    entities["fuel_type_source"] = "model_default"
    confidence = float(default["confidence"])
    if typo_corrected:
        confidence = max(0.0, confidence - 0.05)
    entities["vehicle_confidence"] = confidence
    assumptions.append(
        vehicle_model_default_assumption(
            str(default["assumption_code"]),
            display_name,
        )
    )


def _apply_generic_defaults(
    entities: dict,
    assumptions: list[Assumption],
    explicit_fuel: str,
) -> None:
    vehicle_size = _entity_text(entities.get("vehicle_size"))

    if explicit_fuel:
        entities["fuel_type"] = explicit_fuel
        entities["fuel_type_source"] = "user"
        if not vehicle_size:
            entities["vehicle_size"] = "medium"
            assumptions.append(generic_car_size_default_assumption())
            entities["vehicle_confidence"] = 0.88
        else:
            entities["vehicle_confidence"] = 0.90
        return

    entities["fuel_type"] = "petrol"
    entities["fuel_type_source"] = "generic_default"
    entities.setdefault("vehicle_size", "medium")
    assumptions.append(generic_car_default_assumption())
    entities["vehicle_confidence"] = 0.60


def _vehicle_default(make: str, model: str) -> dict | None:
    if not make:
        return None
    return VEHICLE_MODEL_DEFAULTS.get((make, model)) or VEHICLE_MODEL_DEFAULTS.get((make, ""))


def _is_strong_model_fuel_contradiction(display_name: str, explicit_fuel: str) -> bool:
    return display_name.lower().startswith("tesla") and explicit_fuel in {"diesel", "petrol"}


def _entity_text(value: object) -> str:
    if isinstance(value, str):
        return value.strip().lower()
    return ""
