from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
import heapq
import json
import math
from pathlib import Path
import re
from typing import Literal, Protocol


GEOSPATIAL_DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "geospatial"

PlaceResolutionStatus = Literal["resolved", "unknown", "ambiguous"]
RouteDistanceStatus = Literal["resolved", "unavailable", "mode_not_supported"]
ElectricityRegionStatus = Literal["resolved", "unknown", "ambiguous"]


@dataclass(frozen=True)
class PlaceRecord:
    place_id: str
    name: str
    aliases: tuple[str, ...]
    place_type: str
    region: str
    latitude: float
    longitude: float
    source: str
    source_version: str


@dataclass(frozen=True)
class PlaceResolution:
    status: PlaceResolutionStatus
    query: str
    record: PlaceRecord | None = None
    candidates: tuple[PlaceRecord, ...] = ()
    confidence: float = 0.0
    source: str | None = None
    matched_alias: str | None = None
    match_type: Literal["exact_alias", "fuzzy_alias"] | None = None


@dataclass(frozen=True)
class _FuzzyPlaceCandidate:
    score: float
    alias: str
    record: PlaceRecord


@dataclass(frozen=True)
class RouteDistanceRecord:
    origin_place_id: str
    destination_place_id: str
    mode: str
    distance: float
    distance_unit: str
    distance_source: str
    confidence: float
    source_version: str
    bidirectional: bool = True


@dataclass(frozen=True)
class RouteNetworkEdge:
    origin_place_id: str
    destination_place_id: str
    mode: str
    distance: float
    distance_unit: str
    distance_source: str
    confidence: float
    source_version: str
    bidirectional: bool = True


@dataclass(frozen=True)
class RouteDistanceResolution:
    status: RouteDistanceStatus
    origin: PlaceRecord
    destination: PlaceRecord
    mode: str
    distance: float | None = None
    distance_unit: str = "km"
    distance_source: str | None = None
    confidence: float = 0.0
    source_version: str | None = None
    exact: bool = False
    route_path_place_ids: tuple[str, ...] = ()
    route_path_place_names: tuple[str, ...] = ()


@dataclass(frozen=True)
class ElectricityRegionRecord:
    region: str
    region_name: str
    country: str
    factor_region: str
    fallback_region: str
    aliases: tuple[str, ...]
    source: str
    source_version: str


@dataclass(frozen=True)
class ElectricityRegionResolution:
    status: ElectricityRegionStatus
    query: str
    record: ElectricityRegionRecord | None = None
    candidates: tuple[ElectricityRegionRecord, ...] = ()
    confidence: float = 0.0
    source: str | None = None
    matched_alias: str | None = None


class PlaceResolver(Protocol):
    def resolve_place(self, query: str) -> PlaceResolution:
        """Resolve a user-supplied place string to a maintained place record."""


class RouteDistanceProvider(Protocol):
    def distance(
        self,
        origin: PlaceRecord,
        destination: PlaceRecord,
        mode: str,
    ) -> RouteDistanceResolution:
        """Return a mode-aware route or approximation for resolved places."""


class ElectricityRegionResolver(Protocol):
    def resolve_region(self, text: str) -> ElectricityRegionResolution:
        """Resolve maintained electricity region aliases mentioned in text."""


