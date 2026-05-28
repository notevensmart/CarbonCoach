from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

from pydantic import Field, ValidationError

from app.domain.assumptions import DEFAULT_REGION
from app.domain.confidence import ConfidenceLevel
from app.domain.models import EstimateCoverage, EstimateTotal, ImpactComparison, StrictBaseModel


class ImpactComparisonDefinition(StrictBaseModel):
    key: str = Field(..., min_length=1)
    display_label: str = Field(..., min_length=1)
    reference_label: str = Field(..., min_length=1)
    kg_co2e_per_unit: float = Field(..., gt=0.0)
    unit: Literal["km"]
    applicable_regions: tuple[str, ...] = Field(..., min_length=1)
    applicability: str = Field(..., min_length=1)
    source_note: str = Field(..., min_length=1)
    display_eligibility_rule: Literal["positive_total_non_low_confidence"]
    eligible_confidence_levels: tuple[ConfidenceLevel, ...] = ("medium", "high")


DEFAULT_COMPARISON_KEY = "average_petrol_car_distance"

# This is contextual comparison metadata, not an estimation factor. It is kept
# separate from activity calculation so comparisons cannot change emissions.
IMPACT_COMPARISON_DEFINITIONS: dict[str, ImpactComparisonDefinition] = {
    DEFAULT_COMPARISON_KEY: ImpactComparisonDefinition(
        key=DEFAULT_COMPARISON_KEY,
        display_label="an average petrol car",
        reference_label="average petrol passenger car",
        kg_co2e_per_unit=0.192,
        unit="km",
        applicable_regions=("AU",),
        applicability=(
            "Australia; representative petrol passenger-car operational travel "
            "emissions only; excludes vehicle manufacture and avoided emissions."
        ),
        source_note=(
            "Maintained Australian approximate comparison reference: 0.192 kg "
            "CO2e/km for petrol passenger-car travel, aligned to the DCCEEW "
            "National Greenhouse Accounts Factors 2025 transport-fuel boundary."
        ),
        display_eligibility_rule="positive_total_non_low_confidence",
    )
}


def build_impact_comparison(
    total: EstimateTotal,
    *,
    coverage: EstimateCoverage | None = None,
    region: str = DEFAULT_REGION,
    key: str = DEFAULT_COMPARISON_KEY,
    definitions: Mapping[str, ImpactComparisonDefinition | dict] | None = None,
) -> ImpactComparison | None:
    records = definitions if definitions is not None else IMPACT_COMPARISON_DEFINITIONS
    raw_definition = records.get(key)
    if raw_definition is None:
        return None
    try:
        definition = (
            raw_definition
            if isinstance(raw_definition, ImpactComparisonDefinition)
            else ImpactComparisonDefinition.model_validate(raw_definition)
        )
    except (TypeError, ValidationError):
        return None

    if (
        definition.key != key
        or total.co2e <= 0
        or total.confidence.level not in definition.eligible_confidence_levels
        or region not in definition.applicable_regions
        or (coverage is not None and coverage.estimate_is_partial)
    ):
        return None

    amount = _display_amount(total.co2e / definition.kg_co2e_per_unit)
    if amount <= 0:
        return None

    return ImpactComparison(
        key=definition.key,
        message=(
            f"Roughly equivalent to driving {definition.display_label} "
            f"for {amount:g} {definition.unit}."
        ),
        amount=amount,
        unit=definition.unit,
        reference_label=definition.reference_label,
        kg_co2e_per_unit=definition.kg_co2e_per_unit,
        input_total_kg_co2e=total.co2e,
        applicability=definition.applicability,
        source_note=definition.source_note,
    )


def _display_amount(amount: float) -> float:
    if amount >= 10:
        return float(round(amount))
    if amount >= 1:
        return round(amount, 1)
    return round(amount, 2)
