import pytest

from app.pipeline_v2.emission_estimator import ClimatiqEmissionEstimator
from app.pipeline_v2.pipeline import CarbonPipelineV2


@pytest.mark.parametrize(
    ("journal", "activity_type", "status", "distance"),
    [
        ("I took a 5km bus ride.", "bus_ride", "estimated", 5),
        ("I rode a coach for 6 km.", "bus_ride", "estimated", 6),
        ("I caught the train for 12 km.", "train_ride", "estimated", 12),
        ("I used rail for 4 km.", "train_ride", "estimated", 4),
        ("I took the tram for 5 km.", "train_ride", "estimated", 5),
        ("I rode the subway for 7 km.", "train_ride", "estimated", 7),
        ("I took a rideshare 8 km.", "rideshare", "estimated", 8),
        ("I took a taxi for 3 km.", "rideshare", "estimated", 3),
        ("I rode my bike 6 km.", "bicycle_ride", "not_estimated", 6),
        ("I walked 2 km.", "walking", "not_estimated", 2),
        ("I ran a 5k after work.", "walking", "not_estimated", 5),
    ],
)
def test_transport_mode_matrix_is_taxonomy_driven(
    v2_pipeline,
    fake_climatiq_estimator,
    journal,
    activity_type,
    status,
    distance,
):
    detail = v2_pipeline.run(journal).model_dump()["details"][0]

    assert detail["activity_type"] == activity_type
    assert detail["status"] == status
    assert detail["parameters"]["distance"] == distance
    if status == "estimated":
        assert detail["source"] == "climatiq"
        assert fake_climatiq_estimator.calls[-1][0] == activity_type
    else:
        assert detail["co2e"] == 0
        assert detail["source"] == "none"
        assert fake_climatiq_estimator.calls == []


def test_bus_visible_parity_case_no_longer_returns_zero(v2_pipeline):
    result = v2_pipeline.run("I took a 5km bus ride.").model_dump()

    assert result["total"]["co2e"] == 0.5
    assert result["details"][0]["status"] == "estimated"


def test_explicit_electric_bus_fuel_is_preserved_for_factor_retrieval(
    v2_pipeline,
    fake_climatiq_estimator,
):
    detail = v2_pipeline.run("6km ride in electric bus").model_dump()["details"][0]

    assert detail["activity_type"] == "bus_ride"
    assert detail["parameters"]["fuel_type"] == "electric"
    assert fake_climatiq_estimator.calls[-1][1]["fuel_type"] == "electric"


def test_explicit_ev_bus_wording_normalizes_to_electric_fuel(v2_pipeline):
    detail = v2_pipeline.run("I travelled 8 km by EV bus.").model_dump()["details"][0]

    assert detail["activity_type"] == "bus_ride"
    assert detail["parameters"]["fuel_type"] == "electric"


def test_explicit_rail_subtype_is_preserved_for_retrieval(v2_pipeline):
    tram = v2_pipeline.run("I took the tram for 5 km.").model_dump()["details"][0]
    subway = v2_pipeline.run("I rode the subway for 7 km.").model_dump()["details"][0]

    assert tram["parameters"]["route_type"] == "tram"
    assert subway["parameters"]["route_type"] == "subway"


def test_bus_train_heater_and_car_remain_independent_in_one_journal(v2_pipeline):
    result = v2_pipeline.run(
        "I took a 5 km bus ride and caught the train for 12 km, "
        "then drove 3 km in a petrol car and used the heater for 1 hour."
    ).model_dump()

    assert [detail["activity_type"] for detail in result["details"]] == [
        "bus_ride",
        "train_ride",
        "car_ride",
        "space_heater_use",
    ]
    assert all(detail["status"] == "estimated" for detail in result["details"])


def test_unknown_transport_mode_has_one_useful_issue(v2_pipeline):
    detail = v2_pipeline.run("I used an electric scooter for 4 km.").model_dump()["details"][0]

    assert detail["activity_type"] == "generic_transport"
    assert detail["status"] == "unresolved"
    assert [issue["code"] for issue in detail["issues"]] == ["transport.mode.unsupported"]


def test_plane_trip_with_distance_enters_factor_backed_estimation_path(v2_pipeline):
    detail = v2_pipeline.run("100km by plane").model_dump()["details"][0]

    assert detail["activity_type"] == "flight"
    assert detail["parameters"]["distance"] == 100
    assert detail["parameters"]["route_type"] == "domestic"
    assert detail["parameters"]["passenger_class"] == "average"
    assert detail["parameters"]["rf_effect"] == "included"
    assert detail["parameters"]["distance_band"] == "short_haul"
    assert detail["confidence"]["level"] == "medium"
    assert detail["assumptions"][0]["code"] == "flight.default_factor_parameters"
    assert detail["status"] == "estimated"
    assert detail["issues"] == []


