import time

import pytest

from app.domain.geospatial import (
    LocalElectricityRegionResolver,
    LocalPlaceResolver,
    LocalRouteDistanceProvider,
    PlaceRouteNodeSnap,
    PlaceRecord,
    RoadNetworkEdge,
    RoadNetworkGraph,
    RoadNetworkNode,
    RouteDistanceRecord,
    load_place_route_node_snaps,
    load_road_network_edges,
    load_road_network_nodes,
)
from app.pipeline_v2.location_enricher import LocationEnricher
from app.pipeline_v2.pipeline import CarbonPipelineV2


MAJOR_AUSTRALIAN_CITY_ALIAS_CASES = [
    ("Sydney", "au-nsw-sydney-cbd", "AU-NSW"),
    ("Sydney NSW", "au-nsw-sydney-cbd", "AU-NSW"),
    ("Melbourne", "au-vic-melbourne", "AU-VIC"),
    ("Melb", "au-vic-melbourne", "AU-VIC"),
    ("Brisbane", "au-qld-brisbane", "AU-QLD"),
    ("Bris", "au-qld-brisbane", "AU-QLD"),
    ("Perth", "au-wa-perth", "AU-WA"),
    ("Adelaide", "au-sa-adelaide", "AU-SA"),
    ("Canberra", "au-act-canberra", "AU-ACT"),
    ("Hobart", "au-tas-hobart", "AU-TAS"),
    ("Darwin", "au-nt-darwin", "AU-NT"),
    ("Gold Coast", "au-qld-gold-coast", "AU-QLD"),
    ("Surfers Paradise", "au-qld-gold-coast", "AU-QLD"),
    ("Sunshine Coast", "au-qld-sunshine-coast", "AU-QLD"),
    ("Maroochydore", "au-qld-sunshine-coast", "AU-QLD"),
    ("Newcastle", "au-nsw-newcastle", "AU-NSW"),
    ("Central Coast", "au-nsw-central-coast", "AU-NSW"),
    ("Gosford", "au-nsw-central-coast", "AU-NSW"),
    ("Wollongong", "au-nsw-wollongong", "AU-NSW"),
    ("Geelong", "au-vic-geelong", "AU-VIC"),
    ("Townsville", "au-qld-townsville", "AU-QLD"),
    ("Cairns", "au-qld-cairns", "AU-QLD"),
    ("Toowoomba", "au-qld-toowoomba", "AU-QLD"),
    ("Ballarat", "au-vic-ballarat", "AU-VIC"),
    ("Bendigo", "au-vic-bendigo", "AU-VIC"),
    ("Launceston", "au-tas-launceston", "AU-TAS"),
    ("Mackay", "au-qld-mackay", "AU-QLD"),
    ("Rockhampton", "au-qld-rockhampton", "AU-QLD"),
    ("Albury", "au-nsw-albury", "AU-NSW"),
    ("Wodonga", "au-vic-wodonga", "AU-VIC"),
]


TICKET_13_REQUIRED_PLACE_CASES = [
    ("Surry Hills", "au-nsw-surry-hills", "suburb", "AU-NSW"),
    ("Newtown", "au-nsw-newtown", "suburb", "AU-NSW"),
    ("Melbourne CBD", "au-vic-melbourne-cbd", "cbd", "AU-VIC"),
    ("Fitzroy", "au-vic-fitzroy", "suburb", "AU-VIC"),
    ("Brisbane Airport", "au-qld-brisbane-airport", "airport", "AU-QLD"),
    ("Sydney Airport", "au-nsw-sydney-airport", "airport", "AU-NSW"),
    ("Central Station", "au-nsw-central", "train_station", "AU-NSW"),
    ("Parramatta", "au-nsw-parramatta", "suburb", "AU-NSW"),
    ("Bondi", "au-nsw-bondi", "suburb", "AU-NSW"),
]


def test_place_alias_resolution_and_unknown_place():
    resolver = LocalPlaceResolver()

    resolved = resolver.resolve_place("Parramatta")
    city = resolver.resolve_place("Sydney")
    capital = resolver.resolve_place("Canberra")
    unknown = resolver.resolve_place("Unknown Place")

    assert resolved.status == "resolved"
    assert resolved.record.place_id == "au-nsw-parramatta"
    assert resolved.record.region == "AU-NSW"
    assert city.status == "resolved"
    assert city.record.place_id == "au-nsw-sydney-cbd"
    assert capital.status == "resolved"
    assert capital.record.place_id == "au-act-canberra"
    assert unknown.status == "unknown"


@pytest.mark.parametrize(
    ("surface", "expected_place_id", "expected_place_type", "expected_region"),
    TICKET_13_REQUIRED_PLACE_CASES,
)
def test_ticket_13_required_gazetteer_aliases_resolve(
    surface,
    expected_place_id,
    expected_place_type,
    expected_region,
):
    result = LocalPlaceResolver().resolve_place(surface)

    assert result.status == "resolved"
    assert result.record.place_id == expected_place_id
    assert result.record.place_type == expected_place_type
    assert result.record.region == expected_region
    assert result.match_type == "exact_alias"


