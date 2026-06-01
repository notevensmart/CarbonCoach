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
                    "au-act-civic",
                    "Civic",
                    ["civic", "canberra cbd"],
                    "cbd",
                    "AU-ACT",
                    149.1317,
                    -35.2816,
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
                _place_feature(
                    "au-nsw-surry-hills",
                    "Surry Hills",
                    ["surry hills", "surry hills nsw"],
                    "suburb",
                    "AU-NSW",
                    151.2123,
                    -33.8869,
                ),
                _place_feature(
                    "au-nsw-central-station",
                    "Central Station",
                    ["central station", "sydney central"],
                    "train_station",
                    "AU-NSW",
                    151.2070,
                    -33.8825,
                ),
                _place_feature(
                    "au-nsw-sydney-airport",
                    "Sydney Airport",
                    ["sydney airport", "kingsford smith airport"],
                    "airport",
                    "AU-NSW",
                    151.1772,
                    -33.9399,
                ),
                _place_feature(
                    "au-nsw-sydney-opera-house",
                    "Sydney Opera House",
                    ["sydney opera house", "opera house"],
                    "poi",
                    "AU-NSW",
                    151.2153,
                    -33.8568,
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

    assert result.place_count == 7
    assert result.route_edge_count == 1
    assert result.road_node_count == 0
    assert result.road_edge_count == 0
    assert result.electricity_region_count == 2
    places = _read_jsonl(output_dir / "place_aliases.jsonl")
    edges = _read_jsonl(output_dir / "route_network_edges.jsonl")
    regions = _read_jsonl(output_dir / "electricity_regions.jsonl")
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))

    assert places[0]["place_id"] == "au-act-canberra"
    assert places[0]["aliases"] == ["canberra", "canberra act"]
    assert {place["place_type"] for place in places} >= {
        "airport",
        "cbd",
        "city",
        "poi",
        "suburb",
        "train_station",
    }
    assert edges[0]["distance"] == 286.0
    assert edges[0]["distance_source"] == "qgis_route_network_intercity_road"
    assert regions[0]["region"] == "AU-ACT"
    assert manifest["generated_at"] == "2026-06-01T00:00:00+00:00"
    assert manifest["artifact_counts"]["route_network_edges"] == 1
    assert manifest["artifact_counts"]["road_network_nodes"] == 0
    assert manifest["artifact_counts"]["road_network_edges"] == 0
    assert manifest["place_counts"]["by_place_type"]["airport"] == 1
    assert manifest["validation"]["status"] == "passed"
    assert manifest["validation"]["places"]["status"] == "passed"
    assert manifest["validation"]["road_network"]["status"] == "not_provided"


