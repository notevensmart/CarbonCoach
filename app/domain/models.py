from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.confidence import ConfidenceLevel, clamp_score, confidence_level


Category = Literal["transport", "energy", "waste", "goods_services"]
QuantityDimension = Literal[
    "distance",
    "energy",
    "power",
    "duration",
    "weight",
    "money",
    "number",
    "volume",
    "area",
]
ActivityType = Literal[
    "car_ride",
    "bus_ride",
    "train_ride",
    "flight",
    "rideshare",
    "bicycle_ride",
    "walking",
    "generic_transport",
    "electricity_use",
    "space_heater_use",
    "generic_energy_use",
    "air_conditioner_use",
    "cooking_appliance_use",
    "hot_water_use",
    "natural_gas_use",
    "landfill_waste",
    "recycling",
    "composting",
    "clothing_purchase",
    "electronics_purchase",
    "food_purchase",
    "coffee_purchase",
    "restaurant_meal",
    "generic_purchase",
    "personal_activity",
]
EstimateStatus = Literal[
    "estimated",
    "fallback_estimated",
    "not_estimated",
    "unresolved",
    "failed",
]
EstimateSource = Literal["climatiq", "fallback", "none", "unresolved"]
AssumptionSource = Literal["default", "inference", "user", "fallback", "system"]
IssueSeverity = Literal["info", "warning", "error"]


class StrictBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Confidence(StrictBaseModel):
    score: float = Field(..., ge=0.0, le=1.0)
    level: ConfidenceLevel | None = None

    @classmethod
    def from_score(cls, score: float) -> "Confidence":
        rounded = round(clamp_score(score), 2)
        return cls(score=rounded, level=confidence_level(rounded))

    @model_validator(mode="after")
    def fill_or_validate_level(self) -> "Confidence":
        expected = confidence_level(self.score)
        if self.level is None:
            self.level = expected
            return self
        if self.level != expected:
            raise ValueError("confidence level must match score thresholds")
        return self


class Assumption(StrictBaseModel):
    code: str
    message: str
    source: AssumptionSource
    confidence_impact: float


class Issue(StrictBaseModel):
    code: str
    message: str
    severity: IssueSeverity = "warning"


class PreprocessingCorrection(StrictBaseModel):
    from_text: str = Field(alias="from")
    to: str
    type: str
    confidence: float = Field(..., ge=0.0, le=1.0)

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class PreprocessedJournal(StrictBaseModel):
    raw_journal: str
    cleaned_journal: str
    corrections: list[PreprocessingCorrection] = Field(default_factory=list)


class Quantity(StrictBaseModel):
    value: float
    unit: str
    dimension: QuantityDimension
    surface: str | None = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class CarbonEvent(StrictBaseModel):
    raw_text: str
    category: Category
    activity_type: ActivityType
    quantities: list[Quantity] = Field(default_factory=list)
    entities: dict[str, str | float | int | bool | None] = Field(default_factory=dict)
    assumptions: list[Assumption] = Field(default_factory=list)
    issues: list[Issue] = Field(default_factory=list)
    confidence: Confidence = Field(default_factory=lambda: Confidence.from_score(0.0))


class FactorCandidate(StrictBaseModel):
    activity_id: str
    name: str
    sector: str | None = None
    category: str | None = None
    unit_type: str
    score: float = Field(..., ge=0.0, le=1.0)
    match_reasons: list[str] = Field(default_factory=list)
    specificity_match: bool = False


class EstimateDetail(StrictBaseModel):
    raw_text: str
    category: Category
    activity_type: ActivityType
    status: EstimateStatus
    parameters: dict[str, Any] = Field(default_factory=dict)
    co2e: float | None = None
    unit: str = "kg"
    source: EstimateSource = "none"
    confidence: Confidence
    parameter_confidence: Confidence | None = None
    factor_confidence: Confidence | None = None
    source_confidence: Confidence | None = None
    assumptions: list[Assumption] = Field(default_factory=list)
    issues: list[Issue] = Field(default_factory=list)
    factor: FactorCandidate | None = None


class SourceBreakdown(StrictBaseModel):
    estimated: float = 0.0
    fallback_estimated: float = 0.0
    not_estimated: float = 0.0


class EstimateTotal(StrictBaseModel):
    co2e: float
    unit: str = "kg"
    confidence: Confidence
    source_breakdown: SourceBreakdown


class CarbonEstimateResponse(StrictBaseModel):
    version: Literal["v2"] = "v2"
    total: EstimateTotal
    details: list[EstimateDetail] = Field(default_factory=list)