@pytest.mark.parametrize(
    ("surface", "expected_place_id", "expected_region"),
    MAJOR_AUSTRALIAN_CITY_ALIAS_CASES,
)
def test_major_australian_city_aliases_resolve(surface, expected_place_id, expected_region):
    result = LocalPlaceResolver().resolve_place(surface)

    assert result.status == "resolved"
    assert result.record.place_id == expected_place_id
    assert result.record.region == expected_region
    assert result.match_type == "exact_alias"


def test_place_alias_ambiguity_is_typed():
    resolver = LocalPlaceResolver()

    result = resolver.resolve_place("Springfield")

    assert result.status == "ambiguous"
    assert sorted(record.region for record in result.candidates) == ["AU-NSW", "AU-QLD"]


def test_state_qualified_ambiguous_alias_resolves_specific_place():
    resolver = LocalPlaceResolver()

    result = resolver.resolve_place("Springfield QLD")

    assert result.status == "resolved"
    assert result.record.place_id == "au-qld-springfield"
    assert result.record.region == "AU-QLD"


def test_state_hint_disambiguates_alias_without_state_specific_alias():
    resolver = LocalPlaceResolver(
        records=[
            _place_record("au-nsw-springfield", "Springfield", "AU-NSW"),
            _place_record("au-qld-springfield", "Springfield", "AU-QLD"),
        ]
    )

    result = resolver.resolve_place("Springfield in Queensland")

    assert result.status == "resolved"
    assert result.record.place_id == "au-qld-springfield"
    assert result.record.region == "AU-QLD"
    assert result.matched_alias == "springfield"
    assert result.match_type == "exact_alias"


def test_unknown_state_hint_does_not_choose_different_state_place():
    resolver = LocalPlaceResolver(
        records=[
            _place_record("au-nsw-springfield", "Springfield", "AU-NSW"),
            _place_record("au-qld-springfield", "Springfield", "AU-QLD"),
        ]
    )

    result = resolver.resolve_place("Springfield WA")

    assert result.status == "unknown"


@pytest.mark.parametrize("surface", ["WA", "SA", "NT", "CBD"])
def test_short_administrative_tokens_are_not_fuzzy_matched(surface):
    result = LocalPlaceResolver().resolve_place(surface)

    assert result.status == "unknown"
    assert result.match_type is None


def test_place_resolver_fuzzy_matches_single_clear_typo():
    resolver = LocalPlaceResolver()

    result = resolver.resolve_place("Chastwood")

    assert result.status == "resolved"
    assert result.record.place_id == "au-nsw-chatswood"
    assert result.match_type == "fuzzy_alias"
    assert result.confidence < 0.95


def test_place_resolver_fuzzy_typo_can_still_be_ambiguous():
    resolver = LocalPlaceResolver()

    result = resolver.resolve_place("Springfeld")

    assert result.status == "ambiguous"
    assert sorted(record.region for record in result.candidates) == ["AU-NSW", "AU-QLD"]


def test_state_hint_disambiguates_fuzzy_alias_match():
    resolver = LocalPlaceResolver(
        records=[
            _place_record("au-nsw-springfield", "Springfield", "AU-NSW"),
            _place_record("au-qld-springfield", "Springfield", "AU-QLD"),
        ]
    )

    result = resolver.resolve_place("Springfeld QLD")

    assert result.status == "resolved"
    assert result.record.place_id == "au-qld-springfield"
    assert result.match_type == "fuzzy_alias"


def test_low_confidence_place_typo_is_not_guessed():
    resolver = LocalPlaceResolver()

    result = resolver.resolve_place("Surry Hzzzz")

    assert result.status == "unknown"


def test_exact_route_cache_distance_is_mode_aware():
    places = LocalPlaceResolver()
    provider = LocalRouteDistanceProvider(
        records=[
            RouteDistanceRecord(
                origin_place_id="au-nsw-redfern",
                destination_place_id="au-nsw-chatswood",
                mode="train_ride",
                distance=13.8,
                distance_unit="km",
                distance_source="qgis_gtfs_route_shape",
                confidence=0.85,
                source_version="2026-06-01",
            )
        ],
        network_edges=[],
    )
    origin = places.resolve_place("Redfern").record
    destination = places.resolve_place("Chatswood").record

    result = provider.distance(origin, destination, "train_ride")

    assert result.status == "resolved"
    assert result.exact is True
    assert result.distance == 13.8
    assert result.distance_source == "qgis_gtfs_route_shape"
    assert result.confidence == 0.85


def test_route_network_derives_shortest_path_from_qgis_edges():
    places = LocalPlaceResolver()
    provider = LocalRouteDistanceProvider()
    origin = places.resolve_place("Parramatta").record
    destination = places.resolve_place("Bondi").record

    result = provider.distance(origin, destination, "car_ride")

    assert result.status == "resolved"
    assert result.exact is True
    assert result.distance == 31.2
    assert result.distance_source == "qgis_route_network_road"
    assert result.route_path_place_ids == (
        "au-nsw-parramatta",
        "au-nsw-strathfield",
        "au-nsw-sydney-cbd",
        "au-nsw-bondi",
    )


