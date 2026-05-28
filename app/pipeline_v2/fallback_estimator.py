from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Mapping

from app.domain.activity_taxonomy import ACTIVITY_TAXONOMY
from app.domain.fallback_factors import FallbackFactor, LOCAL_FALLBACK_FACTORS
from app.domain.models import Assumption, CarbonEvent
from app.domain.assumptions import generic_waste_fallback_assumption


@dataclass(frozen=True)
class FallbackEstimateResult:
    co2e: float
    co2e_unit: str
    confidence: float
    assumptions: list[Assumption]


class LocalFallbackEstimator:
    """Estimates only through taxonomy-declared, unit-compatible local factors."""

    def __init__(
        self,
        factor_catalog: Mapping[str, FallbackFactor] | None = None,
    ) -> None:
        self.factor_catalog = (
            factor_catalog if factor_catalog is not None else LOCAL_FALLBACK_FACTORS
        )

    def estimate(
        self,
        event: CarbonEvent,
        parameters: dict,
    ) -> FallbackEstimateResult | None:
        taxonomy = ACTIVITY_TAXONOMY.get(event.activity_type, {})
        factor_key = parameters.get("fallback_factor_key") or taxonomy.get("fallback_factor_key")
        if factor_key not in _declared_fallback_keys(taxonomy):
            return None
        factor = self.factor_catalog.get(str(factor_key)) if factor_key else None
        if factor is None or not _compatible(event, parameters, factor):
            return None

        amount = parameters.get(factor.amount_parameter)
        if not isinstance(amount, (int, float)) or amount < 0:
            return None
        return FallbackEstimateResult(
            co2e=round(float(amount) * factor.kg_co2e_per_unit, 3),
            co2e_unit="kg",
            confidence=factor.confidence,
            assumptions=[*_generic_fallback_assumptions(event, parameters, factor), factor.assumption()],
        )


def _compatible(event: CarbonEvent, parameters: dict, factor: FallbackFactor) -> bool:
    return (
        factor.category == event.category
        and factor.dimension in parameters
        and _normalized_unit(parameters.get(factor.unit_parameter))
        == _normalized_unit(factor.unit)
    )


def _normalized_unit(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def _declared_fallback_keys(taxonomy: dict) -> set[str]:
    keys = {str(taxonomy["fallback_factor_key"])} if taxonomy.get("fallback_factor_key") else set()
    keys.update(
        str(pathway["fallback_factor_key"])
        for pathway in taxonomy.get("pathways", {}).values()
        if pathway.get("fallback_factor_key")
    )
    return keys


def _generic_fallback_assumptions(
    event: CarbonEvent,
    parameters: dict,
    factor: FallbackFactor,
) -> list[Assumption]:
    material_class = str(parameters.get("material_class") or "")
    disposal_method = str(parameters.get("disposal_method") or "")
    if (
        event.category == "waste"
        and factor.key == "waste.landfill_general"
        and disposal_method == "landfill"
        and material_class not in {"", "general_waste", "mixed_packaging"}
    ):
        return [generic_waste_fallback_assumption(material_class, disposal_method)]
    return []
