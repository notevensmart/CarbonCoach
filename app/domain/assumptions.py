from __future__ import annotations

from app.domain.models import Assumption


DEFAULT_REGION = "AU"
DEFAULT_ELECTRICITY_REGION = "AU"
SPACE_HEATER_DEFAULT_POWER_KW = 1.5
AU_ELECTRICITY_FALLBACK_KG_CO2E_PER_KWH = 0.6


def space_heater_default_power_assumption() -> Assumption:
    return Assumption(
        code="space_heater.default_power",
        message="Assumed heater power of 1.5 kW because wattage was not provided.",
        source="default",
        confidence_impact=-0.25,
    )


def default_au_electricity_region_assumption() -> Assumption:
    return Assumption(
        code="region.default_au_electricity",
        message="Assumed Australia electricity grid because no region was provided.",
        source="default",
        confidence_impact=-0.05,
    )