def test_route_network_supports_intercity_city_nodes():
    places = LocalPlaceResolver()
    provider = LocalRouteDistanceProvider()
    origin = places.resolve_place("Sydney").record
    destination = places.resolve_place("Canberra").record

    result = provider.distance(origin, destination, "car_ride")

    assert result.status == "resolved"
    assert result.exact is True
    assert result.distance == 286.0
    assert result.distance_source == "qgis_route_network_intercity_road"
    assert result.route_path_place_ids == (
        "au-nsw-sydney-cbd",
        "au-act-canberra",
    )


def test_road_network_runtime_artifacts_load_without_geojson_geometry():
    nodes = load_road_network_nodes()
    edges = load_road_network_edges()
    graph = RoadNetworkGraph(nodes=nodes, edges=edges)

    assert nodes
    assert edges
    assert "geometry" not in nodes[0].__dict__
    assert "geometry" not in edges[0].__dict__
    assert graph.mode_coverage()["car_ride"] >= 1

    path = graph.shortest_path(
        "road-nsw-parramatta",
        "road-nsw-bondi",
        "car_ride",
    )

    assert path is not None
    assert path.distance_km == 31.2
    assert path.node_ids == (
        "road-nsw-parramatta",
        "road-nsw-strathfield",
        "road-nsw-sydney-cbd",
        "road-nsw-bondi",
    )


def test_place_route_node_snap_artifacts_load_for_road_modes():
    snaps = load_place_route_node_snaps()

    surry_hills_snaps = {
        (snap.place_id, snap.mode): snap
        for snap in snaps
        if snap.place_id == "au-nsw-surry-hills"
    }

    assert surry_hills_snaps[("au-nsw-surry-hills", "car_ride")].node_id == (
        "road-nsw-surry-hills"
    )
    assert surry_hills_snaps[("au-nsw-surry-hills", "rideshare")].node_id == (
        "road-nsw-surry-hills"
    )
    assert all(snap.mode in {"car_ride", "rideshare"} for snap in snaps)


def test_snapped_road_graph_route_wins_before_centroid_fallback():
    places = LocalPlaceResolver()
    provider = LocalRouteDistanceProvider()
    origin = places.resolve_place("Surry Hills").record
    destination = places.resolve_place("Newtown").record

    result = provider.distance(origin, destination, "rideshare")

    assert result.status == "resolved"
    assert result.exact is True
    assert result.distance == 4.0
    assert result.distance_source == "qgis_road_network_graph"
    assert result.origin_route_node_id == "road-nsw-surry-hills"
    assert result.destination_route_node_id == "road-nsw-newtown"
    assert result.route_path_node_ids == (
        "road-nsw-surry-hills",
        "road-nsw-newtown",
    )
    assert result.route_path_edge_ids == ("road-edge-surry-hills-newtown",)
    assert result.snap_confidence == 0.92
    assert result.snap_source == "maintained QGIS place-route-node fixture"


def test_ticket_17_melbourne_to_fitzroy_uses_snapped_road_graph():
    places = LocalPlaceResolver()
    provider = LocalRouteDistanceProvider()
    origin = places.resolve_place("Melbourne CBD").record
    destination = places.resolve_place("Fitzroy").record

    result = provider.distance(origin, destination, "car_ride")

    assert result.status == "resolved"
    assert result.exact is True
    assert result.distance == 2.5
    assert result.distance_source == "qgis_road_network_graph"
    assert result.source_version == "2026-06-01"
    assert result.origin_route_node_id == "road-vic-melbourne-cbd"
    assert result.destination_route_node_id == "road-vic-fitzroy"
    assert result.route_path_edge_ids == ("road-edge-melbourne-cbd-fitzroy",)
    assert result.confidence == 0.82


def test_one_missing_snap_uses_visible_centroid_fallback_issue():
    origin = _route_place_record("place-origin", "Origin", -33.0, 151.0)
    destination = _route_place_record("place-destination", "Destination", -33.1, 151.2)
    provider = LocalRouteDistanceProvider(
        records=[],
        network_edges=[],
        place_records=[origin, destination],
        place_route_nodes=[
            PlaceRouteNodeSnap(
                place_id="place-origin",
                mode="car_ride",
                node_id="node-origin",
                snap_distance_m=40.0,
                snap_confidence=0.9,
                snap_source="test snap",
                source_version="2026-06-01",
            )
        ],
        road_graph=RoadNetworkGraph(
            nodes=[_road_node("node-origin"), _road_node("node-destination")],
            edges=[],
        ),
    )

    result = provider.distance(origin, destination, "car_ride")

    assert result.status == "resolved"
    assert result.exact is False
    assert result.distance_source == "place_centroid_approximation"
    assert [issue.code for issue in result.issues] == ["route.snap_unavailable"]


def test_no_graph_path_between_snapped_nodes_returns_unavailable():
    places = LocalPlaceResolver()
    provider = LocalRouteDistanceProvider()
    origin = places.resolve_place("Brisbane CBD").record
    destination = places.resolve_place("Surry Hills").record

    result = provider.distance(origin, destination, "car_ride")

    assert result.status == "unavailable"
    assert result.distance is None
    assert result.distance_source is None