class LocalPlaceResolver:
    def __init__(
        self,
        records: list[PlaceRecord] | None = None,
        fuzzy_threshold: float = 0.82,
        ambiguity_margin: float = 0.06,
    ) -> None:
        self.records = records if records is not None else load_place_records()
        self.fuzzy_threshold = fuzzy_threshold
        self.ambiguity_margin = ambiguity_margin
        aliases: dict[str, list[PlaceRecord]] = {}
        alias_entries: list[tuple[str, str, PlaceRecord]] = []
        for record in self.records:
            for alias in (record.name, *record.aliases):
                normalized = _normalize_key(alias)
                if normalized:
                    aliases.setdefault(normalized, []).append(record)
                    alias_entries.append((normalized, alias, record))
        self._aliases = aliases
        self._alias_entries = alias_entries

    def resolve_place(self, query: str) -> PlaceResolution:
        normalized = _normalize_key(query)
        if not normalized:
            return PlaceResolution(status="unknown", query=query)
        candidates = _unique_place_records(self._aliases.get(normalized, ()))
        if not candidates:
            return self._resolve_fuzzy(query, normalized)
        if len(candidates) > 1:
            return PlaceResolution(
                status="ambiguous",
                query=query,
                candidates=candidates,
                confidence=0.35,
                source="place_aliases",
            )
        record = candidates[0]
        return PlaceResolution(
            status="resolved",
            query=query,
            record=record,
            candidates=candidates,
            confidence=0.95,
            source=record.source,
            matched_alias=normalized,
            match_type="exact_alias",
        )

    def _resolve_fuzzy(self, query: str, normalized: str) -> PlaceResolution:
        fuzzy = self._fuzzy_candidates(normalized)
        if not fuzzy:
            return PlaceResolution(status="unknown", query=query)
        top = fuzzy[0]
        close_candidates = [
            candidate for candidate in fuzzy
            if top.score - candidate.score <= self.ambiguity_margin
        ]
        if len(close_candidates) > 1:
            return PlaceResolution(
                status="ambiguous",
                query=query,
                candidates=tuple(candidate.record for candidate in close_candidates),
                confidence=0.35,
                source="place_aliases",
            )
        return PlaceResolution(
            status="resolved",
            query=query,
            record=top.record,
            candidates=(top.record,),
            confidence=round(min(0.88, top.score), 2),
            source=top.record.source,
            matched_alias=top.alias,
            match_type="fuzzy_alias",
        )

    def _fuzzy_candidates(self, normalized_query: str) -> list["_FuzzyPlaceCandidate"]:
        if len(normalized_query) < 4:
            return []
        by_place_id: dict[str, _FuzzyPlaceCandidate] = {}
        for normalized_alias, display_alias, record in self._alias_entries:
            score = _alias_similarity(normalized_query, normalized_alias)
            if score < self.fuzzy_threshold:
                continue
            existing = by_place_id.get(record.place_id)
            candidate = _FuzzyPlaceCandidate(
                score=score,
                alias=_normalize_key(display_alias),
                record=record,
            )
            if existing is None or candidate.score > existing.score:
                by_place_id[record.place_id] = candidate
        return sorted(
            by_place_id.values(),
            key=lambda candidate: (-candidate.score, candidate.record.place_id),
        )


