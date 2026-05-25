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
        ("I took a rideshare 8 km.", "rideshare", "estimated", 8),
        ("I took a taxi for 3 km.", "rideshare", "estimated", 3),
        ("I rode my bike 6 km.", "bicycle_ride", "not_estimated", 6),
        ("I walked 2 km.", "walking", "not_estimated", 2),
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


def test_flight_without_approved_path_remains_visible(v2_pipeline):
    detail = v2_pipeline.run("I took a flight for 500 km.").model_dump()["details"][0]

    assert detail["activity_type"] == "flight"
    assert detail["status"] == "unresolved"
    assert detail["issues"][0]["code"] == "transport.flight.factor_unresolved"


def test_missing_climatiq_factor_fails_visibly_without_local_emission_fallback():
    pipeline = CarbonPipelineV2(
        emission_estimator=ClimatiqEmissionEstimator(
            activity_search=lambda query, limit: []
        )
    )

    detail = pipeline.run("I took a 5 km bus ride.").model_dump()["details"][0]

    assert detail["status"] == "failed"
    assert detail["source"] == "climatiq"
    assert detail["co2e"] is None
    assert detail["issues"][0]["code"] == "climatiq.factor_unavailable"
