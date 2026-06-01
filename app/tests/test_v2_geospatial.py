from app.domain.geospatial import (
    LocalElectricityRegionResolver,
    LocalPlaceResolver,
    LocalRouteDistanceProvider,
    RouteDistanceRecord,
)
from app.pipeline_v2.location_enricher import LocationEnricher
from app.pipeline_v2.pipeline import CarbonPipelineV2


def test_place_alias_resolution_and_unknown_place():
    resolver = LocalPlaceResolver()

    resolved = resolver.resolve_place("Parramatta")
    unknown = resolver.resolve_place("Unknown Place")

    assert resolved.status == "resolved"
    assert resolved.record.place_id == "au-nsw-parramatta"
    assert resolved.record.region == "AU-NSW"
    assert unknown.status == "unknown"


def test_place_alias_ambiguity_is_typed():
    resolver = LocalPlaceResolver()

    result = resolver.resolve_place("Springfield")

    assert result.status == "ambiguous"
    assert sorted(record.region for record in result.candidates) == ["AU-NSW", "AU-QLD"]


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
