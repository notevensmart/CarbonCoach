from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Iterable


@dataclass(frozen=True)
class QgisImportResult:
    place_count: int
    route_edge_count: int
    route_distance_count: int
    electricity_region_count: int
    output_dir: Path


class QgisImportError(ValueError):
    """Raised when QGIS exports are missing required app-ready fields."""


def import_qgis_exports(input_dir: Path, output_dir: Path) -> QgisImportResult:
    input_dir = input_dir.resolve()
    output_dir = output_dir.resolve()
    if not input_dir.exists():
        raise QgisImportError(f"QGIS export directory does not exist: {input_dir}")

    places = _load_places(input_dir)
    place_ids = {record["place_id"] for record in places}
    route_edges = _load_route_edges(input_dir, place_ids)
    route_distances = _load_route_distances(input_dir, place_ids)
    electricity_regions = _load_electricity_regions(input_dir)

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_jsonl(output_dir / "place_aliases.jsonl", places)
    _write_jsonl(output_dir / "route_network_edges.jsonl", route_edges)
    _write_jsonl(output_dir / "route_distances.jsonl", route_distances)
    _write_jsonl(output_dir / "electricity_regions.jsonl", electricity_regions)
    _write_manifest(
        input_dir,
        output_dir,
        place_count=len(places),
        route_edge_count=len(route_edges),
        route_distance_count=len(route_distances),
        electricity_region_count=len(electricity_regions),
    )
    return QgisImportResult(
        place_count=len(places),
        route_edge_count=len(route_edges),
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
        f"{result.route_distance_count} exact route distances, "
        f"{result.electricity_region_count} electricity regions "
        f"to {result.output_dir}"
    )
    return 0


def _load_places(input_dir: Path) -> list[dict[str, Any]]:
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
        records.append(
            {
                "place_id": _required_text(properties, "place_id", "places.geojson", feature_index),
                "name": _required_text(properties, "name", "places.geojson", feature_index),
                "aliases": _aliases(properties.get("aliases")),
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
        )
    return sorted(records, key=lambda record: record["place_id"])


def _load_route_edges(input_dir: Path, place_ids: set[str]) -> list[dict[str, Any]]:
    path = _required_file(input_dir, "route_network_edges.geojson")
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
    path = _required_file(input_dir, "electricity_regions.csv")
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


def _write_manifest(
    input_dir: Path,
    output_dir: Path,
    *,
    place_count: int,
    route_edge_count: int,
    route_distance_count: int,
    electricity_region_count: int,
) -> None:
    source_manifest = _load_source_manifest(input_dir)
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
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
            "route_distances": route_distance_count,
            "electricity_regions": electricity_region_count,
        },
        "artifacts": [
            {"path": "place_aliases.jsonl", "schema": "place_alias_record"},
            {"path": "route_network_edges.jsonl", "schema": "route_network_edge"},
            {"path": "route_distances.jsonl", "schema": "route_distance_record"},
            {"path": "electricity_regions.jsonl", "schema": "electricity_region_record"},
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