def test_qgis_export_importer_generates_road_network_artifacts_and_manifest(tmp_path):
    input_dir = tmp_path / "qgis_exports"
    output_dir = tmp_path / "runtime"
    input_dir.mkdir()
    _write_json(
        input_dir / "places.geojson",
        {
            "type": "FeatureCollection",
            "features": [
                _place_feature(
                    "au-nsw-sydney",
                    "Sydney",
                    ["sydney"],
                    "city",
                    "AU-NSW",
                    151.2093,
                    -33.8688,
                )
            ],
        },
    )
    _write_json(
        input_dir / "road_network_nodes.geojson",
        {
            "type": "FeatureCollection",
            "features": [
                _road_node_feature("node-a", 151.0, -33.0),
                _road_node_feature("node-b", 151.1, -33.1),
                _road_node_feature("node-c", 151.2, -33.2),
                _road_node_feature("node-d", 144.9, -37.8),
                _road_node_feature("node-e", 144.95, -37.81),
            ],
        },
    )
    _write_json(
        input_dir / "road_network_edges.geojson",
        {
            "type": "FeatureCollection",
            "features": [
                _road_edge_feature(
                    "edge-a-b",
                    "node-a",
                    "node-b",
                    3.1,
                    ["car_ride", "rideshare"],
                    bidirectional=True,
                ),
                _road_edge_feature(
                    "edge-b-c",
                    "node-b",
                    "node-c",
                    4.2,
                    "car_ride",
                    bidirectional=False,
                ),
                _road_edge_feature(
                    "edge-d-e",
                    "node-d",
                    "node-e",
                    2.0,
                    "car_ride",
                    bidirectional=True,
                ),
            ],
        },
    )

    result = import_qgis_exports(input_dir, output_dir)

    nodes = _read_jsonl(output_dir / "road_network_nodes.jsonl")
    edges = _read_jsonl(output_dir / "road_network_edges.jsonl")
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))

    assert result.route_edge_count == 0
    assert result.road_node_count == 5
    assert result.road_edge_count == 3
    assert nodes[0] == {
        "latitude": -33.0,
        "longitude": 151.0,
        "node_id": "node-a",
        "source": "QGIS road graph test",
        "source_version": "2026-06-01",
    }
    assert "geometry" not in nodes[0]
    assert edges[0]["modes"] == ["car_ride", "rideshare"]
    assert edges[1]["bidirectional"] is False
    assert edges[1]["modes"] == ["car_ride"]
    assert manifest["artifact_counts"]["road_network_nodes"] == 5
    assert manifest["artifact_counts"]["road_network_edges"] == 3
    assert manifest["road_network"]["connected_component_count"] == 2
    assert manifest["road_network"]["mode_coverage"] == {"car_ride": 3, "rideshare": 1}
    assert manifest["road_network"]["source_version"] == "2026-06-01"
    assert manifest["road_network"]["validation_status"] == "passed"
    assert manifest["validation"]["road_network"]["status"] == "passed"


def test_qgis_export_importer_generates_place_route_node_snaps_and_manifest(tmp_path):
    input_dir = tmp_path / "qgis_exports"
    output_dir = tmp_path / "runtime"
    input_dir.mkdir()
    _write_json(
        input_dir / "places.geojson",
        {
            "type": "FeatureCollection",
            "features": [
                _place_feature(
                    "au-nsw-surry-hills",
                    "Surry Hills",
                    ["surry hills"],
                    "suburb",
                    "AU-NSW",
                    151.2123,
                    -33.8869,
                )
            ],
        },
    )
    _write_json(
        input_dir / "road_network_nodes.geojson",
        {
            "type": "FeatureCollection",
            "features": [
                _road_node_feature("node-car", 151.2120, -33.8870),
                _road_node_feature("node-rideshare", 151.2130, -33.8860),
            ],
        },
    )
    _write_place_route_nodes_csv(
        input_dir / "place_route_nodes.csv",
        [
            {
                "place_id": "au-nsw-surry-hills",
                "mode": "car_ride",
                "node_id": "node-car",
                "snap_distance_m": 40,
                "snap_confidence": 0.93,
                "snap_source": "QGIS snap test",
                "source_version": "2026-06-01",
            },
            {
                "place_id": "au-nsw-surry-hills",
                "mode": "rideshare",
                "node_id": "node-rideshare",
                "snap_distance_m": 30,
                "snap_confidence": 0.91,
                "snap_source": "QGIS snap test",
                "source_version": "2026-06-01",
            },
        ],
    )

    result = import_qgis_exports(input_dir, output_dir)

    snaps = _read_jsonl(output_dir / "place_route_nodes.jsonl")
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))

    assert result.place_route_node_count == 2
    assert snaps == [
        {
            "approximate": False,
            "mode": "car_ride",
            "node_id": "node-car",
            "place_id": "au-nsw-surry-hills",
            "snap_confidence": 0.93,
            "snap_distance_m": 40.0,
            "snap_source": "QGIS snap test",
            "source_version": "2026-06-01",
        },
        {
            "approximate": False,
            "mode": "rideshare",
            "node_id": "node-rideshare",
            "place_id": "au-nsw-surry-hills",
            "snap_confidence": 0.91,
            "snap_distance_m": 30.0,
            "snap_source": "QGIS snap test",
            "source_version": "2026-06-01",
        },
    ]
    assert manifest["artifact_counts"]["place_route_nodes"] == 2
    assert manifest["place_route_nodes"]["mode_coverage"] == {
        "car_ride": 1,
        "rideshare": 1,
    }
    assert manifest["place_route_nodes"]["snap_distance_threshold_m"] == 1000.0
    assert manifest["validation"]["place_route_nodes"]["status"] == "passed"


