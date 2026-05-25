from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal, Protocol, Sequence


FuelCertainty = Literal["fixed", "default", "unknown"]
LookupStatus = Literal["matched", "ambiguous", "not_found"]


@dataclass(frozen=True)
class VehicleMetadataQuery:
    vehicle_description: str
    year: int | None = None


@dataclass(frozen=True)
class VehicleMetadataRecord:
    record_id: str
    display_name: str
    aliases: tuple[str, ...]
    vehicle_make: str
    vehicle_model: str
    year: int | None = None
    vehicle_type: str = "car"
    vehicle_size: str | None = None
    fuel_type: str | None = None
    fuel_certainty: FuelCertainty = "unknown"
    confidence: float = 0.65
    assumption_code: str = "vehicle.metadata.default"
    metadata_source: str = "local_verified_cache"
    source_reference: str = ""


@dataclass(frozen=True)
class VehicleLookupResult:
    status: LookupStatus
    record: VehicleMetadataRecord | None = None
    candidate_record_ids: tuple[str, ...] = ()


class VehicleMetadataProvider(Protocol):
    def lookup(self, query: VehicleMetadataQuery) -> VehicleLookupResult:
        """Return only records that resolve the supplied description unambiguously."""


LOCAL_VERIFIED_VEHICLE_RECORDS = (
    VehicleMetadataRecord(
        record_id="local.toyota.camry.default",
        display_name="Toyota Camry",
        aliases=("toyota camry",),
        vehicle_make="toyota",
        vehicle_model="camry",
        vehicle_size="medium",
        fuel_type="petrol",
        fuel_certainty="default",
        confidence=0.65,
        assumption_code="vehicle.toyota_camry.default_petrol_medium",
        source_reference="Existing CarbonCoach reviewed bootstrap default.",
    ),
    VehicleMetadataRecord(
        record_id="local.tesla.model_3.bev",
        display_name="Tesla Model 3",
        aliases=("tesla model 3", "tesla model3"),
        vehicle_make="tesla",
        vehicle_model="model 3",
        vehicle_size="medium",
        fuel_type="electric",
        fuel_certainty="fixed",
        confidence=0.85,
        assumption_code="vehicle.tesla_model_3.default_electric",
        source_reference="Existing CarbonCoach reviewed bootstrap BEV mapping.",
    ),
    VehicleMetadataRecord(
        record_id="local.tesla.bev",
        display_name="Tesla",
        aliases=("tesla",),
        vehicle_make="tesla",
        vehicle_model="",
        vehicle_size="medium",
        fuel_type="electric",
        fuel_certainty="fixed",
        confidence=0.80,
        assumption_code="vehicle.tesla.default_electric",
        source_reference="Existing CarbonCoach reviewed all-electric manufacturer mapping.",
    ),
)


class CachedVehicleMetadataProvider:
    """Deterministic provider backed by vetted records supplied at construction time."""

    def __init__(self, records: Sequence[VehicleMetadataRecord]) -> None:
        self._records = tuple(records)

    def lookup(self, query: VehicleMetadataQuery) -> VehicleLookupResult:
        normalized = normalize_vehicle_description(query.vehicle_description)
        without_year = _without_year(normalized)
        matches = [
            record
            for record in self._records
            if (
                normalized in {normalize_vehicle_description(alias) for alias in record.aliases}
                or without_year in {normalize_vehicle_description(alias) for alias in record.aliases}
            )
        ]
        if query.year is not None:
            year_matches = [record for record in matches if record.year == query.year]
            if year_matches:
                matches = year_matches
            else:
                matches = [record for record in matches if record.year is None]
        if len(matches) == 1:
            return VehicleLookupResult(status="matched", record=matches[0])
        if len(matches) > 1:
            return VehicleLookupResult(
                status="ambiguous",
                candidate_record_ids=tuple(record.record_id for record in matches),
            )
        return VehicleLookupResult(status="not_found")


class LocalVehicleMetadataProvider(CachedVehicleMetadataProvider):
    def __init__(self) -> None:
        super().__init__(LOCAL_VERIFIED_VEHICLE_RECORDS)


def normalize_vehicle_description(description: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", " ", description.lower())
    return re.sub(r"\s+", " ", normalized).strip()


def _without_year(description: str) -> str:
    without_year = re.sub(r"\b(?:19|20)\d{2}\b", "", description)
    return re.sub(r"\s+", " ", without_year).strip()
