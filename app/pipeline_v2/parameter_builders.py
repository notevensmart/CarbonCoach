from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.domain.activity_taxonomy import TRANSPORT_TAXONOMY
from app.domain.assumptions import (
    SPACE_HEATER_DEFAULT_POWER_KW,
    distance_compact_k_context_assumption,
    default_au_electricity_region_assumption,
    flight_default_factor_assumption,
    space_heater_default_power_assumption,
)
from app.domain.models import Assumption, CarbonEvent, Confidence, EstimateStatus, Issue, Quantity


@dataclass(frozen=True)
class ParameterBuildResult:
    parameters: dict
    confidence: Confidence
    assumptions: list[Assumption] = field(default_factory=list)
    issues: list[Issue] = field(default_factory=list)
    can_estimate: bool = True
    status: EstimateStatus | None = None


class EnergyParameterBuilder:
    def build(self, event: CarbonEvent) -> ParameterBuildResult:
        energy = _first_quantity(event.quantities, "energy")
        power = _first_quantity(event.quantities, "power")
        duration = _first_quantity(event.quantities, "duration")
        assumptions = [default_au_electricity_region_assumption()]

        if (
            event.activity_type == "space_heater_use"
            and event.entities.get("power_source") == "natural_gas"
        ):
            parameters = {}
            if duration is not None:
                parameters = {
                    "duration": _round_quantity(duration.value),
                    "duration_unit": "hours",
                    "power_source": "natural_gas",
                }
            return ParameterBuildResult(
                parameters=parameters,
                confidence=Confidence.from_score(0.35),
                assumptions=[],
                issues=[
                    Issue(
                        code="energy.natural_gas_heater.unsupported_factor",
                        message=(
                            "Detected a gas heater, but no validated natural-gas "
                            "heater factor pathway is configured in V2 yet."
                        ),
                        severity="warning",
                    )
                ],
                can_estimate=False,
            )

        if energy is not None:
            return ParameterBuildResult(
                parameters={
                    "energy": _round_quantity(energy.value),
                    "energy_unit": "kWh",
                },
                confidence=Confidence.from_score(0.95),
                assumptions=assumptions,
            )

        if power is not None and duration is not None:
            energy_kwh = power.value * duration.value
            return ParameterBuildResult(
                parameters={
                    "energy": _round_quantity(energy_kwh),
                    "energy_unit": "kWh",
                    "power": _round_quantity(power.value),
                    "power_unit": "kW",
                    "duration": _round_quantity(duration.value),
                    "duration_unit": "hours",
                },
                confidence=Confidence.from_score(0.90),
                assumptions=assumptions,
            )

        if event.activity_type == "space_heater_use" and duration is not None:
            power_kw = SPACE_HEATER_DEFAULT_POWER_KW
            energy_kwh = power_kw * duration.value
            return ParameterBuildResult(
                parameters={
                    "energy": _round_quantity(energy_kwh),
                    "energy_unit": "kWh",
                    "power": power_kw,
                    "power_unit": "kW",
                    "duration": _round_quantity(duration.value),
                    "duration_unit": "hours",
                },
                confidence=Confidence.from_score(0.60),
                assumptions=[
                    space_heater_default_power_assumption(),
                    *assumptions,
                ],
            )

        if duration is not None:
            return ParameterBuildResult(
                parameters={
                    "duration": _round_quantity(duration.value),
                    "duration_unit": "hours",
                },
                confidence=Confidence.from_score(0.30),
                assumptions=[],
                issues=[
                    Issue(
                        code="energy.appliance.default_power_unavailable",
                        message=(
                            "Detected appliance usage duration, but no validated "
                            "default-power conversion is configured for this appliance."
                        ),
                        severity="warning",
                    )
                ],
                can_estimate=False,
            )

        return ParameterBuildResult(
            parameters={},
            confidence=Confidence.from_score(0.25),
            assumptions=assumptions,
            issues=[
                Issue(
                    code="energy.missing_quantity",
                    message="Could not find an energy amount, duration, or power needed for this energy estimate.",
                    severity="warning",
                )
            ],
            can_estimate=False,
        )