def test_qgis_export_importer_rejects_snap_with_unknown_place(tmp_path):
    input_dir = tmp_path / "qgis_exports"
    output_dir = tmp_path / "runtime"
    input_dir.mkdir()
    _write_json(
        input_dir / "places.geojson",
        {"type": "FeatureCollection", "features": [_minimal_place_feature()]},
    )
    _write_json(
        input_dir / "road_network_nodes.geojson",
        {"type": "FeatureCollection", "features": [_road_node_feature("node-a", 151.0, -33.0)]},
    )
    _write_place_route_nodes_csv(
        input_dir / "place_route_nodes.csv",
        [_place_route_node_row(place_id="au-nsw-missing", node_id="node-a")],
    )

    with pytest.raises(QgisImportError, match="unknown place_id"):
        import_qgis_exports(input_dir, output_dir)


def test_qgis_export_importer_rejects_snap_with_unknown_node(tmp_path):
    input_dir = tmp_path / "qgis_exports"
    output_dir = tmp_path / "runtime"
    input_dir.mkdir()
    _write_json(
        input_dir / "places.geojson",
        {"type": "FeatureCollection", "features": [_minimal_place_feature()]},
    )
    _write_json(
        input_dir / "road_network_nodes.geojson",
        {"type": "FeatureCollection", "features": [_road_node_feature("node-a", 151.0, -33.0)]},
    )
    _write_place_route_nodes_csv(
        input_dir / "place_route_nodes.csv",
        [_place_route_node_row(place_id="au-nsw-sydney", node_id="node-missing")],
    )

    with pytest.raises(QgisImportError, match="unknown node_id"):
        import_qgis_exports(input_dir, output_dir)


def test_qgis_export_importer_rejects_excessive_snap_distance_without_approximate_marker(
    tmp_path,
):
    input_dir = tmp_path / "qgis_exports"
    output_dir = tmp_path / "runtime"
    input_dir.mkdir()
    _write_json(
        input_dir / "places.geojson",
        {"type": "FeatureCollection", "features": [_minimal_place_feature()]},
    )
    _write_json(
        input_dir / "road_network_nodes.geojson",
        {"type": "FeatureCollection", "features": [_road_node_feature("node-a", 151.0, -33.0)]},
    )
    _write_place_route_nodes_csv(
        input_dir / "place_route_nodes.csv",
        [
            _place_route_node_row(
                place_id="au-nsw-sydney",
                node_id="node-a",
                snap_distance_m=1200,
            )
        ],
    )

    with pytest.raises(QgisImportError, match="exceeds configured threshold"):
        import_qgis_exports(input_dir, output_dir)


def test_qgis_export_importer_allows_explicit_approximate_snap_above_threshold(tmp_path):
    input_dir = tmp_path / "qgis_exports"
    output_dir = tmp_path / "runtime"
    input_dir.mkdir()
    _write_json(
        input_dir / "places.geojson",
        {"type": "FeatureCollection", "features": [_minimal_place_feature()]},
    )
    _write_json(
        input_dir / "road_network_nodes.geojson",
        {"type": "FeatureCollection", "features": [_road_node_feature("node-a", 151.0, -33.0)]},
    )
    _write_place_route_nodes_csv(
        input_dir / "place_route_nodes.csv",
        [
            _place_route_node_row(
                place_id="au-nsw-sydney",
                node_id="node-a",
                snap_distance_m=1200,
                approximate=True,
            )
        ],
    )

    import_qgis_exports(input_dir, output_dir)
    snaps = _read_jsonl(output_dir / "place_route_nodes.jsonl")

    assert snaps[0]["approximate"] is True


