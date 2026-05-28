from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from pydantic import ConfigDict, Field, model_validator

from app.domain.activity_taxonomy import ACTIVITY_TAXONOMY
from app.domain.material_ontology import (
    WASTE_DISPOSAL_METHOD_SYNONYMS,
    WASTE_MATERIAL_SYNONYMS,
)
from app.domain.models import ActivityType, Category, StrictBaseModel


DEFAULT_OVERLAY_PATH = (
    Path(__file__).resolve().parents[1] / "data" / "enriched_factor_metadata.jsonl"
)

SUPPORTED_CATEGORIES = {"transport", "energy", "goods_services", "waste"}
KNOWN_UNIT_TYPES = {
    "Distance",
    "Energy",
    "Money",
    "Number",
    "PassengerOverDistance",
    "Weight",
}
CONTROLLED_TRANSPORT_MODES = {
    "car_ride",
    "petrol_car",
    "diesel_car",
    "electric_car",
    "hybrid_car",
    "bus_ride",
    "train_ride",
    "rideshare",
    "flight",
    "walking",
    "cycling",
}
CONTROLLED_FUEL_TYPES = {
    "petrol",
    "diesel",
    "electric",
    "hybrid",
    "electricity",
    "natural_gas",
    "unknown",
}
CONTROLLED_VEHICLE_CLASSES = {
    "passenger_car",
    "small_car",
    "medium_car",
    "large_car",
    "suv",
    "bus",
    "coach",
    "train",
    "rail",
    "taxi",
    "aircraft",
}
CONTROLLED_ENERGY_END_USES = {
    "grid_electricity",
    "space_heating",
    "cooling",
    "hot_water",
    "cooking",
    "generic_device",
    "computer",
    "entertainment",
}
CONTROLLED_PRODUCT_CLASSES = {
    "coffee",
    "beef",
    "beef_burrito",
    "restaurant_meal",
    "takeaway_meal",
    "groceries",
    "clothing",
    "electronics",
    "generic_purchase",
    "soft_drink",
}
CONTROLLED_PURCHASE_CONTEXTS = {
    "serving",
    "item",
    "weight",
    "spend",
    "restaurant",
    "takeaway",
    "delivery_app",
    "grocery",
}
CONTROLLED_MATERIAL_CLASSES = set(WASTE_MATERIAL_SYNONYMS) | {
    "textiles",
    "electronics",
}
CONTROLLED_DISPOSAL_METHODS = set(WASTE_DISPOSAL_METHOD_SYNONYMS) | {"unknown"}
CONTROLLED_REGION_HINTS = {"AU", "US", "GB", "global"}
ACTIVITY_CATEGORY_BY_TYPE = {
    "car_ride": "transport",
    "bus_ride": "transport",
    "train_ride": "transport",
    "flight": "transport",
    "rideshare": "transport",
    "bicycle_ride": "transport",
    "walking": "transport",
    "generic_transport": "transport",
    "electricity_use": "energy",
    "space_heater_use": "energy",
    "generic_energy_use": "energy",
    "air_conditioner_use": "energy",
    "cooking_appliance_use": "energy",
    "hot_water_use": "energy",
    "natural_gas_use": "energy",
    "landfill_waste": "waste",
    "recycling": "waste",
    "composting": "waste",
    "clothing_purchase": "goods_services",
    "electronics_purchase": "goods_services",
    "food_purchase": "goods_services",
    "coffee_purchase": "goods_services",
    "restaurant_meal": "goods_services",
    "generic_purchase": "goods_services",
    "personal_activity": "goods_services",
}


