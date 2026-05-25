from __future__ import annotations

from app.domain.assumptions import (
    explicit_fuel_override_assumption,
    generic_car_default_assumption,
    generic_car_size_default_assumption,
    named_vehicle_default_assumption,
    named_vehicle_size_default_assumption,
    vehicle_model_default_assumption,
)
from app.domain.models import Assumption, CarbonEvent, Issue
from app.domain.vehicle_metadata import (
    LocalVehicleMetadataProvider,
    VehicleLookupResult,
    VehicleMetadataProvider,
    VehicleMetadataQuery,
    VehicleMetadataRecord,
)


class EntityEnricher:
    def __init__(self, vehicle_metadata_provider: VehicleMetadataProvider | None = None) -> None:
        self.vehicle_metadata_provider = (
            vehicle_metadata_provider or LocalVehicleMetadataProvider()
        )

    def enrich(self, event: CarbonEvent) -> CarbonEvent:
        if event.category != "transport" or event.activity_type not in {"car_ride", "rideshare"}:
            return event
        return self._enrich_road_vehicle(event)

    def _enrich_road_vehicle(self, event: CarbonEvent) -> CarbonEvent:
        entities = dict(event.entities)
        assumptions = list(event.assumptions)
        issues = list(event.issues)
        explicit_fuel = _entity_text(entities.get("explicit_fuel_type"))
        vehicle_description = _entity_display_text(entities.get("vehicle_description"))
        lookup_result = self._lookup_vehicle(
            vehicle_description,
            _entity_int(entities.get("vehicle_year")),
            issues,
        )

        if lookup_result.record is not None:
            _apply_metadata_record(
                entities=entities,
                assumptions=assumptions,
                issues=issues,
                record=lookup_result.record,
                explicit_fuel=explicit_fuel,
                typo_corrected=bool(entities.get("vehicle_typo_corrected")),
            )
        else:
            _apply_generic_defaults(
                entities,
                assumptions,
                explicit_fuel,
                vehicle_description,
            )
            if vehicle_description and lookup_result.status == "not_found":
                issues.append(
                    Issue(
                        code="vehicle.named_model.unmapped",
                        message=(
                            f"Recognized {vehicle_description}, but no verified vehicle "
                            "mapping is available. Used only explicit class/fuel details "
                            "and visible defaults."
                        ),
                        severity="info",
                    )
                )
            if vehicle_description and lookup_result.status == "ambiguous":
                issues.append(
                    Issue(
                        code="vehicle.metadata.ambiguous",
                        message=(
                            f"Multiple vehicle metadata records match {vehicle_description}; "
                            "used only explicit traits and visible defaults."
                        ),
                        severity="warning",
                    )
                )

        entities.setdefault("vehicle_type", "car")
        entities.setdefault("vehicle_confidence", 0.60)
        return event.model_copy(
            update={
                "entities": entities,
                "assumptions": assumptions,
                "issues": issues,
            }
        )

    def _lookup_vehicle(
        self,
        vehicle_description: str,
        vehicle_year: int | None,
        issues: list[Issue],
    ) -> VehicleLookupResult:
        if not vehicle_description:
            return VehicleLookupResult(status="not_found")
        try:
            return self.vehicle_metadata_provider.lookup(
                VehicleMetadataQuery(
                    vehicle_description=vehicle_description,
                    year=vehicle_year,
                )
            )
        except Exception:
            issues.append(
                Issue(
                    code="vehicle.metadata.unavailable",
                    message=(
                        "Vehicle metadata lookup was unavailable; used explicit traits "
                        "and visible defaults."
                    ),
                    severity="warning",
                )
            )
            return VehicleLookupResult(status="ambiguous")


