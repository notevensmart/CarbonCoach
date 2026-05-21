from __future__ import annotations

from dataclasses import dataclass, field

from app.domain.assumptions import (
    SPACE_HEATER_DEFAULT_POWER_KW,
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


def _first_quantity(quantities: list[Quantity], dimension: str) -> Quantity | None:
    return next((quantity for quantity in quantities if quantity.dimension == dimension), None)


def _round_quantity(value: float) -> float:
    return round(float(value), 3)