class SemanticDimensions(StrictBaseModel):
    material_classes: list[str] = Field(default_factory=list)
    disposal_methods: list[str] = Field(default_factory=list)
    transport_modes: list[str] = Field(default_factory=list)
    fuel_types: list[str] = Field(default_factory=list)
    vehicle_classes: list[str] = Field(default_factory=list)
    energy_end_uses: list[str] = Field(default_factory=list)
    product_classes: list[str] = Field(default_factory=list)
    purchase_contexts: list[str] = Field(default_factory=list)
    region_hints: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_controlled_values(self) -> "SemanticDimensions":
        _validate_values("material_classes", self.material_classes, CONTROLLED_MATERIAL_CLASSES)
        _validate_values("disposal_methods", self.disposal_methods, CONTROLLED_DISPOSAL_METHODS)
        _validate_values("transport_modes", self.transport_modes, CONTROLLED_TRANSPORT_MODES)
        _validate_values("fuel_types", self.fuel_types, CONTROLLED_FUEL_TYPES)
        _validate_values("vehicle_classes", self.vehicle_classes, CONTROLLED_VEHICLE_CLASSES)
        _validate_values("energy_end_uses", self.energy_end_uses, CONTROLLED_ENERGY_END_USES)
        _validate_values("product_classes", self.product_classes, CONTROLLED_PRODUCT_CLASSES)
        _validate_values("purchase_contexts", self.purchase_contexts, CONTROLLED_PURCHASE_CONTEXTS)
        _validate_values("region_hints", self.region_hints, CONTROLLED_REGION_HINTS)
        return self


class EnrichedFactorMetadataRow(StrictBaseModel):
    activity_id: str | None = None
    pathway_key: str | None = None
    fallback_pathway_key: str | None = None
    local_fallback: bool = False
    description: str
    carboncoach_category: Category
    allowed_activity_types: list[ActivityType]
    unit_type: str
    preferred_terms: list[str]
    excluded_terms: list[str] = Field(default_factory=list)
    semantic_dimensions: SemanticDimensions = Field(default_factory=SemanticDimensions)
    calculation_boundary: str
    source_note: str
    source_urls: list[str] = Field(default_factory=list)
    source_quality_score: float = Field(..., ge=0.0, le=1.0)
    allow_duplicate_activity_id: bool = False

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_overlay_row(self) -> "EnrichedFactorMetadataRow":
        if self.carboncoach_category not in SUPPORTED_CATEGORIES:
            raise ValueError("carboncoach_category must be a supported V2 category")
        if self.unit_type not in KNOWN_UNIT_TYPES:
            raise ValueError(f"unknown unit_type: {self.unit_type}")
        if not (self.activity_id or self.pathway_key or self.fallback_pathway_key):
            raise ValueError("overlay row must have activity_id, pathway_key, or fallback_pathway_key")
        if not self.activity_id and not self.local_fallback:
            raise ValueError("pathway-key rows without activity_id must be marked local_fallback")
        if not self.allowed_activity_types:
            raise ValueError("allowed_activity_types must not be empty")
        if not _non_empty_strings(self.preferred_terms):
            raise ValueError("preferred_terms must contain non-empty strings")
        for field_name in ("description", "calculation_boundary", "source_note"):
            if not str(getattr(self, field_name)).strip():
                raise ValueError(f"{field_name} must not be empty")
        for activity_type in self.allowed_activity_types:
            taxonomy_category = ACTIVITY_TAXONOMY.get(activity_type, {}).get(
                "category"
            ) or ACTIVITY_CATEGORY_BY_TYPE.get(activity_type)
            if taxonomy_category != self.carboncoach_category:
                raise ValueError(
                    f"{activity_type} belongs to {taxonomy_category}, "
                    f"not {self.carboncoach_category}"
                )
        return self

    def pathway_identifier(self) -> str | None:
        return self.pathway_key or self.fallback_pathway_key

    def to_record_fields(self) -> dict[str, Any]:
        dimensions = self.semantic_dimensions.model_dump(exclude_defaults=True)
        fields: dict[str, Any] = {
            "enriched_description": self.description,
            "carboncoach_category": self.carboncoach_category,
            "allowed_activity_types": list(self.allowed_activity_types),
            "preferred_terms": list(self.preferred_terms),
            "excluded_terms": list(self.excluded_terms),
            "semantic_dimensions": dimensions,
            "calculation_boundary": self.calculation_boundary,
            "source_note": self.source_note,
            "source_urls": list(self.source_urls),
            "source_quality_score": self.source_quality_score,
        }
        pathway_identifier = self.pathway_identifier()
        if pathway_identifier:
            fields["carboncoach_pathway_key"] = pathway_identifier
        if self.local_fallback:
            fields["local_fallback"] = True
        return fields