class LocalRouteDistanceProvider:
    def __init__(
        self,
        records: list[RouteDistanceRecord] | None = None,
        network_edges: list[RouteNetworkEdge] | None = None,
        place_records: list[PlaceRecord] | None = None,
        supported_approximate_modes: tuple[str, ...] = (
            "car_ride",
            "rideshare",
            "bus_ride",
            "train_ride",
        ),
    ) -> None:
        self.records = records if records is not None else load_route_distance_records()
        self.network_edges = (
            network_edges if network_edges is not None else load_route_network_edges()
        )
        self.place_records = (
            place_records if place_records is not None else load_place_records()
        )
        self._places_by_id = {record.place_id: record for record in self.place_records}
        self.supported_approximate_modes = supported_approximate_modes
        self._records_by_key = {
            (record.origin_place_id, record.destination_place_id, record.mode): record
            for record in self.records
        }
        self._network_by_mode = self._build_network_by_mode()

    def distance(
        self,
        origin: PlaceRecord,
        destination: PlaceRecord,
        mode: str,
    ) -> RouteDistanceResolution:
        exact_record = self._exact_record(origin.place_id, destination.place_id, mode)
        if exact_record is not None:
            return RouteDistanceResolution(
                status="resolved",
                origin=origin,
                destination=destination,
                mode=mode,
                distance=round(float(exact_record.distance), 3),
                distance_unit=exact_record.distance_unit,
                distance_source=exact_record.distance_source,
                confidence=exact_record.confidence,
                source_version=exact_record.source_version,
                exact=True,
                route_path_place_ids=(origin.place_id, destination.place_id),
                route_path_place_names=(origin.name, destination.name),
            )
        network_resolution = self._network_distance(origin, destination, mode)
        if network_resolution is not None:
            return network_resolution
        if mode not in self.supported_approximate_modes:
            return RouteDistanceResolution(
                status="mode_not_supported",
                origin=origin,
                destination=destination,
                mode=mode,
            )
        distance = _centroid_distance_km(origin, destination) * _mode_multiplier(mode)
        if distance <= 0:
            return RouteDistanceResolution(
                status="unavailable",
                origin=origin,
                destination=destination,
                mode=mode,
            )
        return RouteDistanceResolution(
            status="resolved",
            origin=origin,
            destination=destination,
            mode=mode,
            distance=round(distance, 3),
            distance_unit="km",
            distance_source="place_centroid_approximation",
            confidence=_approximate_confidence(mode),
            source_version=max(
                origin.source_version,
                destination.source_version,
            ),
            exact=False,
        )

    def _exact_record(
        self,
        origin_place_id: str,
        destination_place_id: str,
        mode: str,
    ) -> RouteDistanceRecord | None:
        direct = self._records_by_key.get((origin_place_id, destination_place_id, mode))
        if direct is not None:
            return direct
        reverse = self._records_by_key.get((destination_place_id, origin_place_id, mode))
        if reverse is not None and reverse.bidirectional:
            return RouteDistanceRecord(
                origin_place_id=origin_place_id,
                destination_place_id=destination_place_id,
                mode=mode,
                distance=reverse.distance,
                distance_unit=reverse.distance_unit,
                distance_source=reverse.distance_source,
                confidence=reverse.confidence,
                source_version=reverse.source_version,
                bidirectional=reverse.bidirectional,
            )
        return None

    def _network_distance(
        self,
        origin: PlaceRecord,
        destination: PlaceRecord,
        mode: str,
    ) -> RouteDistanceResolution | None:
        adjacency = self._network_by_mode.get(mode)
        if not adjacency:
            return None
        path = _shortest_path(adjacency, origin.place_id, destination.place_id)
        if path is None:
            return None
        distance, place_ids, edges = path
        if not edges:
            return None
        sources = {edge.distance_source for edge in edges}
        source_versions = {edge.source_version for edge in edges}
        distance_source = (
            next(iter(sources)) if len(sources) == 1 else "qgis_route_network_mixed"
        )
        return RouteDistanceResolution(
            status="resolved",
            origin=origin,
            destination=destination,
            mode=mode,
            distance=round(distance, 3),
            distance_unit="km",
            distance_source=distance_source,
            confidence=min(edge.confidence for edge in edges),
            source_version=max(source_versions),
            exact=True,
            route_path_place_ids=tuple(place_ids),
            route_path_place_names=tuple(
                self._places_by_id[place_id].name
                for place_id in place_ids
                if place_id in self._places_by_id
            ),
        )

    def _build_network_by_mode(
        self,
    ) -> dict[str, dict[str, list[tuple[str, RouteNetworkEdge]]]]:
        network: dict[str, dict[str, list[tuple[str, RouteNetworkEdge]]]] = {}
        for edge in self.network_edges:
            network.setdefault(edge.mode, {}).setdefault(edge.origin_place_id, []).append(
                (edge.destination_place_id, edge)
            )
            if edge.bidirectional:
                reverse = RouteNetworkEdge(
                    origin_place_id=edge.destination_place_id,
                    destination_place_id=edge.origin_place_id,
                    mode=edge.mode,
                    distance=edge.distance,
                    distance_unit=edge.distance_unit,
                    distance_source=edge.distance_source,
                    confidence=edge.confidence,
                    source_version=edge.source_version,
                    bidirectional=edge.bidirectional,
                )
                network.setdefault(edge.mode, {}).setdefault(reverse.origin_place_id, []).append(
                    (reverse.destination_place_id, reverse)
                )
        return network