def test_road_network_fixture_disconnected_component_has_no_silent_estimate():
    graph = RoadNetworkGraph()

    assert graph.connected_component_count() >= 2
    assert (
        graph.shortest_path(
            "road-nsw-parramatta",
            "road-vic-melbourne-cbd",
            "car_ride",
        )
        is None
    )


def test_road_network_respects_one_way_and_bidirectional_edges():
    graph = RoadNetworkGraph(
        nodes=[
            _road_node("node-a"),
            _road_node("node-b"),
            _road_node("node-c"),
        ],
        edges=[
            _road_edge("edge-a-b", "node-a", "node-b", 5.0, bidirectional=False),
            _road_edge("edge-b-c", "node-b", "node-c", 2.0, bidirectional=True),
        ],
    )

    direct = graph.shortest_path("node-a", "node-b", "car_ride")
    blocked_reverse = graph.shortest_path("node-b", "node-a", "car_ride")
    bidirectional_reverse = graph.shortest_path("node-c", "node-b", "car_ride")

    assert direct is not None
    assert direct.distance_km == 5.0
    assert blocked_reverse is None
    assert bidirectional_reverse is not None
    assert bidirectional_reverse.distance_km == 2.0


def test_road_network_one_way_edges_can_make_reverse_distance_different():
    graph = RoadNetworkGraph(
        nodes=[
            _road_node("node-a"),
            _road_node("node-b"),
            _road_node("node-c"),
        ],
        edges=[
            _road_edge("edge-a-b-one-way", "node-a", "node-b", 3.0, bidirectional=False),
            _road_edge("edge-b-c", "node-b", "node-c", 2.0, bidirectional=True),
            _road_edge("edge-c-a", "node-c", "node-a", 6.0, bidirectional=True),
        ],
    )

    forward = graph.shortest_path("node-a", "node-b", "car_ride")
    reverse = graph.shortest_path("node-b", "node-a", "car_ride")

    assert forward is not None
    assert reverse is not None
    assert forward.distance_km == 3.0
    assert reverse.distance_km == 8.0
    assert forward.edge_ids == ("edge-a-b-one-way",)
    assert reverse.edge_ids == ("edge-b-c", "edge-c-a")


def test_road_network_filters_modes():
    graph = RoadNetworkGraph(
        nodes=[_road_node("node-a"), _road_node("node-b")],
        edges=[
            _road_edge(
                "edge-a-b",
                "node-a",
                "node-b",
                5.0,
                modes=("car_ride",),
            )
        ],
    )

    assert graph.shortest_path("node-a", "node-b", "car_ride") is not None
    assert graph.shortest_path("node-a", "node-b", "rideshare") is None
    assert graph.shortest_path("node-a", "node-b", "train_ride") is None


def test_route_provider_does_not_use_road_graph_for_train_mode():
    places = LocalPlaceResolver()
    provider = LocalRouteDistanceProvider()
    origin = places.resolve_place("Surry Hills").record
    destination = places.resolve_place("Newtown").record

    result = provider.distance(origin, destination, "train_ride")

    assert result.status == "resolved"
    assert result.distance_source == "place_centroid_approximation"
    assert result.distance_source != "qgis_road_network_graph"


def test_road_graph_shortest_path_performance_stays_bounded():
    graph = RoadNetworkGraph()

    started_at = time.perf_counter()
    for _ in range(500):
        path = graph.shortest_path(
            "road-nsw-parramatta",
            "road-nsw-bondi",
            "car_ride",
        )
    elapsed = time.perf_counter() - started_at

    assert path is not None
    assert path.distance_km == 31.2
    assert elapsed < 0.5


def test_approximate_route_fallback_uses_place_centroids():
    places = LocalPlaceResolver()
    provider = LocalRouteDistanceProvider()
    origin = places.resolve_place("Parramatta").record
    destination = places.resolve_place("Chatswood").record

    result = provider.distance(origin, destination, "car_ride")

    assert result.status == "resolved"
    assert result.exact is False
    assert result.distance > 20
    assert result.distance_source == "place_centroid_approximation"
    assert result.confidence < 0.6


def test_electricity_region_mapping_supports_nsw_and_victoria():
    resolver = LocalElectricityRegionResolver()

    nsw = resolver.resolve_region("I used electricity at home in NSW.")
    victoria = resolver.resolve_region("I used electricity in Victoria.")

    assert nsw.status == "resolved"
    assert nsw.record.region == "AU-NSW"
    assert victoria.status == "resolved"
    assert victoria.record.region == "AU-VIC"


def test_pipeline_derives_exact_car_route_distance(v2_pipeline):
    detail = _single_detail(v2_pipeline, "I drove from Parramatta to Bondi.")

    assert detail["status"] == "estimated"
    assert detail["activity_type"] == "car_ride"
    assert detail["parameters"]["origin"] == "Parramatta"
    assert detail["parameters"]["destination"] == "Bondi"
    assert detail["parameters"]["origin_place_id"] == "au-nsw-parramatta"
    assert detail["parameters"]["destination_place_id"] == "au-nsw-bondi"
    assert detail["parameters"]["distance"] == 31.2
    assert detail["parameters"]["distance_source"] == "qgis_route_network_road"
    assert detail["parameters"]["route_exact"] is True
    assert detail["parameters"]["route_path_place_names"] == (
        "Parramatta -> Strathfield -> Sydney CBD -> Bondi"
    )
    assert "route.distance.from_route_network" in _assumption_codes(detail)


