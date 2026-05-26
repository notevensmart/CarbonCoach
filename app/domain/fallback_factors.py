from __future__ import annotations

from dataclasses import dataclass

from app.domain.models import Assumption


@dataclass(frozen=True)
class FallbackFactor:
    """Maintained local coefficient used only when Climatiq cannot estimate."""

    key: str
    name: str
    category: str
    dimension: str
    amount_parameter: str
    unit_parameter: str
    unit: str
    kg_co2e_per_unit: float
    confidence: float
    source_reference: str

    def assumption(self) -> Assumption:
        return Assumption(
            code=f"fallback_factor.{self.key}",
            message=(
                f"Used local fallback factor {self.name} "
                f"({self.kg_co2e_per_unit:g} kg CO2e/{self.unit}) because "
                "no successful compatible Climatiq estimate was available."
            ),
            source="fallback",
            confidence_impact=-0.25,
        )


# These bootstrap coefficients retain the existing local fallback boundary from
# V1 while V2 makes its use visible. They are generic estimates, not model-level
# or route-specific accounting factors.
LOCAL_FALLBACK_FACTORS = {
    "energy.au_electricity": FallbackFactor(
        key="energy.au_electricity",
        name="generic electricity energy",
        category="energy",
        dimension="energy",
        amount_parameter="energy",
        unit_parameter="energy_unit",
        unit="kWh",
        kg_co2e_per_unit=0.4,
        confidence=0.55,
        source_reference="Existing CarbonCoach V1 local energy fallback coefficient.",
    ),
    "transport.road_distance": FallbackFactor(
        key="transport.road_distance",
        name="generic road transport distance",
        category="transport",
        dimension="distance",
        amount_parameter="distance",
        unit_parameter="distance_unit",
        unit="km",
        kg_co2e_per_unit=0.18,
        confidence=0.50,
        source_reference="Existing CarbonCoach V1 local transport distance coefficient.",
    ),
    "transport.public_passenger_distance": FallbackFactor(
        key="transport.public_passenger_distance",
        name="generic passenger transport distance",
        category="transport",
        dimension="distance",
        amount_parameter="distance",
        unit_parameter="distance_unit",
        unit="km",
        kg_co2e_per_unit=0.09,
        confidence=0.50,
        source_reference="Existing CarbonCoach V1 local passenger-distance coefficient.",
    ),
}