class LocalElectricityRegionResolver:
    def __init__(
        self,
        records: list[ElectricityRegionRecord] | None = None,
    ) -> None:
        self.records = records if records is not None else load_electricity_region_records()
        aliases: dict[str, list[ElectricityRegionRecord]] = {}
        for record in self.records:
            for alias in (record.region, record.region_name, *record.aliases):
                normalized = _normalize_key(alias)
                if normalized:
                    aliases.setdefault(normalized, []).append(record)
        self._aliases = aliases

    def resolve_region(self, text: str) -> ElectricityRegionResolution:
        normalized_text = f" {_normalize_key(text)} "
        matches: dict[str, ElectricityRegionRecord] = {}
        matched_aliases: dict[str, str] = {}
        for alias, records in self._aliases.items():
            if f" {alias} " not in normalized_text:
                continue
            for record in records:
                matches[record.region] = record
                matched_aliases.setdefault(record.region, alias)
        if not matches:
            return ElectricityRegionResolution(status="unknown", query=text)
        candidates = tuple(matches.values())
        if len(candidates) > 1:
            return ElectricityRegionResolution(
                status="ambiguous",
                query=text,
                candidates=candidates,
                confidence=0.35,
                source="electricity_regions",
            )
        record = candidates[0]
        return ElectricityRegionResolution(
            status="resolved",
            query=text,
            record=record,
            candidates=candidates,
            confidence=0.95,
            source=record.source,
            matched_alias=matched_aliases[record.region],
        )


def load_place_records(
    path: Path | None = None,
) -> list[PlaceRecord]:
    records = []
    for item in _load_jsonl(path or GEOSPATIAL_DATA_DIR / "place_aliases.jsonl"):
        records.append(
            PlaceRecord(
                place_id=str(item["place_id"]),
                name=str(item["name"]),
                aliases=tuple(str(alias) for alias in item.get("aliases", ())),
                place_type=str(item["place_type"]),
                region=str(item["region"]),
                latitude=float(item["latitude"]),
                longitude=float(item["longitude"]),
                source=str(item["source"]),
                source_version=str(item["source_version"]),
            )
        )
    return records


def load_route_distance_records(
    path: Path | None = None,
) -> list[RouteDistanceRecord]:
    records = []
    for item in _load_jsonl(path or GEOSPATIAL_DATA_DIR / "route_distances.jsonl"):
        records.append(
            RouteDistanceRecord(
                origin_place_id=str(item["origin_place_id"]),
                destination_place_id=str(item["destination_place_id"]),
                mode=str(item["mode"]),
                distance=float(item["distance"]),
                distance_unit=str(item.get("distance_unit") or "km"),
                distance_source=str(item["distance_source"]),
                confidence=float(item["confidence"]),
                source_version=str(item["source_version"]),
                bidirectional=bool(item.get("bidirectional", True)),
            )
        )
    return records


def load_route_network_edges(
    path: Path | None = None,
) -> list[RouteNetworkEdge]:
    records = []
    for item in _load_jsonl(path or GEOSPATIAL_DATA_DIR / "route_network_edges.jsonl"):
        records.append(
            RouteNetworkEdge(
                origin_place_id=str(item["origin_place_id"]),
                destination_place_id=str(item["destination_place_id"]),
                mode=str(item["mode"]),
                distance=float(item["distance"]),
                distance_unit=str(item.get("distance_unit") or "km"),
                distance_source=str(item["distance_source"]),
                confidence=float(item["confidence"]),
                source_version=str(item["source_version"]),
                bidirectional=bool(item.get("bidirectional", True)),
            )
        )
    return records


def load_electricity_region_records(
    path: Path | None = None,
) -> list[ElectricityRegionRecord]:
    records = []
    for item in _load_jsonl(path or GEOSPATIAL_DATA_DIR / "electricity_regions.jsonl"):
        records.append(
            ElectricityRegionRecord(
                region=str(item["region"]),
                region_name=str(item["region_name"]),
                country=str(item["country"]),
                factor_region=str(item["factor_region"]),
                fallback_region=str(item["fallback_region"]),
                aliases=tuple(str(alias) for alias in item.get("aliases", ())),
                source=str(item["source"]),
                source_version=str(item["source_version"]),
            )
        )
    return records