def test_qgis_export_importer_rejects_road_edges_with_unknown_node_refs(tmp_path):
    input_dir = tmp_path / "qgis_exports"
    output_dir = tmp_path / "runtime"
    input_dir.mkdir()
    _write_json(
        input_dir / "places.geojson",
        {"type": "FeatureCollection", "features": [_minimal_place_feature()]},
    )
    _write_json(
        input_dir / "road_network_nodes.geojson",
        {"type": "FeatureCollection", "features": [_road_node_feature("node-a", 151.0, -33.0)]},
    )
    _write_json(
        input_dir / "road_network_edges.geojson",
        {
            "type": "FeatureCollection",
            "features": [
                _road_edge_feature(
                    "edge-a-missing",
                    "node-a",
                    "node-missing",
                    3.1,
                    "car_ride",
                )
            ],
        },
    )

    with pytest.raises(QgisImportError, match="unknown to_node_id"):
        import_qgis_exports(input_dir, output_dir)


@pytest.mark.parametrize(
    ("distance", "expected_error"),
    [
        (0, "distance_km must be positive"),
        (-1, "distance_km must be positive"),
        ("far", "Field distance_km must be numeric"),
    ],
)
def test_qgis_export_importer_rejects_invalid_road_edge_distance(
    tmp_path,
    distance,
    expected_error,
):
    input_dir = tmp_path / "qgis_exports"
    output_dir = tmp_path / "runtime"
    input_dir.mkdir()
    _write_json(
        input_dir / "places.geojson",
        {"type": "FeatureCollection", "features": [_minimal_place_feature()]},
    )
    _write_json(
        input_dir / "road_network_nodes.geojson",
        {
            "type": "FeatureCollection",
            "features": [
                _road_node_feature("node-a", 151.0, -33.0),
                _road_node_feature("node-b", 151.1, -33.1),
            ],
        },
    )
    _write_json(
        input_dir / "road_network_edges.geojson",
        {
            "type": "FeatureCollection",
            "features": [
                _road_edge_feature(
                    "edge-a-b",
                    "node-a",
                    "node-b",
                    distance,
                    "car_ride",
                )
            ],
        },
    )

    with pytest.raises(QgisImportError, match=expected_error):
        import_qgis_exports(input_dir, output_dir)


def test_qgis_export_importer_rejects_unsupported_road_modes(tmp_path):
    input_dir = tmp_path / "qgis_exports"
    output_dir = tmp_path / "runtime"
    input_dir.mkdir()
    _write_json(
        input_dir / "places.geojson",
        {"type": "FeatureCollection", "features": [_minimal_place_feature()]},
    )
    _write_json(
        input_dir / "road_network_nodes.geojson",
        {
            "type": "FeatureCollection",
            "features": [
                _road_node_feature("node-a", 151.0, -33.0),
                _road_node_feature("node-b", 151.1, -33.1),
            ],
        },
    )
    _write_json(
        input_dir / "road_network_edges.geojson",
        {
            "type": "FeatureCollection",
            "features": [
                _road_edge_feature(
                    "edge-a-b",
                    "node-a",
                    "node-b",
                    3.1,
                    ["car_ride", "train_ride"],
                )
            ],
        },
    )

    with pytest.raises(QgisImportError, match="unsupported road modes: train_ride"):
        import_qgis_exports(input_dir, output_dir)


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


def test_qgis_export_importer_rejects_missing_required_place_fields(tmp_path):
    input_dir = tmp_path / "qgis_exports"
    output_dir = tmp_path / "runtime"
    input_dir.mkdir()
    _write_json(
        input_dir / "places.geojson",
        {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [151.2093, -33.8688]},
                    "properties": {
                        "place_id": "au-nsw-sydney",
                        "name": "Sydney",
                        "place_type": "city",
                        "region": "AU-NSW",
                        "source": "QGIS export test",
                        "source_version": "2026-06-01",
                    },
                }
            ],
        },
    )

    with pytest.raises(QgisImportError, match="aliases"):
        import_qgis_exports(input_dir, output_dir)


