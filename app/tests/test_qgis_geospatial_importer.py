import json

import pytest

from app.pipeline_v2.qgis_geospatial_importer import QgisImportError, import_qgis_exports


def test_qgis_export_importer_generates_runtime_artifacts(tmp_path):
    input_dir = tmp_path / "qgis_exports"
    output_dir = tmp_path / "runtime"
    input_dir.mkdir()
    _write_json(
        input_dir / "places.geojson",
        {
            "type": "FeatureCollection",
            "features": [
                _place_feature(
                    "au-act-canberra",
                    "Canberra",
                    ["canberra", "canberra act"],
                    "city",
                    "AU-ACT",
                    149.131,
                    -35.2809,
                ),
                _place_feature(
                    "au-nsw-sydney",
                    "Sydney",
                    ["sydney", "sydney nsw"],
                    "city",
                    "AU-NSW",
                    151.2093,
                    -33.8688,
                ),
            ],
        },
    )
    _write_json(
        input_dir / "route_network_edges.geojson",
        {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [[149.131, -35.2809], [151.2093, -33.8688]],
                    },
                    "properties": {
                        "origin_place_id": "au-act-canberra",
                        "destination_place_id": "au-nsw-sydney",
                        "mode": "car_ride",
                        "distance_km": 286.0,
                        "distance_source": "qgis_route_network_intercity_road",
                        "confidence": 0.82,
                        "source_version": "2026-06-01",
                        "bidirectional": True,
                    },
                }
            ],
        },
    )
    (input_dir / "electricity_regions.csv").write_text(
        "\n".join(
            [
                "region,region_name,country,factor_region,fallback_region,aliases,source,source_version",
                "AU-ACT,Australian Capital Territory,AU,AU-ACT,AU,act|australian capital territory,QGIS export test,2026-06-01",
                "AU-NSW,New South Wales,AU,AU-NSW,AU,nsw|new south wales,QGIS export test,2026-06-01",
            ]
        ),
        encoding="utf-8",
    )

    result = import_qgis_exports(input_dir, output_dir)

    assert result.place_count == 2
    assert result.route_edge_count == 1
    assert result.electricity_region_count == 2
    places = _read_jsonl(output_dir / "place_aliases.jsonl")
    edges = _read_jsonl(output_dir / "route_network_edges.jsonl")
    regions = _read_jsonl(output_dir / "electricity_regions.jsonl")
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))

    assert places[0]["place_id"] == "au-act-canberra"
    assert places[0]["aliases"] == ["canberra", "canberra act"]
    assert edges[0]["distance"] == 286.0
    assert edges[0]["distance_source"] == "qgis_route_network_intercity_road"
    assert regions[0]["region"] == "AU-ACT"
    assert manifest["artifact_counts"]["route_network_edges"] == 1


def test_qgis_export_importer_rejects_edges_with_unknown_place_refs(tmp_path):
    input_dir = tmp_path / "qgis_exports"
    output_dir = tmp_path / "runtime"
    input_dir.mkdir()
    _write_json(
        input_dir / "places.geojson",
        {
            "type": "FeatureCollection",
            "features": [
                _place_feature(
                    "au-act-canberra",
                    "Canberra",
                    ["canberra"],
                    "city",
                    "AU-ACT",
                    149.131,
                    -35.2809,
                )
            ],
        },
    )
    _write_json(
        input_dir / "route_network_edges.geojson",
        {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "LineString", "coordinates": []},
                    "properties": {
                        "origin_place_id": "au-act-canberra",
                        "destination_place_id": "au-nsw-sydney",
                        "mode": "car_ride",
                        "distance_km": 286.0,
                        "distance_source": "qgis_route_network_intercity_road",
                        "confidence": 0.82,
                        "source_version": "2026-06-01",
                    },
                }
            ],
        },
    )
    (input_dir / "electricity_regions.csv").write_text(
        "\n".join(
            [
                "region,region_name,country,factor_region,fallback_region,aliases,source,source_version",
                "AU-ACT,Australian Capital Territory,AU,AU-ACT,AU,act,QGIS export test,2026-06-01",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(QgisImportError, match="unknown destination_place_id"):
        import_qgis_exports(input_dir, output_dir)


def _place_feature(
    place_id,
    name,
    aliases,
    place_type,
    region,
    longitude,
    latitude,
):
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [longitude, latitude]},
        "properties": {
            "place_id": place_id,
            "name": name,
            "aliases": aliases,
            "place_type": place_type,
            "region": region,
            "source": "QGIS export test",
            "source_version": "2026-06-01",
        },
    }


def _write_json(path, payload):
    path.write_text(json.dumps(payload), encoding="utf-8")


def _read_jsonl(path):
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