def test_pipeline_derives_exact_train_route_distance(v2_pipeline):
    detail = _single_detail(v2_pipeline, "I took the train from Redfern to Chatswood.")

    assert detail["status"] == "estimated"
    assert detail["activity_type"] == "train_ride"
    assert detail["parameters"]["distance"] == 13.8
    assert detail["parameters"]["distance_source"] == "qgis_route_network_gtfs_shape"
    assert detail["parameters"]["route_exact"] is True
    assert detail["parameters"]["route_path_place_names"] == (
        "Redfern -> Central -> North Sydney -> Chatswood"
    )
    assert "route.distance.from_route_network" in _assumption_codes(detail)


def test_pipeline_derives_intercity_car_route_distance(v2_pipeline):
    detail = _single_detail(v2_pipeline, "Drove from Sydney to Canberra by car")

    assert detail["status"] == "estimated"
    assert detail["activity_type"] == "car_ride"
    assert detail["parameters"]["origin"] == "Sydney"
    assert detail["parameters"]["destination"] == "Canberra"
    assert detail["parameters"]["origin_place_id"] == "au-nsw-sydney-cbd"
    assert detail["parameters"]["destination_place_id"] == "au-act-canberra"
    assert detail["parameters"]["distance"] == 286.0
    assert detail["parameters"]["distance_source"] == "qgis_route_network_intercity_road"
    assert detail["parameters"]["route_exact"] is True
    assert detail["parameters"]["route_path_place_names"] == "Sydney CBD -> Canberra"
    assert "route.distance.from_route_network" in _assumption_codes(detail)
    assert "transport.missing_distance" not in _issue_codes(detail)


def test_pipeline_derives_reverse_intercity_electric_car_route(v2_pipeline):
    detail = _single_detail(
        v2_pipeline,
        "I travelled from Canberra to Sydney by electric car.",
    )

    assert detail["status"] == "estimated"
    assert detail["parameters"]["origin_place_id"] == "au-act-canberra"
    assert detail["parameters"]["destination_place_id"] == "au-nsw-sydney-cbd"
    assert detail["parameters"]["distance"] == 286.0
    assert detail["parameters"]["fuel_type"] == "electric"


def test_pipeline_uses_major_city_aliases_with_approximate_fallback(v2_pipeline):
    detail = _single_detail(v2_pipeline, "I drove from Melb to Brisbane.")

    assert detail["status"] == "estimated"
    assert detail["parameters"]["origin_place_id"] == "au-vic-melbourne"
    assert detail["parameters"]["destination_place_id"] == "au-qld-brisbane"
    assert detail["parameters"]["origin_match_type"] == "exact_alias"
    assert detail["parameters"]["destination_match_type"] == "exact_alias"
    assert detail["parameters"]["distance_source"] == "place_centroid_approximation"
    assert detail["parameters"]["route_exact"] is False
    assert "route.distance.estimated_from_place_centroids" in _assumption_codes(detail)
    assert "transport.missing_distance" not in _issue_codes(detail)


def test_pipeline_uses_ticket_13_gazetteer_places_for_route_enrichment(v2_pipeline):
    detail = _single_detail(v2_pipeline, "I took an Uber from Surry Hills to Newtown.")

    assert detail["status"] == "estimated"
    assert detail["activity_type"] == "rideshare"
    assert detail["parameters"]["origin"] == "Surry Hills"
    assert detail["parameters"]["destination"] == "Newtown"
    assert detail["parameters"]["origin_place_id"] == "au-nsw-surry-hills"
    assert detail["parameters"]["destination_place_id"] == "au-nsw-newtown"
    assert detail["parameters"]["distance"] == 4.0
    assert detail["parameters"]["distance_source"] == "qgis_road_network_graph"
    assert detail["parameters"]["route_exact"] is True
    assert detail["parameters"]["origin_route_node_id"] == "road-nsw-surry-hills"
    assert detail["parameters"]["destination_route_node_id"] == "road-nsw-newtown"
    assert detail["parameters"]["route_path_node_ids"] == (
        "road-nsw-surry-hills|road-nsw-newtown"
    )
    assert detail["parameters"]["snap_confidence"] == 0.92
    assert detail["parameters"]["snap_source"] == "maintained QGIS place-route-node fixture"
    assert "route.distance.from_route_network" in _assumption_codes(detail)
    assert "transport.missing_distance" not in _issue_codes(detail)


def test_pipeline_uses_mode_specific_airport_and_cbd_snaps(v2_pipeline):
    detail = _single_detail(
        v2_pipeline,
        "I got a rideshare from Brisbane CBD to Brisbane Airport.",
    )

    assert detail["status"] == "estimated"
    assert detail["activity_type"] == "rideshare"
    assert detail["parameters"]["origin_place_id"] == "au-qld-brisbane"
    assert detail["parameters"]["destination_place_id"] == "au-qld-brisbane-airport"
    assert detail["parameters"]["distance"] == 16.2
    assert detail["parameters"]["distance_source"] == "qgis_road_network_graph"
    assert detail["parameters"]["origin_route_node_id"] == "road-qld-brisbane-cbd"
    assert detail["parameters"]["destination_route_node_id"] == "road-qld-brisbane-airport"
    assert detail["parameters"]["snap_confidence"] == 0.91
    assert "route.distance.from_route_network" in _assumption_codes(detail)