class TransportParameterBuilder:
    def build(self, event: CarbonEvent) -> ParameterBuildResult:
        distance = _first_quantity(event.quantities, "distance")
        if distance is None:
            return ParameterBuildResult(
                parameters={},
                confidence=Confidence.from_score(0.25),
                issues=[
                    Issue(
                        code="transport.missing_distance",
                        message="Could not find a distance needed for this transport estimate.",
                        severity="warning",
                    )
                ],
                can_estimate=False,
            )

        metadata = TRANSPORT_TAXONOMY[event.activity_type]
        policy = str(metadata.get("estimate_policy", "unresolved"))
        assumptions = []
        if _is_compact_k_distance(distance):
            assumptions.append(distance_compact_k_context_assumption(distance.surface or "k"))
        parameters = {
            "distance": _round_quantity(distance.value),
            "distance_unit": "km",
            "transport_mode": event.activity_type,
        }
        _add_declared_transport_traits(parameters, event, metadata)
        if event.activity_type == "flight":
            _add_flight_factor_defaults(parameters, event, distance, assumptions)

        if policy == "operational_zero":
            parameters["emissions_boundary"] = metadata["emissions_boundary"]
            return ParameterBuildResult(
                parameters=parameters,
                confidence=Confidence.from_score(_distance_confidence(event, distance)),
                assumptions=assumptions,
                status="not_estimated",
            )

        if policy == "unresolved":
            issue_code = (
                "transport.flight.factor_unresolved"
                if event.activity_type == "flight"
                else "transport.mode.unsupported"
            )
            return ParameterBuildResult(
                parameters=parameters,
                confidence=Confidence.from_score(0.30),
                assumptions=assumptions,
                issues=[
                    Issue(
                        code=issue_code,
                        message=(
                            f"Detected {event.activity_type}, but no approved Climatiq "
                            "factor pathway is configured for this mode yet."
                        ),
                        severity="warning",
                    )
                ],
                can_estimate=False,
            )

        if policy == "climatiq_distance":
            return ParameterBuildResult(
                parameters=parameters,
                confidence=Confidence.from_score(
                    0.60
                    if event.activity_type == "flight"
                    else _distance_confidence(event, distance)
                ),
                assumptions=assumptions,
            )

        vehicle_type = _entity_text(event.entities.get("vehicle_type")) or "car"
        vehicle_size = _entity_text(event.entities.get("vehicle_size")) or "medium"
        fuel_type = _entity_text(event.entities.get("fuel_type")) or "petrol"

        parameters.update({
            "vehicle_type": vehicle_type,
            "vehicle_size": vehicle_size,
            "fuel_type": fuel_type,
        })
        if event.entities.get("vehicle_make"):
            parameters["vehicle_make"] = event.entities["vehicle_make"]
        if event.entities.get("vehicle_model"):
            parameters["vehicle_model"] = event.entities["vehicle_model"]
        if event.entities.get("vehicle_class"):
            parameters["vehicle_class"] = event.entities["vehicle_class"]
        if event.entities.get("vehicle_description"):
            parameters["vehicle_description"] = event.entities["vehicle_description"]
        if event.entities.get("vehicle_metadata_record_id"):
            parameters["vehicle_metadata_record_id"] = event.entities["vehicle_metadata_record_id"]
        if event.entities.get("vehicle_metadata_source"):
            parameters["vehicle_metadata_source"] = event.entities["vehicle_metadata_source"]
        if event.entities.get("vehicle_year"):
            parameters["vehicle_year"] = event.entities["vehicle_year"]

        return ParameterBuildResult(
            parameters=parameters,
            confidence=Confidence.from_score(_transport_confidence(event, distance)),
            assumptions=assumptions,
        )


def _first_quantity(quantities: list[Quantity], dimension: str) -> Quantity | None:
    return next((quantity for quantity in quantities if quantity.dimension == dimension), None)


def _round_quantity(value: float) -> float:
    return round(float(value), 3)


def _transport_confidence(event: CarbonEvent, distance: Quantity) -> float:
    score = min(
        event.confidence.score,
        distance.confidence,
        float(event.entities.get("vehicle_confidence") or 0.60),
    )
    if event.entities.get("vehicle_typo_corrected"):
        score -= 0.03
    if any(issue.code == "vehicle.fuel_type.contradiction" for issue in event.issues):
        score = min(score, 0.50)
    return score


def _distance_confidence(event: CarbonEvent, distance: Quantity) -> float:
    return min(event.confidence.score, distance.confidence)


def _is_compact_k_distance(quantity: Quantity) -> bool:
    return bool(quantity.surface and re.match(r"^\d+(?:\.\d+)?\s*k$", quantity.surface, re.I))


def _entity_text(value: object) -> str:
    if isinstance(value, str):
        return value.strip().lower()
    return ""


def _add_declared_transport_traits(parameters: dict, event: CarbonEvent, metadata: dict) -> None:
    for field in metadata.get("factor_trait_fields", ()):
        value = _entity_text(event.entities.get(str(field)))
        if value:
            parameters[str(field)] = value


def _add_flight_factor_defaults(
    parameters: dict,
    event: CarbonEvent,
    distance: Quantity,
    assumptions: list[Assumption],
) -> None:
    route_type = _entity_text(event.entities.get("route_type"))
    passenger_class = _entity_text(event.entities.get("passenger_class"))
    parameters["route_type"] = route_type or "domestic"
    parameters["passenger_class"] = passenger_class or "average"
    parameters["rf_effect"] = "included"
    parameters["distance_band"] = (
        "short_haul" if float(distance.value) < 3700 else "long_haul"
    )
    assumptions.append(
        flight_default_factor_assumption(
            assumed_route=not bool(route_type),
            assumed_passenger_class=not bool(passenger_class),
        )
    )
