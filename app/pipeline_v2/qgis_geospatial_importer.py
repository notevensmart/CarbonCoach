from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any, Iterable


@dataclass(frozen=True)
class QgisImportResult:
    place_count: int
    route_edge_count: int
    road_node_count: int
    road_edge_count: int
    place_route_node_count: int
    route_distance_count: int
    electricity_region_count: int
    output_dir: Path


class QgisImportError(ValueError):
    """Raised when QGIS exports are missing required app-ready fields."""


SUPPORTED_ROAD_MODES = {"car_ride", "rideshare"}
DEFAULT_SNAP_DISTANCE_THRESHOLD_M = 1000.0


def import_qgis_exports(input_dir: Path, output_dir: Path) -> QgisImportResult:
    input_dir = input_dir.resolve()
    output_dir = output_dir.resolve()
    if not input_dir.exists():
        raise QgisImportError(f"QGIS export directory does not exist: {input_dir}")

    source_manifest = _load_source_manifest(input_dir)
    places, place_validation = _load_places(input_dir, source_manifest)
    place_ids = {record["place_id"] for record in places}
    route_edges = _load_route_edges(input_dir, place_ids)
    road_nodes = _load_road_nodes(input_dir)
    road_node_ids = {record["node_id"] for record in road_nodes}
    road_edges = _load_road_edges(input_dir, road_node_ids)
    place_route_nodes = _load_place_route_nodes(
        input_dir,
        place_ids,
        road_node_ids,
        source_manifest,
    )
    route_distances = _load_route_distances(input_dir, place_ids)
    electricity_regions = _load_electricity_regions(input_dir)

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_jsonl(output_dir / "place_aliases.jsonl", places)
    _write_jsonl(output_dir / "route_network_edges.jsonl", route_edges)
    _write_jsonl(output_dir / "road_network_nodes.jsonl", road_nodes)
    _write_jsonl(output_dir / "road_network_edges.jsonl", road_edges)
    _write_jsonl(output_dir / "place_route_nodes.jsonl", place_route_nodes)
    _write_jsonl(output_dir / "route_distances.jsonl", route_distances)
    _write_jsonl(output_dir / "electricity_regions.jsonl", electricity_regions)
    _write_manifest(
        source_manifest,
        input_dir,
        output_dir,
        places=places,
        route_edges=route_edges,
        road_nodes=road_nodes,
        road_edges=road_edges,
        place_route_nodes=place_route_nodes,
        route_distances=route_distances,
        electricity_regions=electricity_regions,
        place_validation=place_validation,
        place_count=len(places),
        route_edge_count=len(route_edges),
        road_node_count=len(road_nodes),
        road_edge_count=len(road_edges),
        place_route_node_count=len(place_route_nodes),
        route_distance_count=len(route_distances),
        electricity_region_count=len(electricity_regions),
    )
    return QgisImportResult(
        place_count=len(places),
        route_edge_count=len(route_edges),
        road_node_count=len(road_nodes),
        road_edge_count=len(road_edges),
        place_route_node_count=len(place_route_nodes),
        route_distance_count=len(route_distances),
        electricity_region_count=len(electricity_regions),
        output_dir=output_dir,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Import QGIS-exported geospatial layers into CarbonCoach runtime JSONL artifacts."
    )
    parser.add_argument("--input-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    result = import_qgis_exports(args.input_dir, args.output_dir)
    print(
        "Imported QGIS exports: "
        f"{result.place_count} places, "
        f"{result.route_edge_count} route edges, "
        f"{result.road_node_count} road nodes, "
        f"{result.road_edge_count} road edges, "
        f"{result.place_route_node_count} place route-node snaps, "
        f"{result.route_distance_count} exact route distances, "
        f"{result.electricity_region_count} electricity regions "
        f"to {result.output_dir}"
    )
    return 0


def _load_places(
    input_dir: Path,
    source_manifest: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    features = _load_geojson_features(_required_file(input_dir, "places.geojson"))
    records = []
    for feature_index, feature in enumerate(features, start=1):
        properties = _properties(feature, "places.geojson", feature_index)
        geometry = feature.get("geometry") or {}
        longitude, latitude = _point_or_property_coordinates(
            geometry,
            properties,
            "places.geojson",
            feature_index,
        )
        aliases = _required_aliases(properties, "places.geojson", feature_index)
        ambiguous_aliases = _aliases(properties.get("ambiguous_aliases"))
        _validate_ambiguous_aliases_subset(
            aliases,
            ambiguous_aliases,
            "places.geojson",
            feature_index,
        )
        record = {
            "place_id": _required_text(properties, "place_id", "places.geojson", feature_index),
            "name": _required_text(properties, "name", "places.geojson", feature_index),
            "aliases": aliases,
            "place_type": _required_text(properties, "place_type", "places.geojson", feature_index),
            "region": _required_text(properties, "region", "places.geojson", feature_index),
            "latitude": latitude,
            "longitude": longitude,
            "source": _required_text(properties, "source", "places.geojson", feature_index),
            "source_version": _required_text(
                properties,
                "source_version",
                "places.geojson",
                feature_index,
            ),
        }
        if ambiguous_aliases:
            record["ambiguous_aliases"] = ambiguous_aliases
        records.append(record)
    _validate_duplicate_place_ids(records)
    validation = _validate_duplicate_aliases(records, source_manifest)
    return sorted(records, key=lambda record: record["place_id"]), validation


def _load_route_edges(input_dir: Path, place_ids: set[str]) -> list[dict[str, Any]]:
    path = _optional_file(input_dir, "route_network_edges.geojson")
    if path is None:
        return []
    records = []
    for feature_index, feature in enumerate(_load_geojson_features(path), start=1):
        properties = _properties(feature, path.name, feature_index)
        record = _route_record(properties, path.name, feature_index)
        _validate_place_refs(record, place_ids, path.name, feature_index)
        records.append(record)
    return sorted(
        records,
        key=lambda record: (
            record["mode"],
            record["origin_place_id"],
            record["destination_place_id"],
        ),
    )


def _load_road_nodes(input_dir: Path) -> list[dict[str, Any]]:
    path = _optional_file(input_dir, "road_network_nodes.geojson")
    if path is None:
        return []
    records = []
    for feature_index, feature in enumerate(_load_geojson_features(path), start=1):
        properties = _properties(feature, path.name, feature_index)
        geometry = feature.get("geometry") or {}
        longitude, latitude = _point_or_property_coordinates(
            geometry,
            properties,
            path.name,
            feature_index,
        )
        records.append(
            {
                "node_id": _required_text(properties, "node_id", path.name, feature_index),
                "latitude": latitude,
                "longitude": longitude,
                "source": _required_text(properties, "source", path.name, feature_index),
                "source_version": _required_text(
                    properties,
                    "source_version",
                    path.name,
                    feature_index,
                ),
            }
        )
    _validate_duplicate_record_ids(records, "node_id", path.name)
    return sorted(records, key=lambda record: record["node_id"])


def _load_road_edges(input_dir: Path, node_ids: set[str]) -> list[dict[str, Any]]:
    path = _optional_file(input_dir, "road_network_edges.geojson")
    if path is None:
        return []
    if not node_ids:
        raise QgisImportError(
            "road_network_edges.geojson requires road_network_nodes.geojson with matching node_id values."
        )
    records = []
    for feature_index, feature in enumerate(_load_geojson_features(path), start=1):
        properties = _properties(feature, path.name, feature_index)
        record = _road_edge_record(properties, path.name, feature_index)
        _validate_road_node_refs(record, node_ids, path.name, feature_index)
        records.append(record)
    _validate_duplicate_record_ids(records, "edge_id", path.name)
    return sorted(
        records,
        key=lambda record: record["edge_id"],
    )


def _load_place_route_nodes(
    input_dir: Path,
    place_ids: set[str],
    node_ids: set[str],
    source_manifest: dict[str, Any],
) -> list[dict[str, Any]]:
    path = _optional_file(input_dir, "place_route_nodes.csv")
    if path is None:
        return []
    if not node_ids:
        raise QgisImportError(
            "place_route_nodes.csv requires road_network_nodes.geojson with matching node_id values."
        )
    snap_distance_threshold_m = _snap_distance_threshold_m(source_manifest)
    records = []
    for row_index, row in enumerate(_load_csv_rows(path), start=2):
        record = _place_route_node_record(
            row,
            path.name,
            row_index,
            snap_distance_threshold_m,
        )
        _validate_snap_refs(record, place_ids, node_ids, path.name, row_index)
        records.append(record)
    _validate_duplicate_place_route_node_snaps(records, path.name)
    return sorted(
        records,
        key=lambda record: (
            record["place_id"],
            record["mode"],
            record["node_id"],
        ),
    )


def _load_route_distances(input_dir: Path, place_ids: set[str]) -> list[dict[str, Any]]:
    path = _optional_file(input_dir, "route_distances.csv")
    if path is None:
        return []
    records = []
    for row_index, row in enumerate(_load_csv_rows(path), start=2):
        record = _route_record(row, path.name, row_index)
        _validate_place_refs(record, place_ids, path.name, row_index)
        records.append(record)
    return sorted(
        records,
        key=lambda record: (
            record["mode"],
            record["origin_place_id"],
            record["destination_place_id"],
        ),
    )


def _load_electricity_regions(input_dir: Path) -> list[dict[str, Any]]:
    path = _optional_file(input_dir, "electricity_regions.csv")
    if path is None:
        return []
    records = []
    for row_index, row in enumerate(_load_csv_rows(path), start=2):
        records.append(
            {
                "region": _required_text(row, "region", path.name, row_index),
                "region_name": _required_text(row, "region_name", path.name, row_index),
                "country": _required_text(row, "country", path.name, row_index),
                "factor_region": _required_text(row, "factor_region", path.name, row_index),
                "fallback_region": _required_text(row, "fallback_region", path.name, row_index),
                "aliases": _aliases(row.get("aliases")),
                "source": _required_text(row, "source", path.name, row_index),
                "source_version": _required_text(row, "source_version", path.name, row_index),
            }
        )
    return sorted(records, key=lambda record: record["region"])


def _route_record(
    properties: dict[str, Any],
    file_name: str,
    record_index: int,
) -> dict[str, Any]:
    distance = _optional_number(properties, "distance_km")
    if distance is None:
        distance = _required_number(properties, "distance", file_name, record_index)
    return {
        "origin_place_id": _required_text(properties, "origin_place_id", file_name, record_index),
        "destination_place_id": _required_text(
            properties,
            "destination_place_id",
            file_name,
            record_index,
        ),
        "mode": _required_text(properties, "mode", file_name, record_index),
        "distance": distance,
        "distance_unit": str(properties.get("distance_unit") or "km"),
        "distance_source": _required_text(properties, "distance_source", file_name, record_index),
        "confidence": _required_number(properties, "confidence", file_name, record_index),
        "source_version": _required_text(properties, "source_version", file_name, record_index),
        "bidirectional": _optional_bool(properties.get("bidirectional"), default=True),
    }


def _road_edge_record(
    properties: dict[str, Any],
    file_name: str,
    record_index: int,
) -> dict[str, Any]:
    distance = _required_number(properties, "distance_km", file_name, record_index)
    if distance <= 0:
        raise QgisImportError(
            f"{file_name}:{record_index} distance_km must be positive; got {distance}."
        )
    confidence = _required_number(properties, "confidence", file_name, record_index)
    if confidence < 0 or confidence > 1:
        raise QgisImportError(
            f"{file_name}:{record_index} confidence must be between 0 and 1; got {confidence}."
        )
    return {
        "edge_id": _required_text(properties, "edge_id", file_name, record_index),
        "from_node_id": _required_text(properties, "from_node_id", file_name, record_index),
        "to_node_id": _required_text(properties, "to_node_id", file_name, record_index),
        "distance_km": distance,
        "modes": _required_road_modes(properties, file_name, record_index),
        "bidirectional": _optional_bool(properties.get("bidirectional"), default=True),
        "source": _required_text(properties, "source", file_name, record_index),
        "confidence": confidence,
        "source_version": _required_text(properties, "source_version", file_name, record_index),
    }


def _place_route_node_record(
    properties: dict[str, Any],
    file_name: str,
    record_index: int,
    snap_distance_threshold_m: float,
) -> dict[str, Any]:
    snap_distance_m = _required_number(
        properties,
        "snap_distance_m",
        file_name,
        record_index,
    )
    if snap_distance_m < 0:
        raise QgisImportError(
            f"{file_name}:{record_index} snap_distance_m must be non-negative; "
            f"got {snap_distance_m}."
        )
    approximate = _optional_bool(
        _first_present(
            properties,
            "approximate",
            "snap_approximate",
            "is_approximate",
        ),
        default=False,
    )
    if snap_distance_m > snap_distance_threshold_m and not approximate:
        raise QgisImportError(
            f"{file_name}:{record_index} snap_distance_m {snap_distance_m} exceeds "
            f"configured threshold {snap_distance_threshold_m} unless approximate=true."
        )
    snap_confidence = _required_number(
        properties,
        "snap_confidence",
        file_name,
        record_index,
    )
    if snap_confidence < 0 or snap_confidence > 1:
        raise QgisImportError(
            f"{file_name}:{record_index} snap_confidence must be between 0 and 1; "
            f"got {snap_confidence}."
        )
    mode = _required_text(properties, "mode", file_name, record_index)
    if mode not in SUPPORTED_ROAD_MODES:
        raise QgisImportError(
            f"{file_name}:{record_index} has unsupported road mode: {mode}."
        )
    return {
        "place_id": _required_text(properties, "place_id", file_name, record_index),
        "mode": mode,
        "node_id": _required_text(properties, "node_id", file_name, record_index),
        "snap_distance_m": snap_distance_m,
        "snap_confidence": snap_confidence,
        "snap_source": _required_text(properties, "snap_source", file_name, record_index),
        "source_version": _required_text(properties, "source_version", file_name, record_index),
        "approximate": approximate,
    }


def _write_manifest(
    source_manifest: dict[str, Any],
    input_dir: Path,
    output_dir: Path,
    *,
    places: list[dict[str, Any]],
    route_edges: list[dict[str, Any]],
    road_nodes: list[dict[str, Any]],
    road_edges: list[dict[str, Any]],
    place_route_nodes: list[dict[str, Any]],
    route_distances: list[dict[str, Any]],
    electricity_regions: list[dict[str, Any]],
    place_validation: dict[str, Any],
    place_count: int,
    route_edge_count: int,
    road_node_count: int,
    road_edge_count: int,
    place_route_node_count: int,
    route_distance_count: int,
    electricity_region_count: int,
) -> None:
    generated_at = _generated_at(
        source_manifest,
        places,
        route_edges,
        road_nodes,
        road_edges,
        place_route_nodes,
        route_distances,
        electricity_regions,
    )
    road_network_summary = _road_network_summary(road_nodes, road_edges)
    place_route_node_summary = _place_route_node_summary(
        place_route_nodes,
        source_manifest,
    )
    manifest = {
        "artifact_set": source_manifest.get(
            "artifact_set",
            "carboncoach-v2-geospatial-qgis-export",
        ),
        "version": source_manifest.get("version", generated_at[:10]),
        "generated_at": generated_at,
        "generated_from": str(input_dir),
        "runtime_dependency_policy": (
            "QGIS is used only for offline data preparation; FastAPI runtime loads "
            "these generated compact JSONL artifacts."
        ),
        "crs": source_manifest.get("crs", "EPSG:4326"),
        "source_notes": source_manifest.get("source_notes", []),
        "artifact_counts": {
            "places": place_count,
            "route_network_edges": route_edge_count,
            "road_network_nodes": road_node_count,
            "road_network_edges": road_edge_count,
            "place_route_nodes": place_route_node_count,
            "route_distances": route_distance_count,
            "electricity_regions": electricity_region_count,
        },
        "place_counts": {
            "by_place_type": _count_by(places, "place_type"),
            "by_region": _count_by(places, "region"),
        },
        "validation": {
            "status": "passed",
            "places": place_validation,
            "road_network": {
                "status": road_network_summary["validation_status"],
                "supported_modes": sorted(SUPPORTED_ROAD_MODES),
                "unsupported_modes": [],
                "unknown_node_references": [],
                "duplicate_node_ids": [],
                "duplicate_edge_ids": [],
            },
            "place_route_nodes": {
                "status": place_route_node_summary["validation_status"],
                "supported_modes": sorted(SUPPORTED_ROAD_MODES),
                "unknown_place_references": [],
                "unknown_node_references": [],
                "duplicate_place_mode_refs": [],
                "snap_distance_threshold_m": place_route_node_summary[
                    "snap_distance_threshold_m"
                ],
            },
        },
        "road_network": road_network_summary,
        "place_route_nodes": place_route_node_summary,
        "artifacts": [
            {
                "path": "place_aliases.jsonl",
                "schema": "place_alias_record",
                "source": "places.geojson",
            },
            {
                "path": "route_network_edges.jsonl",
                "schema": "route_network_edge",
                "source": "route_network_edges.geojson",
            },
            {
                "path": "road_network_nodes.jsonl",
                "schema": "road_network_node",
                "source": "road_network_nodes.geojson",
            },
            {
                "path": "road_network_edges.jsonl",
                "schema": "road_network_edge",
                "source": "road_network_edges.geojson",
            },
            {
                "path": "place_route_nodes.jsonl",
                "schema": "place_route_node_snap",
                "source": "place_route_nodes.csv",
            },
            {
                "path": "route_distances.jsonl",
                "schema": "route_distance_record",
                "source": "route_distances.csv",
            },
            {
                "path": "electricity_regions.jsonl",
                "schema": "electricity_region_record",
                "source": "electricity_regions.csv",
            },
        ],
    }
    _write_json(output_dir / "manifest.json", manifest)


def _load_source_manifest(input_dir: Path) -> dict[str, Any]:
    path = input_dir / "qgis_export_manifest.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _load_geojson_features(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("type") != "FeatureCollection":
        raise QgisImportError(f"{path.name} must be a GeoJSON FeatureCollection.")
    features = payload.get("features")
    if not isinstance(features, list):
        raise QgisImportError(f"{path.name} must contain a features array.")
    return features


def _load_csv_rows(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _properties(
    feature: dict[str, Any],
    file_name: str,
    feature_index: int,
) -> dict[str, Any]:
    properties = feature.get("properties")
    if not isinstance(properties, dict):
        raise QgisImportError(f"{file_name}:{feature_index} is missing properties.")
    return properties


def _point_or_property_coordinates(
    geometry: dict[str, Any],
    properties: dict[str, Any],
    file_name: str,
    feature_index: int,
) -> tuple[float, float]:
    if geometry.get("type") == "Point":
        coordinates = geometry.get("coordinates")
        if (
            isinstance(coordinates, list)
            and len(coordinates) >= 2
            and isinstance(coordinates[0], (int, float))
            and isinstance(coordinates[1], (int, float))
        ):
            return float(coordinates[0]), float(coordinates[1])
    longitude = _optional_number(properties, "longitude")
    latitude = _optional_number(properties, "latitude")
    if longitude is not None and latitude is not None:
        return longitude, latitude
    raise QgisImportError(
        f"{file_name}:{feature_index} must have Point geometry or latitude/longitude properties."
    )


def _validate_place_refs(
    record: dict[str, Any],
    place_ids: set[str],
    file_name: str,
    record_index: int,
) -> None:
    for field in ("origin_place_id", "destination_place_id"):
        if record[field] not in place_ids:
            raise QgisImportError(
                f"{file_name}:{record_index} references unknown {field}={record[field]}."
            )


def _validate_road_node_refs(
    record: dict[str, Any],
    node_ids: set[str],
    file_name: str,
    record_index: int,
) -> None:
    for field in ("from_node_id", "to_node_id"):
        if record[field] not in node_ids:
            raise QgisImportError(
                f"{file_name}:{record_index} references unknown {field}={record[field]}."
            )


def _validate_snap_refs(
    record: dict[str, Any],
    place_ids: set[str],
    node_ids: set[str],
    file_name: str,
    record_index: int,
) -> None:
    if record["place_id"] not in place_ids:
        raise QgisImportError(
            f"{file_name}:{record_index} references unknown place_id={record['place_id']}."
        )
    if record["node_id"] not in node_ids:
        raise QgisImportError(
            f"{file_name}:{record_index} references unknown node_id={record['node_id']}."
        )


def _validate_duplicate_record_ids(
    records: list[dict[str, Any]],
    id_field: str,
    file_name: str,
) -> None:
    seen: set[str] = set()
    duplicates = []
    for record in records:
        record_id = str(record[id_field])
        if record_id in seen:
            duplicates.append(record_id)
        seen.add(record_id)
    if duplicates:
        duplicate_list = ", ".join(sorted(set(duplicates)))
        raise QgisImportError(
            f"{file_name} contains duplicate {id_field} values: {duplicate_list}."
        )


def _validate_duplicate_place_route_node_snaps(
    records: list[dict[str, Any]],
    file_name: str,
) -> None:
    seen: set[tuple[str, str]] = set()
    duplicates = []
    for record in records:
        key = (str(record["place_id"]), str(record["mode"]))
        if key in seen:
            duplicates.append(key)
        seen.add(key)
    if duplicates:
        duplicate_list = ", ".join(
            f"{place_id}/{mode}" for place_id, mode in sorted(set(duplicates))
        )
        raise QgisImportError(
            f"{file_name} contains duplicate place_id/mode snap rows: {duplicate_list}."
        )


def _validate_duplicate_place_ids(records: list[dict[str, Any]]) -> None:
    seen: dict[str, str] = {}
    duplicates = []
    for record in records:
        place_id = str(record["place_id"])
        if place_id in seen:
            duplicates.append(place_id)
        seen.setdefault(place_id, place_id)
    if duplicates:
        duplicate_list = ", ".join(sorted(set(duplicates)))
        raise QgisImportError(f"places.geojson contains duplicate place_id values: {duplicate_list}.")


def _validate_duplicate_aliases(
    records: list[dict[str, Any]],
    source_manifest: dict[str, Any],
) -> dict[str, Any]:
    aliases_by_key: dict[str, list[dict[str, Any]]] = {}
    display_aliases: dict[str, str] = {}
    for record in records:
        for alias in record["aliases"]:
            normalized = _normalize_alias(alias)
            if not normalized:
                continue
            aliases_by_key.setdefault(normalized, []).append(record)
            display_aliases.setdefault(normalized, alias)

    allowed_ambiguous_aliases = []
    accidental_duplicates = []
    for normalized_alias, matching_records in sorted(aliases_by_key.items()):
        unique_records = _unique_records_by_place_id(matching_records)
        if len(unique_records) <= 1:
            continue
        place_ids = tuple(record["place_id"] for record in unique_records)
        alias = display_aliases[normalized_alias]
        if _is_allowed_ambiguous_alias(
            normalized_alias,
            place_ids,
            unique_records,
            source_manifest,
        ):
            for record in unique_records:
                record_aliases = record.setdefault("ambiguous_aliases", [])
                if alias not in record_aliases:
                    record_aliases.append(alias)
            allowed_ambiguous_aliases.append(
                {
                    "alias": alias,
                    "normalized_alias": normalized_alias,
                    "place_ids": list(place_ids),
                    "place_names": [record["name"] for record in unique_records],
                }
            )
        else:
            accidental_duplicates.append(
                {
                    "alias": alias,
                    "normalized_alias": normalized_alias,
                    "place_ids": list(place_ids),
                }
            )

    if accidental_duplicates:
        duplicate_summary = "; ".join(
            f"{item['alias']} -> {', '.join(item['place_ids'])}"
            for item in accidental_duplicates
        )
        raise QgisImportError(
            "places.geojson contains duplicate aliases that point to multiple places "
            f"without explicit ambiguity approval: {duplicate_summary}."
        )

    return {
        "status": "passed",
        "duplicate_place_ids": [],
        "duplicate_aliases": [],
        "ambiguous_aliases": allowed_ambiguous_aliases,
    }


def _unique_records_by_place_id(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    unique: dict[str, dict[str, Any]] = {}
    for record in records:
        unique.setdefault(str(record["place_id"]), record)
    return [unique[place_id] for place_id in sorted(unique)]


def _is_allowed_ambiguous_alias(
    normalized_alias: str,
    place_ids: tuple[str, ...],
    records: list[dict[str, Any]],
    source_manifest: dict[str, Any],
) -> bool:
    record_level = all(
        normalized_alias
        in {_normalize_alias(item) for item in record.get("ambiguous_aliases", [])}
        for record in records
    )
    if record_level:
        return True
    return _source_manifest_allows_ambiguous_alias(
        normalized_alias,
        place_ids,
        source_manifest,
    )


def _source_manifest_allows_ambiguous_alias(
    normalized_alias: str,
    place_ids: tuple[str, ...],
    source_manifest: dict[str, Any],
) -> bool:
    raw = source_manifest.get("allowed_ambiguous_aliases", ())
    if isinstance(raw, dict):
        for key, value in raw.items():
            if _normalize_alias(str(key)) != normalized_alias:
                continue
            return _allowed_alias_value_matches(value, place_ids)
        return False
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, str) and _normalize_alias(item) == normalized_alias:
                return True
            if isinstance(item, dict):
                item_alias = str(item.get("alias", ""))
                if _normalize_alias(item_alias) != normalized_alias:
                    continue
                return _allowed_alias_value_matches(item.get("place_ids", True), place_ids)
    if isinstance(raw, str):
        return _normalize_alias(raw) == normalized_alias
    return False


def _allowed_alias_value_matches(value: Any, place_ids: tuple[str, ...]) -> bool:
    if value is True or value == "*":
        return True
    if isinstance(value, list):
        return set(str(item) for item in value) == set(place_ids)
    if isinstance(value, tuple):
        return set(str(item) for item in value) == set(place_ids)
    return False


def _validate_ambiguous_aliases_subset(
    aliases: list[str],
    ambiguous_aliases: list[str],
    file_name: str,
    record_index: int,
) -> None:
    alias_keys = {_normalize_alias(alias) for alias in aliases}
    for ambiguous_alias in ambiguous_aliases:
        if _normalize_alias(ambiguous_alias) not in alias_keys:
            raise QgisImportError(
                f"{file_name}:{record_index} ambiguous_aliases must also appear in aliases."
            )


def _required_file(input_dir: Path, file_name: str) -> Path:
    path = input_dir / file_name
    if not path.exists():
        raise QgisImportError(f"Missing required QGIS export: {path}")
    return path


def _optional_file(input_dir: Path, file_name: str) -> Path | None:
    path = input_dir / file_name
    return path if path.exists() else None


def _required_text(
    properties: dict[str, Any],
    key: str,
    file_name: str,
    record_index: int,
) -> str:
    value = properties.get(key)
    if value is None or str(value).strip() == "":
        raise QgisImportError(f"{file_name}:{record_index} is missing required field {key}.")
    return str(value).strip()


def _required_number(
    properties: dict[str, Any],
    key: str,
    file_name: str,
    record_index: int,
) -> float:
    value = _optional_number(properties, key)
    if value is None:
        raise QgisImportError(f"{file_name}:{record_index} is missing numeric field {key}.")
    return value


def _optional_number(properties: dict[str, Any], key: str) -> float | None:
    value = properties.get(key)
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise QgisImportError(f"Field {key} must be numeric; got {value!r}.") from exc


def _required_aliases(
    properties: dict[str, Any],
    file_name: str,
    record_index: int,
) -> list[str]:
    aliases = _aliases(properties.get("aliases"))
    if not aliases:
        raise QgisImportError(f"{file_name}:{record_index} is missing required field aliases.")
    return aliases


def _required_road_modes(
    properties: dict[str, Any],
    file_name: str,
    record_index: int,
) -> list[str]:
    modes = _string_list(properties.get("modes"), field_name="modes")
    if not modes:
        raise QgisImportError(f"{file_name}:{record_index} is missing required field modes.")
    unsupported = sorted(set(modes) - SUPPORTED_ROAD_MODES)
    if unsupported:
        raise QgisImportError(
            f"{file_name}:{record_index} has unsupported road modes: {', '.join(unsupported)}."
        )
    return sorted(dict.fromkeys(modes))


def _optional_bool(value: Any, *, default: bool) -> bool:
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"true", "1", "yes", "y"}:
        return True
    if text in {"false", "0", "no", "n"}:
        return False
    raise QgisImportError(f"Boolean field must be true/false; got {value!r}.")


def _first_present(properties: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in properties and properties.get(key) != "":
            return properties.get(key)
    return None


def _aliases(value: Any) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return [str(alias).strip() for alias in value if str(alias).strip()]
    text = str(value).strip()
    if text.startswith("["):
        parsed = json.loads(text)
        if not isinstance(parsed, list):
            raise QgisImportError("aliases JSON must be an array.")
        return [str(alias).strip() for alias in parsed if str(alias).strip()]
    return [alias.strip() for alias in text.split("|") if alias.strip()]


def _string_list(value: Any, *, field_name: str) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    if text.startswith("["):
        parsed = json.loads(text)
        if not isinstance(parsed, list):
            raise QgisImportError(f"{field_name} JSON must be an array.")
        return [str(item).strip() for item in parsed if str(item).strip()]
    separator = "|" if "|" in text else ","
    return [item.strip() for item in text.split(separator) if item.strip()]


def _normalize_alias(value: str) -> str:
    text = re.sub(r"[^a-z0-9]+", " ", value.lower())
    return re.sub(r"\s+", " ", text).strip()


def _generated_at(
    source_manifest: dict[str, Any],
    *record_groups: list[dict[str, Any]],
) -> str:
    configured = source_manifest.get("generated_at") or source_manifest.get("generated_timestamp")
    if configured:
        return str(configured)
    version = str(source_manifest.get("version") or _latest_source_version(*record_groups))
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", version):
        return f"{version}T00:00:00+00:00"
    return "1970-01-01T00:00:00+00:00"


def _latest_source_version(*record_groups: list[dict[str, Any]]) -> str:
    versions = [
        str(record["source_version"])
        for records in record_groups
        for record in records
        if record.get("source_version")
    ]
    return max(versions) if versions else "1970-01-01"


def _count_by(records: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for record in records:
        value = str(record.get(key) or "unknown")
        counts[value] = counts.get(value, 0) + 1
    return {value: counts[value] for value in sorted(counts)}


def _road_network_summary(
    road_nodes: list[dict[str, Any]],
    road_edges: list[dict[str, Any]],
) -> dict[str, Any]:
    mode_coverage = _road_mode_coverage(road_edges)
    source_version = _latest_source_version(road_nodes, road_edges)
    validation_status = "passed" if road_nodes or road_edges else "not_provided"
    return {
        "node_count": len(road_nodes),
        "edge_count": len(road_edges),
        "connected_component_count": _road_connected_component_count(road_nodes, road_edges),
        "connected_component_count_by_mode": {
            mode: _road_connected_component_count(road_nodes, road_edges, mode=mode)
            for mode in sorted(mode_coverage)
        },
        "mode_coverage": mode_coverage,
        "source_version": source_version,
        "validation_status": validation_status,
    }


def _place_route_node_summary(
    place_route_nodes: list[dict[str, Any]],
    source_manifest: dict[str, Any],
) -> dict[str, Any]:
    return {
        "snap_count": len(place_route_nodes),
        "mode_coverage": _count_by(place_route_nodes, "mode"),
        "approximate_snap_count": sum(
            1 for snap in place_route_nodes if bool(snap.get("approximate", False))
        ),
        "snap_distance_threshold_m": _snap_distance_threshold_m(source_manifest),
        "source_version": _latest_source_version(place_route_nodes),
        "validation_status": "passed" if place_route_nodes else "not_provided",
    }


def _snap_distance_threshold_m(source_manifest: dict[str, Any]) -> float:
    configured = (
        source_manifest.get("place_route_node_snap_distance_threshold_m")
        or source_manifest.get("snap_distance_threshold_m")
    )
    if configured is None or configured == "":
        return DEFAULT_SNAP_DISTANCE_THRESHOLD_M
    try:
        threshold = float(configured)
    except (TypeError, ValueError) as exc:
        raise QgisImportError(
            f"snap_distance_threshold_m must be numeric; got {configured!r}."
        ) from exc
    if threshold <= 0:
        raise QgisImportError(
            f"snap_distance_threshold_m must be positive; got {threshold}."
        )
    return threshold


def _road_mode_coverage(road_edges: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for edge in road_edges:
        for mode in edge.get("modes", ()):
            counts[str(mode)] = counts.get(str(mode), 0) + 1
    return {mode: counts[mode] for mode in sorted(counts)}


def _road_connected_component_count(
    road_nodes: list[dict[str, Any]],
    road_edges: list[dict[str, Any]],
    *,
    mode: str | None = None,
) -> int:
    node_ids = {str(node["node_id"]) for node in road_nodes}
    if not node_ids:
        return 0
    adjacency: dict[str, set[str]] = {node_id: set() for node_id in node_ids}
    for edge in road_edges:
        if mode is not None and mode not in edge.get("modes", ()):
            continue
        from_node_id = str(edge["from_node_id"])
        to_node_id = str(edge["to_node_id"])
        if from_node_id not in adjacency or to_node_id not in adjacency:
            continue
        adjacency[from_node_id].add(to_node_id)
        adjacency[to_node_id].add(from_node_id)

    seen: set[str] = set()
    component_count = 0
    for node_id in sorted(node_ids):
        if node_id in seen:
            continue
        component_count += 1
        stack = [node_id]
        seen.add(node_id)
        while stack:
            current = stack.pop()
            for neighbor in adjacency[current]:
                if neighbor in seen:
                    continue
                seen.add(neighbor)
                stack.append(neighbor)
    return component_count


def _write_jsonl(path: Path, records: Iterable[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True))
            handle.write("\n")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    raise SystemExit(main())