def test_pipeline_uses_ticket_17_melbourne_cbd_to_fitzroy_graph_route(v2_pipeline):
    detail = _single_detail(v2_pipeline, "I drove from Melbourne CBD to Fitzroy.")

    assert detail["status"] == "estimated"
    assert detail["activity_type"] == "car_ride"
    assert detail["parameters"]["origin"] == "Melbourne CBD"
    assert detail["parameters"]["destination"] == "Fitzroy"
    assert detail["parameters"]["origin_place_id"] == "au-vic-melbourne-cbd"
    assert detail["parameters"]["destination_place_id"] == "au-vic-fitzroy"
    assert detail["parameters"]["distance"] == 2.5
    assert detail["parameters"]["distance_source"] == "qgis_road_network_graph"
    assert detail["parameters"]["distance_confidence"] == 0.82
    assert detail["parameters"]["route_exact"] is True
    assert detail["parameters"]["route_source_version"] == "2026-06-01"
    assert detail["parameters"]["route_path_node_ids"] == (
        "road-vic-melbourne-cbd|road-vic-fitzroy"
    )
    assert detail["parameters"]["route_path_edge_ids"] == "road-edge-melbourne-cbd-fitzroy"
    assert "route.distance.from_route_network" in _assumption_codes(detail)
    assert "transport.missing_distance" not in _issue_codes(detail)


def test_pipeline_keeps_explicit_melbourne_fitzroy_distance_over_graph(v2_pipeline):
    detail = _single_detail(v2_pipeline, "I drove 10 km from Melbourne CBD to Fitzroy.")

    assert detail["status"] == "estimated"
    assert detail["parameters"]["distance"] == 10
    assert detail["parameters"]["origin_place_id"] == "au-vic-melbourne-cbd"
    assert detail["parameters"]["destination_place_id"] == "au-vic-fitzroy"
    assert "distance_source" not in detail["parameters"]
    assert "route.distance.from_route_network" not in _assumption_codes(detail)


def test_pipeline_uses_unseen_fixture_graph_route_without_sentence_branch(v2_pipeline):
    detail = _single_detail(v2_pipeline, "I drove from Bondi to Surry Hills.")

    assert detail["status"] == "estimated"
    assert detail["parameters"]["origin_place_id"] == "au-nsw-bondi"
    assert detail["parameters"]["destination_place_id"] == "au-nsw-surry-hills"
    assert detail["parameters"]["distance"] == 8.9
    assert detail["parameters"]["distance_source"] == "qgis_road_network_graph"
    assert detail["parameters"]["route_path_edge_ids"] == (
        "road-edge-sydney-cbd-bondi|road-edge-sydney-cbd-surry-hills-one-way"
    )


def test_pipeline_returns_route_distance_unavailable_when_snapped_graph_has_no_path(
    v2_pipeline,
):
    detail = _single_detail(v2_pipeline, "I drove from Brisbane CBD to Surry Hills.")

    assert detail["status"] == "unresolved"
    assert detail["parameters"]["origin_place_id"] == "au-qld-brisbane"
    assert detail["parameters"]["destination_place_id"] == "au-nsw-surry-hills"
    assert "distance_source" not in detail["parameters"]
    assert "route.distance_unavailable" in _issue_codes(detail)
    assert "transport.missing_distance" in _issue_codes(detail)


def test_pipeline_resolves_ticket_14_clear_place_typo(v2_pipeline):
    detail = _single_detail(v2_pipeline, "I drove from Surry Hils to Newtown.")

    assert detail["status"] == "estimated"
    assert detail["parameters"]["origin"] == "Surry Hils"
    assert detail["parameters"]["origin_place_name"] == "Surry Hills"
    assert detail["parameters"]["destination_place_name"] == "Newtown"
    assert detail["parameters"]["origin_match_type"] == "fuzzy_alias"
    assert detail["parameters"]["distance_source"] == "qgis_road_network_graph"
    assert detail["parameters"]["origin_route_node_id"] == "road-nsw-surry-hills"
    assert detail["parameters"]["destination_route_node_id"] == "road-nsw-newtown"
    assert "location.place_fuzzy_matched" in _assumption_codes(detail)


def test_pipeline_keeps_explicit_distance_with_fuzzy_place_match(v2_pipeline):
    detail = _single_detail(v2_pipeline, "I drove 8 km from Surry Hils to Newtown.")

    assert detail["status"] == "estimated"
    assert detail["parameters"]["distance"] == 8.0
    assert detail["parameters"]["origin"] == "Surry Hils"
    assert detail["parameters"]["origin_place_name"] == "Surry Hills"
    assert detail["parameters"]["origin_match_type"] == "fuzzy_alias"
    assert "distance_source" not in detail["parameters"]
    assert "origin_route_node_id" not in detail["parameters"]
    assert "route.distance.estimated_from_place_centroids" not in _assumption_codes(detail)