def test_explicit_flight_route_and_class_override_defaults(v2_pipeline):
    detail = v2_pipeline.run(
        "I flew 900 km on an international economy flight."
    ).model_dump()["details"][0]

    assert detail["parameters"]["route_type"] == "international"
    assert detail["parameters"]["passenger_class"] == "economy"
    assert detail["parameters"]["distance_band"] == "short_haul"
    assert "domestic route" not in detail["assumptions"][0]["message"]
    assert "average passenger class" not in detail["assumptions"][0]["message"]


def test_internationally_wording_is_preserved_as_explicit_route(v2_pipeline):
    detail = v2_pipeline.run(
        "I flew 900 km internationally in economy."
    ).model_dump()["details"][0]

    assert detail["parameters"]["route_type"] == "international"
    assert detail["parameters"]["passenger_class"] == "economy"
    assert "domestic route" not in detail["assumptions"][0]["message"]


def test_powered_bicycle_is_not_reported_as_zero_operational_cycling(v2_pipeline):
    detail = v2_pipeline.run("I rode my e-bike for 8 km.").model_dump()["details"][0]

    assert detail["activity_type"] == "generic_transport"
    assert detail["status"] == "unresolved"
    assert detail["issues"][0]["code"] == "transport.mode.unsupported"


def test_known_unsupported_carbon_events_remain_visible_in_mixed_journals(v2_pipeline):
    waste = v2_pipeline.run(
        "I recycled plastic bottles after driving 3 km in a hybrid car."
    ).model_dump()["details"]
    goods = v2_pipeline.run(
        "I bought two shirts and caught the bus for 4 km."
    ).model_dump()["details"]

    assert [detail["activity_type"] for detail in waste] == ["car_ride", "recycling"]
    assert waste[1]["status"] == "unresolved"
    assert waste[1]["issues"][0]["code"] == "waste.missing_weight"
    assert [detail["activity_type"] for detail in goods] == [
        "clothing_purchase",
        "bus_ride",
    ]
    assert goods[0]["status"] == "unresolved"
    assert goods[0]["issues"][0]["code"] == "goods_services.estimation.not_implemented"


@pytest.mark.parametrize(
    ("journal", "category", "activity_type", "status", "issue_code"),
    [
        ("I recycled 500 g of plastic.", "waste", "recycling", "estimated", None),
        ("I put food scraps in the compost bin.", "waste", "composting", "unresolved", "waste.missing_weight"),
        ("I put rubbish in the general waste bin.", "waste", "landfill_waste", "unresolved", "waste.missing_weight"),
        ("I bought two shirts.", "goods_services", "clothing_purchase", "unresolved", "goods_services.estimation.not_implemented"),
        ("I ordered a laptop online.", "goods_services", "electronics_purchase", "unresolved", "goods_services.estimation.not_implemented"),
        ("I spent $6 on coffee.", "goods_services", "coffee_purchase", "unresolved", "goods_services.money_factor_unavailable"),
        ("I bought groceries today.", "goods_services", "food_purchase", "unresolved", "goods_services.product.unsupported_pathway"),
        ("I had dinner at a restaurant.", "goods_services", "restaurant_meal", "unresolved", "goods_services.product.unsupported_pathway"),
    ],
)
def test_known_waste_and_goods_events_follow_bounded_factor_pathways(
    v2_pipeline,
    journal,
    category,
    activity_type,
    status,
    issue_code,
):
    detail = v2_pipeline.run(journal).model_dump()["details"][0]

    assert detail["category"] == category
    assert detail["activity_type"] == activity_type
    assert detail["status"] == status
    if issue_code:
        assert detail["source"] == "unresolved"
        assert detail["issues"][0]["code"] == issue_code
    else:
        assert detail["source"] == "climatiq"


def test_missing_climatiq_factor_uses_declared_local_fallback():
    pipeline = CarbonPipelineV2(
        emission_estimator=ClimatiqEmissionEstimator(
            activity_search=lambda query, limit: []
        )
    )

    detail = pipeline.run("I took a 5 km bus ride.").model_dump()["details"][0]

    assert detail["status"] == "fallback_estimated"
    assert detail["source"] == "fallback"
    assert detail["co2e"] == 0.45
    assert detail["issues"][0]["code"] == "climatiq.factor_unavailable"
    assert detail["assumptions"][0]["code"] == "fallback_factor.transport.public_passenger_distance"