def _load_jsonl(path: Path) -> list[dict]:
    records: list[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                records.append(json.loads(stripped))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL record in {path}:{line_number}") from exc
    return records


def _unique_place_records(records: list[PlaceRecord]) -> tuple[PlaceRecord, ...]:
    unique: dict[str, PlaceRecord] = {}
    for record in records:
        unique.setdefault(record.place_id, record)
    return tuple(unique.values())


def _alias_similarity(query: str, alias: str) -> float:
    if not query or not alias:
        return 0.0
    direct = SequenceMatcher(None, query, alias).ratio()
    token_sorted = SequenceMatcher(
        None,
        " ".join(sorted(query.split())),
        " ".join(sorted(alias.split())),
    ).ratio()
    edit_score = _edit_similarity(query, alias)
    prefix_bonus = 0.03 if alias.startswith(query[: max(3, min(len(query), 5))]) else 0.0
    return round(min(1.0, max(direct, token_sorted, edit_score) + prefix_bonus), 3)


def _edit_similarity(first: str, second: str) -> float:
    max_length = max(len(first), len(second))
    if max_length == 0:
        return 1.0
    distance = _levenshtein_distance(first, second)
    return 1.0 - (distance / max_length)


def _levenshtein_distance(first: str, second: str) -> int:
    if first == second:
        return 0
    if not first:
        return len(second)
    if not second:
        return len(first)
    previous = list(range(len(second) + 1))
    for first_index, first_char in enumerate(first, start=1):
        current = [first_index]
        for second_index, second_char in enumerate(second, start=1):
            insertion = current[second_index - 1] + 1
            deletion = previous[second_index] + 1
            substitution = previous[second_index - 1] + (first_char != second_char)
            current.append(min(insertion, deletion, substitution))
        previous = current
    return previous[-1]


def _normalize_key(value: str) -> str:
    text = re.sub(r"[^a-z0-9]+", " ", value.lower())
    return re.sub(r"\s+", " ", text).strip()


def _centroid_distance_km(origin: PlaceRecord, destination: PlaceRecord) -> float:
    radius_km = 6371.0088
    lat1 = math.radians(origin.latitude)
    lat2 = math.radians(destination.latitude)
    delta_lat = math.radians(destination.latitude - origin.latitude)
    delta_lon = math.radians(destination.longitude - origin.longitude)
    haversine = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(delta_lon / 2) ** 2
    )
    return radius_km * 2 * math.atan2(math.sqrt(haversine), math.sqrt(1 - haversine))


def _mode_multiplier(mode: str) -> float:
    return {
        "car_ride": 1.35,
        "rideshare": 1.35,
        "bus_ride": 1.30,
        "train_ride": 1.18,
    }.get(mode, 1.30)


def _approximate_confidence(mode: str) -> float:
    return {
        "car_ride": 0.52,
        "rideshare": 0.52,
        "bus_ride": 0.48,
        "train_ride": 0.50,
    }.get(mode, 0.45)


def _shortest_path(
    adjacency: dict[str, list[tuple[str, RouteNetworkEdge]]],
    origin_place_id: str,
    destination_place_id: str,
) -> tuple[float, list[str], list[RouteNetworkEdge]] | None:
    frontier: list[tuple[float, str, list[str], list[RouteNetworkEdge]]] = []
    heapq.heappush(frontier, (0.0, origin_place_id, [origin_place_id], []))
    best_distance: dict[str, float] = {origin_place_id: 0.0}

    while frontier:
        distance, place_id, path, edges = heapq.heappop(frontier)
        if place_id == destination_place_id:
            return distance, path, edges
        if distance > best_distance.get(place_id, float("inf")):
            continue
        for next_place_id, edge in adjacency.get(place_id, ()):
            if edge.distance_unit != "km":
                continue
            candidate_distance = distance + float(edge.distance)
            if candidate_distance >= best_distance.get(next_place_id, float("inf")):
                continue
            best_distance[next_place_id] = candidate_distance
            heapq.heappush(
                frontier,
                (
                    candidate_distance,
                    next_place_id,
                    [*path, next_place_id],
                    [*edges, edge],
                )
            )
    return None