def test_pipeline_state_hint_resolves_ambiguous_origin(v2_pipeline):
    detail = _single_detail(v2_pipeline, "I drove from Springfield QLD to Brisbane.")

    assert detail["status"] == "estimated"
    assert detail["parameters"]["origin_place_id"] == "au-qld-springfield"
    assert detail["parameters"]["origin_region"] == "AU-QLD"
    assert detail["parameters"]["distance_source"] == "place_centroid_approximation"
    assert "route.snap_unavailable" in _issue_codes(detail)
    assert "location.place_ambiguous" not in _issue_codes(detail)


def test_pipeline_uses_fuzzy_place_matches_without_preprocessor_autocorrect(v2_pipeline):
    detail = _single_detail(v2_pipeline, "I took the train from Redfernn to Chastwood.")

    assert detail["status"] == "estimated"
    assert detail["parameters"]["origin"] == "Redfernn"
    assert detail["parameters"]["destination"] == "Chastwood"
    assert detail["parameters"]["origin_place_id"] == "au-nsw-redfern"
    assert detail["parameters"]["destination_place_id"] == "au-nsw-chatswood"
    assert detail["parameters"]["origin_match_type"] == "fuzzy_alias"
    assert detail["parameters"]["destination_match_type"] == "fuzzy_alias"
    assert detail["parameters"]["distance"] == 13.8
    assert _assumption_codes(detail).count("location.place_fuzzy_matched") == 2


def test_pipeline_does_not_guess_ambiguous_fuzzy_place(v2_pipeline):
    detail = _single_detail(v2_pipeline, "I drove from Springfeld to Bondi.")

    assert detail["status"] == "unresolved"
    assert "location.place_ambiguous" in _issue_codes(detail)
    assert "transport.missing_distance" in _issue_codes(detail)


def test_pipeline_marks_approximate_route_distance_with_visible_assumption(v2_pipeline):
    detail = _single_detail(v2_pipeline, "I drove from Parramatta to Chatswood.")

    assert detail["status"] == "estimated"
    assert detail["parameters"]["distance"] > 20
    assert detail["parameters"]["distance_source"] == "place_centroid_approximation"
    assert detail["parameters"]["route_exact"] is False
    assert "route.distance.estimated_from_place_centroids" in _assumption_codes(detail)


def test_pipeline_preserves_explicit_distance_over_route_distance(v2_pipeline):
    detail = _single_detail(v2_pipeline, "I drove 10 km from Parramatta to Bondi.")

    assert detail["status"] == "estimated"
    assert detail["parameters"]["distance"] == 10
    assert detail["parameters"]["origin_place_id"] == "au-nsw-parramatta"
    assert detail["parameters"]["destination_place_id"] == "au-nsw-bondi"
    assert "distance_source" not in detail["parameters"]
    assert "route.distance.from_route_network" not in _assumption_codes(detail)


def test_pipeline_returns_unresolved_for_unknown_route_place(v2_pipeline):
    detail = _single_detail(v2_pipeline, "I drove from Unknown Place to Bondi.")

    assert detail["status"] == "unresolved"
    assert detail["parameters"]["origin"] == "Unknown Place"
    assert detail["parameters"]["destination"] == "Bondi"
    assert "location.place_unresolved" in _issue_codes(detail)
    assert "transport.missing_distance" in _issue_codes(detail)


def test_pipeline_uses_nsw_electricity_context_with_explicit_kwh(v2_pipeline):
    detail = _single_detail(v2_pipeline, "I used 5 kWh of electricity at home in NSW.")

    assert detail["status"] == "estimated"
    assert detail["parameters"]["energy"] == 5
    assert detail["parameters"]["region"] == "AU-NSW"
    assert detail["parameters"]["factor_region"] == "AU-NSW"
    assert "region.energy.user_supplied" in _assumption_codes(detail)
    assert "region.default_au_electricity" not in _assumption_codes(detail)


def test_pipeline_keeps_region_context_but_does_not_infer_home_electricity(v2_pipeline):
    detail = _single_detail(v2_pipeline, "I used electricity at home in NSW.")

    assert detail["status"] == "unresolved"
    assert detail["parameters"]["region"] == "AU-NSW"
    assert "energy" not in detail["parameters"]
    assert "energy.missing_quantity" in _issue_codes(detail)
    assert "region.default_au_electricity" not in _assumption_codes(detail)


def test_pipeline_supports_non_nsw_australian_electricity_region(v2_pipeline):
    detail = _single_detail(v2_pipeline, "I used 2 kWh of electricity at home in VIC.")

    assert detail["status"] == "estimated"
    assert detail["parameters"]["energy"] == 2
    assert detail["parameters"]["region"] == "AU-VIC"
    assert "region.energy.user_supplied" in _assumption_codes(detail)
    assert "region.default_au_electricity" not in _assumption_codes(detail)