def _apply_metadata_record(
    entities: dict,
    assumptions: list[Assumption],
    issues: list[Issue],
    record: VehicleMetadataRecord,
    explicit_fuel: str,
    typo_corrected: bool,
) -> None:
    entities["vehicle_type"] = record.vehicle_type
    entities.setdefault("vehicle_size", record.vehicle_size)
    entities["vehicle_make"] = record.vehicle_make
    entities["vehicle_model"] = record.vehicle_model
    entities["vehicle_name"] = record.display_name
    entities["vehicle_metadata_record_id"] = record.record_id
    entities["vehicle_metadata_source"] = record.metadata_source
    if record.year is not None:
        entities.setdefault("vehicle_year", record.year)
    default_fuel = record.fuel_type or ""

    if explicit_fuel and _is_fixed_fuel_contradiction(record, explicit_fuel):
        entities["fuel_type"] = default_fuel
        entities["fuel_type_source"] = "vehicle_metadata"
        entities["vehicle_confidence"] = 0.50
        assumptions.append(
            vehicle_model_default_assumption(record.assumption_code, record.display_name)
        )
        issues.append(
            Issue(
                code="vehicle.fuel_type.contradiction",
                message=(
                    f"The journal mentions {explicit_fuel}, but {record.display_name} is "
                    f"verified as {default_fuel}. Used verified metadata and lowered confidence."
                ),
                severity="warning",
            )
        )
        return

    if explicit_fuel:
        entities["fuel_type"] = explicit_fuel
        entities["fuel_type_source"] = "user"
        entities["vehicle_confidence"] = 0.85
        if default_fuel and explicit_fuel != default_fuel:
            assumptions.append(
                explicit_fuel_override_assumption(
                    record.display_name,
                    default_fuel,
                    explicit_fuel,
                )
            )
        return

    if default_fuel:
        entities["fuel_type"] = default_fuel
        entities["fuel_type_source"] = "vehicle_metadata"
        confidence = record.confidence - (0.05 if typo_corrected else 0.0)
        entities["vehicle_confidence"] = max(0.0, confidence)
        assumptions.append(
            vehicle_model_default_assumption(record.assumption_code, record.display_name)
        )
        return

    _apply_generic_defaults(
        entities,
        assumptions,
        explicit_fuel="",
        vehicle_description=record.display_name,
    )


def _apply_generic_defaults(
    entities: dict,
    assumptions: list[Assumption],
    explicit_fuel: str,
    vehicle_description: str,
) -> None:
    vehicle_size = _entity_text(entities.get("vehicle_size"))
    if explicit_fuel:
        entities["fuel_type"] = explicit_fuel
        entities["fuel_type_source"] = "user"
        if not vehicle_size:
            entities["vehicle_size"] = "medium"
            assumptions.append(
                named_vehicle_size_default_assumption(vehicle_description)
                if vehicle_description
                else generic_car_size_default_assumption()
            )
            entities["vehicle_confidence"] = 0.88
        else:
            entities["vehicle_confidence"] = 0.90
        return

    entities["fuel_type"] = "petrol"
    entities["fuel_type_source"] = "generic_default"
    if vehicle_description:
        if vehicle_size:
            assumptions.append(named_vehicle_default_assumption(vehicle_description, vehicle_size))
        else:
            entities["vehicle_size"] = "medium"
            assumptions.append(named_vehicle_default_assumption(vehicle_description))
    else:
        entities.setdefault("vehicle_size", "medium")
        assumptions.append(generic_car_default_assumption())
    entities["vehicle_confidence"] = 0.60


def _is_fixed_fuel_contradiction(record: VehicleMetadataRecord, explicit_fuel: str) -> bool:
    return (
        record.fuel_certainty == "fixed"
        and record.fuel_type == "electric"
        and explicit_fuel in {"diesel", "petrol"}
    )


def _entity_text(value: object) -> str:
    if isinstance(value, str):
        return value.strip().lower()
    return ""


def _entity_display_text(value: object) -> str:
    if isinstance(value, str):
        return value.strip()
    return ""


def _entity_int(value: object) -> int | None:
    if isinstance(value, int):
        return value
    return None