def test_qgis_export_importer_rejects_missing_coordinates(tmp_path):
    input_dir = tmp_path / "qgis_exports"
    output_dir = tmp_path / "runtime"
    input_dir.mkdir()
    feature = _place_feature(
        "au-nsw-sydney",
        "Sydney",
        ["sydney"],
        "city",
        "AU-NSW",
        151.2093,
        -33.8688,
    )
    feature["geometry"] = None
    _write_json(
        input_dir / "places.geojson",
        {"type": "FeatureCollection", "features": [feature]},
    )

    with pytest.raises(QgisImportError, match="latitude/longitude"):
        import_qgis_exports(input_dir, output_dir)


def test_qgis_export_importer_rejects_duplicate_place_id(tmp_path):
    input_dir = tmp_path / "qgis_exports"
    output_dir = tmp_path / "runtime"
    input_dir.mkdir()
    _write_json(
        input_dir / "places.geojson",
        {
            "type": "FeatureCollection",
            "features": [
                _place_feature(
                    "au-nsw-springfield",
                    "Springfield NSW",
                    ["springfield nsw"],
                    "locality",
                    "AU-NSW",
                    151.3688,
                    -33.4284,
                ),
                _place_feature(
                    "au-nsw-springfield",
                    "Springfield Duplicate",
                    ["springfield duplicate"],
                    "locality",
                    "AU-NSW",
                    151.3689,
                    -33.4285,
                ),
            ],
        },
    )

    with pytest.raises(QgisImportError, match="duplicate place_id"):
        import_qgis_exports(input_dir, output_dir)


def test_qgis_export_importer_supports_intentional_ambiguous_alias(tmp_path):
    input_dir = tmp_path / "qgis_exports"
    output_dir = tmp_path / "runtime"
    input_dir.mkdir()
    _write_json(
        input_dir / "places.geojson",
        {
            "type": "FeatureCollection",
            "features": [
                _place_feature(
                    "au-nsw-springfield",
                    "Springfield NSW",
                    ["springfield", "springfield nsw"],
                    "locality",
                    "AU-NSW",
                    151.3688,
                    -33.4284,
                    ambiguous_aliases=["springfield"],
                ),
                _place_feature(
                    "au-qld-springfield",
                    "Springfield QLD",
                    ["springfield", "springfield qld"],
                    "suburb",
                    "AU-QLD",
                    152.9177,
                    -27.6532,
                    ambiguous_aliases=["springfield"],
                ),
            ],
        },
    )

    result = import_qgis_exports(input_dir, output_dir)
    places = _read_jsonl(output_dir / "place_aliases.jsonl")
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))

    assert result.place_count == 2
    assert places[0]["ambiguous_aliases"] == ["springfield"]
    assert manifest["validation"]["places"]["ambiguous_aliases"] == [
        {
            "alias": "springfield",
            "normalized_alias": "springfield",
            "place_ids": ["au-nsw-springfield", "au-qld-springfield"],
            "place_names": ["Springfield NSW", "Springfield QLD"],
        }
    ]


def test_qgis_export_importer_rejects_accidental_duplicate_alias(tmp_path):
    input_dir = tmp_path / "qgis_exports"
    output_dir = tmp_path / "runtime"
    input_dir.mkdir()
    _write_json(
        input_dir / "places.geojson",
        {
            "type": "FeatureCollection",
            "features": [
                _place_feature(
                    "au-nsw-springfield",
                    "Springfield NSW",
                    ["springfield", "springfield nsw"],
                    "locality",
                    "AU-NSW",
                    151.3688,
                    -33.4284,
                ),
                _place_feature(
                    "au-qld-springfield",
                    "Springfield QLD",
                    ["springfield", "springfield qld"],
                    "suburb",
                    "AU-QLD",
                    152.9177,
                    -27.6532,
                ),
            ],
        },
    )

    with pytest.raises(QgisImportError, match="duplicate aliases"):
        import_qgis_exports(input_dir, output_dir)