def test_route_electricity_and_unrelated_activity_do_not_bleed(v2_pipeline):
    result = v2_pipeline.run(
        "I drove from Parramatta to Bondi, used 5 kWh of electricity at home in VIC, "
        "and read a book."
    ).model_dump()

    route, electricity, reading = result["details"]

    assert [detail["activity_type"] for detail in result["details"]] == [
        "car_ride",
        "electricity_use",
        "personal_activity",
    ]
    assert route["parameters"]["distance"] == 31.2
    assert "region" not in route["parameters"]
    assert electricity["parameters"]["region"] == "AU-VIC"
    assert "origin" not in electricity["parameters"]
    assert reading["status"] == "not_estimated"


def test_graph_route_electricity_and_food_parameters_do_not_bleed(v2_pipeline):
    result = v2_pipeline.run(
        "I drove from Melbourne CBD to Fitzroy, used 2 kWh of electricity at home in VIC, "
        "and grabbed a coffee."
    ).model_dump()

    details_by_type = {detail["activity_type"]: detail for detail in result["details"]}
    route = details_by_type["car_ride"]
    electricity = details_by_type["electricity_use"]
    coffee = details_by_type["coffee_purchase"]

    assert route["parameters"]["distance_source"] == "qgis_road_network_graph"
    assert route["parameters"]["origin_place_id"] == "au-vic-melbourne-cbd"
    assert "region" not in route["parameters"]
    assert "product_class" not in route["parameters"]
    assert electricity["parameters"]["region"] == "AU-VIC"
    assert "origin" not in electricity["parameters"]
    assert coffee["status"] == "estimated"
    assert coffee["parameters"]["product_class"] == "coffee"
    assert "distance" not in coffee["parameters"]
    assert "region" not in coffee["parameters"]


def test_fuzzy_route_electricity_and_unrelated_activity_do_not_bleed(v2_pipeline):
    result = v2_pipeline.run(
        "I drove from Surry Hils to Newtown, used 2 kWh of electricity at home in NSW, "
        "and read a book."
    ).model_dump()

    route, electricity, reading = result["details"]

    assert [detail["activity_type"] for detail in result["details"]] == [
        "car_ride",
        "electricity_use",
        "personal_activity",
    ]
    assert route["parameters"]["origin"] == "Surry Hils"
    assert route["parameters"]["origin_place_name"] == "Surry Hills"
    assert route["parameters"]["origin_match_type"] == "fuzzy_alias"
    assert "region" not in route["parameters"]
    assert electricity["parameters"]["region"] == "AU-NSW"
    assert "origin" not in electricity["parameters"]
    assert reading["status"] == "not_estimated"


def test_route_provider_failure_is_isolated_to_affected_event(fake_climatiq_estimator):
    class RaisingRouteDistanceProvider:
        def distance(self, origin, destination, mode):
            raise RuntimeError("route cache unavailable")

    pipeline = CarbonPipelineV2(
        emission_estimator=fake_climatiq_estimator,
        location_enricher=LocationEnricher(
            route_distance_provider=RaisingRouteDistanceProvider()
        ),
    )

    result = pipeline.run(
        "I drove from Parramatta to Bondi and used 5 kWh of electricity."
    ).model_dump()

    assert [detail["status"] for detail in result["details"]] == [
        "unresolved",
        "estimated",
    ]
    assert "location.provider_unavailable" in _issue_codes(result["details"][0])
    assert result["details"][1]["parameters"]["energy"] == 5


def _single_detail(v2_pipeline, journal: str) -> dict:
    result = v2_pipeline.run(journal).model_dump()
    assert len(result["details"]) == 1
    return result["details"][0]


def _assumption_codes(detail: dict) -> list[str]:
    return [assumption["code"] for assumption in detail["assumptions"]]


def _issue_codes(detail: dict) -> list[str]:
    return [issue["code"] for issue in detail["issues"]]


def _place_record(place_id: str, name: str, region: str) -> PlaceRecord:
    return PlaceRecord(
        place_id=place_id,
        name=name,
        aliases=("springfield",),
        place_type="locality",
        region=region,
        latitude=-33.0,
        longitude=151.0,
        source="test fixture",
        source_version="2026-06-01",
        ambiguous_aliases=("springfield",),
    )


def _route_place_record(
    place_id: str,
    name: str,
    latitude: float,
    longitude: float,
) -> PlaceRecord:
    return PlaceRecord(
        place_id=place_id,
        name=name,
        aliases=(name.lower(),),
        place_type="suburb",
        region="AU-NSW",
        latitude=latitude,
        longitude=longitude,
        source="test fixture",
        source_version="2026-06-01",
    )


def _road_node(node_id: str) -> RoadNetworkNode:
    return RoadNetworkNode(
        node_id=node_id,
        latitude=-33.0,
        longitude=151.0,
        source="test road graph",
        source_version="2026-06-01",
    )


def _road_edge(
    edge_id: str,
    from_node_id: str,
    to_node_id: str,
    distance_km: float,
    *,
    modes: tuple[str, ...] = ("car_ride", "rideshare"),
    bidirectional: bool = True,
) -> RoadNetworkEdge:
    return RoadNetworkEdge(
        edge_id=edge_id,
        from_node_id=from_node_id,
        to_node_id=to_node_id,
        distance_km=distance_km,
        modes=modes,
        bidirectional=bidirectional,
        source="test road graph",
        confidence=0.9,
        source_version="2026-06-01",
    )