@dataclass(frozen=True)
class EnrichedMetadataOverlay:
    by_activity_id: dict[str, EnrichedFactorMetadataRow]
    by_pathway_key: dict[str, EnrichedFactorMetadataRow]

    @classmethod
    def empty(cls) -> "EnrichedMetadataOverlay":
        return cls(by_activity_id={}, by_pathway_key={})

    @property
    def rows(self) -> list[EnrichedFactorMetadataRow]:
        by_identity = dict(self.by_pathway_key)
        for row in self.by_activity_id.values():
            key = row.pathway_identifier() or row.activity_id or ""
            by_identity[key] = row
        return list(by_identity.values())


def load_enriched_metadata_overlay(
    path: str | Path | None = None,
    *,
    required: bool = False,
) -> EnrichedMetadataOverlay:
    overlay_path = Path(path) if path is not None else DEFAULT_OVERLAY_PATH
    if not overlay_path.exists():
        if required:
            raise FileNotFoundError(f"Enriched factor metadata overlay not found: {overlay_path}")
        return EnrichedMetadataOverlay.empty()

    by_activity_id: dict[str, EnrichedFactorMetadataRow] = {}
    by_pathway_key: dict[str, EnrichedFactorMetadataRow] = {}
    with overlay_path.open(encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            if not line.strip():
                continue
            try:
                row = EnrichedFactorMetadataRow.model_validate(json.loads(line))
            except Exception as exc:
                raise ValueError(
                    f"Invalid enriched metadata overlay row at "
                    f"{overlay_path}:{line_number}: {exc}"
                ) from exc

            if row.activity_id:
                existing = by_activity_id.get(row.activity_id)
                if existing and not (
                    existing.allow_duplicate_activity_id and row.allow_duplicate_activity_id
                ):
                    raise ValueError(
                        f"Duplicate enriched metadata activity_id {row.activity_id!r} "
                        f"at {overlay_path}:{line_number}"
                    )
                by_activity_id[row.activity_id] = row
            pathway_identifier = row.pathway_identifier()
            if pathway_identifier:
                existing = by_pathway_key.get(pathway_identifier)
                if existing and existing is not row:
                    raise ValueError(
                        f"Duplicate enriched metadata pathway key {pathway_identifier!r} "
                        f"at {overlay_path}:{line_number}"
                    )
                by_pathway_key[pathway_identifier] = row

    return EnrichedMetadataOverlay(
        by_activity_id=by_activity_id,
        by_pathway_key=by_pathway_key,
    )


def merge_enriched_factor_metadata(
    raw_metadata: dict[str, dict],
    overlay: EnrichedMetadataOverlay | None = None,
    *,
    overlay_path: str | Path | None = None,
    required_overlay: bool = False,
) -> dict[str, dict]:
    selected_overlay = overlay or load_enriched_metadata_overlay(
        overlay_path,
        required=required_overlay,
    )
    merged = {activity_id: dict(record) for activity_id, record in raw_metadata.items()}

    for activity_id, row in selected_overlay.by_activity_id.items():
        if activity_id not in merged:
            continue
        merged[activity_id] = _merge_record(merged[activity_id], row)

    for pathway_key, row in selected_overlay.by_pathway_key.items():
        for activity_id, record in list(merged.items()):
            if activity_id == row.activity_id:
                continue
            record_key = (
                record.get("carboncoach_pathway_key")
                or record.get("pathway_key")
                or record.get("fallback_pathway_key")
            )
            if str(record_key or "") == pathway_key:
                merged[activity_id] = _merge_record(record, row)

    return merged


def _merge_record(record: dict, row: EnrichedFactorMetadataRow) -> dict:
    merged = dict(record)
    merged.update(row.to_record_fields())
    merged.setdefault("unit_type", row.unit_type)
    return merged


def _validate_values(field_name: str, values: list[str], allowed: set[str]) -> None:
    invalid = sorted({value for value in values if value not in allowed})
    if invalid:
        raise ValueError(f"{field_name} has unknown values: {', '.join(invalid)}")


def _non_empty_strings(values: list[str]) -> bool:
    return bool(values) and all(isinstance(value, str) and value.strip() for value in values)