def test_qgis_export_importer_outputs_are_stable_across_runs(tmp_path):
    input_dir = tmp_path / "qgis_exports"
    first_output_dir = tmp_path / "runtime-one"
    second_output_dir = tmp_path / "runtime-two"
    input_dir.mkdir()
    _write_json(
        input_dir / "places.geojson",
        {
            "type": "FeatureCollection",
            "features": [
                _place_feature(
                    "au-vic-melbourne-cbd",
                    "Melbourne CBD",
                    ["melbourne", "melbourne cbd"],
                    "cbd",
                    "AU-VIC",
                    144.9631,
                    -37.8136,
                ),
            ],
        },
    )

    import_qgis_exports(input_dir, first_output_dir)
    import_qgis_exports(input_dir, second_output_dir)

    assert (first_output_dir / "place_aliases.jsonl").read_text(encoding="utf-8") == (
        second_output_dir / "place_aliases.jsonl"
    ).read_text(encoding="utf-8")
    assert (first_output_dir / "manifest.json").read_text(encoding="utf-8") == (
        second_output_dir / "manifest.json"
    ).read_text(encoding="utf-8")


def _place_feature(
    place_id,
    name,
    aliases,
    place_type,
    region,
    longitude,
    latitude,
    ambiguous_aliases=None,
):
    properties = {
        "place_id": place_id,
        "name": name,
        "aliases": aliases,
        "place_type": place_type,
        "region": region,
        "source": "QGIS export test",
        "source_version": "2026-06-01",
    }
    if ambiguous_aliases is not None:
        properties["ambiguous_aliases"] = ambiguous_aliases
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [longitude, latitude]},
        "properties": properties,
    }


def _minimal_place_feature():
    return _place_feature(
        "au-nsw-sydney",
        "Sydney",
        ["sydney"],
        "city",
        "AU-NSW",
        151.2093,
        -33.8688,
    )


def _road_node_feature(node_id, longitude, latitude):
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [longitude, latitude]},
        "properties": {
            "node_id": node_id,
            "source": "QGIS road graph test",
            "source_version": "2026-06-01",
        },
    }


def _road_edge_feature(
    edge_id,
    from_node_id,
    to_node_id,
    distance_km,
    modes,
    *,
    bidirectional=True,
):
    return {
        "type": "Feature",
        "geometry": {"type": "LineString", "coordinates": []},
        "properties": {
            "edge_id": edge_id,
            "from_node_id": from_node_id,
            "to_node_id": to_node_id,
            "distance_km": distance_km,
            "modes": modes,
            "bidirectional": bidirectional,
            "source": "QGIS road graph test",
            "confidence": 0.87,
            "source_version": "2026-06-01",
        },
    }


def _place_route_node_row(
    *,
    place_id,
    node_id,
    mode="car_ride",
    snap_distance_m=40,
    snap_confidence=0.93,
    snap_source="QGIS snap test",
    source_version="2026-06-01",
    approximate=False,
):
    return {
        "place_id": place_id,
        "mode": mode,
        "node_id": node_id,
        "snap_distance_m": snap_distance_m,
        "snap_confidence": snap_confidence,
        "snap_source": snap_source,
        "source_version": source_version,
        "approximate": str(approximate).lower(),
    }


def _write_place_route_nodes_csv(path, rows):
    fields = [
        "place_id",
        "mode",
        "node_id",
        "snap_distance_m",
        "snap_confidence",
        "snap_source",
        "source_version",
        "approximate",
    ]
    lines = [",".join(fields)]
    for row in rows:
        lines.append(",".join(str(row.get(field, "")) for field in fields))
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_json(path, payload):
    path.write_text(json.dumps(payload), encoding="utf-8")


def _read_jsonl(path):
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
