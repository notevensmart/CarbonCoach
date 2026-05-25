from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.domain.assumptions import (
    SPACE_HEATER_DEFAULT_POWER_KW,
    TRANSPORT_FALLBACK_KG_CO2E_PER_KM,
    distance_compact_k_context_assumption,
    default_au_electricity_region_assumption,
    space_heater_default_power_assumption,
)
from app.domain.models import Assumption, CarbonEvent, Confidence, Issue, Quantity


@dataclass(frozen=True)
class ParameterBuildResult:
    parameters: dict
    confidence: Confidence
    assumptions: list[Assumption] = field(default_factory=list)
    issues: list[Issue] = field(default_factory=list)
    can_estimate: bool = True
    fallback_factor: float | None = None


class EnergyParameterBuilder:
    def build(self, event: CarbonEvent) -> ParameterBuildResult:
        energy = _first_quantity(event.quantities, "energy")
        power = _first_quantity(event.quantities, "power")
        duration = _first_quantity(event.quantities, "duration")
        assumptions = [default_au_electricity_region_assumption()]

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
        if event.activity_type != "car_ride":
            return _unsupported_transport_build(event)

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

        vehicle_type = _entity_text(event.entities.get("vehicle_type")) or "car"
        vehicle_size = _entity_text(event.entities.get("vehicle_size")) or "medium"
        fuel_type = _entity_text(event.entities.get("fuel_type")) or "petrol"
        factor = _transport_factor(vehicle_type, vehicle_size, fuel_type)

        assumptions = []
        if _is_compact_k_distance(distance):
            assumptions.append(distance_compact_k_context_assumption(distance.surface or "k"))

        parameters = {
            "distance": _round_quantity(distance.value),
            "distance_unit": "km",
            "vehicle_type": vehicle_type,
            "vehicle_size": vehicle_size,
            "fuel_type": fuel_type,
        }
        if event.entities.get("vehicle_make"):
            parameters["vehicle_make"] = event.entities["vehicle_make"]
        if event.entities.get("vehicle_model"):
            parameters["vehicle_model"] = event.entities["vehicle_model"]
        if event.entities.get("vehicle_class"):
            parameters["vehicle_class"] = event.entities["vehicle_class"]

        return ParameterBuildResult(
            parameters=parameters,
            confidence=Confidence.from_score(_transport_confidence(event, distance)),
            assumptions=assumptions,
            fallback_factor=factor,
        )


def _first_quantity(quantities: list[Quantity], dimension: str) -> Quantity | None:
    return next((quantity for quantity in quantities if quantity.dimension == dimension), None)


def _round_quantity(value: float) -> float:
    return round(float(value), 3)


def _unsupported_transport_build(event: CarbonEvent) -> ParameterBuildResult:
    return ParameterBuildResult(
        parameters={},
        confidence=Confidence.from_score(0.20),
        issues=[
            Issue(
                code="transport.not_implemented",
                message=(
                    f"Detected {event.activity_type}, but this transport type is not estimated yet."
                ),
                severity="warning",
            )
        ],
        can_estimate=False,
    )


def _transport_factor(vehicle_type: str, vehicle_size: str, fuel_type: str) -> float:
    return TRANSPORT_FALLBACK_KG_CO2E_PER_KM.get(
        (vehicle_type, vehicle_size, fuel_type),
        TRANSPORT_FALLBACK_KG_CO2E_PER_KM[("car", "medium", "petrol")],
    )


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


def _is_compact_k_distance(quantity: Quantity) -> bool:
    return bool(quantity.surface and re.match(r"^\d+(?:\.\d+)?\s*k$", quantity.surface, re.I))


def _entity_text(value: object) -> str:
    if isinstance(value, str):
        return value.strip().lower()
    return ""
