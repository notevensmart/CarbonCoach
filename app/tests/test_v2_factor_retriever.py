from app.domain.models import CarbonEvent, Confidence
from app.pipeline_v2.emission_estimator import ClimatiqEmissionEstimator
from app.pipeline_v2.factor_retriever import ClimatiqFactorRetriever
from app.services.climatiq_api import ClimatiqEstimate, ClimatiqClient


def test_local_climatiq_records_select_medium_petrol_car_without_remote_search():
    remote_calls = []
    retriever = ClimatiqFactorRetriever(
        local_records_provider=lambda: [
            _record(
                "managed_assets_vehicle-vehicle_type_business_travel_medium_car-fuel_source_petrol",
                "Petrol car (medium) - Managed assets (vehicles)",
                "Distance",
            ),
            _record(
                "passenger_vehicle-vehicle_type_business_travel_large_car-fuel_source_petrol",
                "Petrol car (large) - Business travel",
                "Distance",
            ),
            _record(
                "passenger_vehicle-vehicle_type_business_travel_medium_car-fuel_source_petrol",
                "Petrol car (medium) - Business travel",
                "Distance",
            ),
        ],
        remote_search=lambda *args, **kwargs: remote_calls.append((args, kwargs)) or [],
    )

    candidates = retriever.retrieve(
        _event("car_ride"),
        {
            "distance": 6,
            "distance_unit": "km",
            "fuel_type": "petrol",
            "vehicle_size": "medium",
        },
    )

    assert candidates[0].activity_id.endswith("medium_car-fuel_source_petrol")
    assert candidates[0].activity_id.startswith("passenger_vehicle-")
    assert candidates[0].unit_type == "Distance"
    assert remote_calls == []


def test_passenger_distance_factor_sends_default_single_passenger_to_climatiq():
    class FakeClient:
        def __init__(self):
            self.calls = []

        def estimate(self, activity_id, parameters):
            self.calls.append((activity_id, parameters))
            return ClimatiqEstimate(co2e=0.4, co2e_unit="kg", ok=True)

    client = FakeClient()
    retriever = ClimatiqFactorRetriever(
        local_records_provider=lambda: [
            _record(
                "passenger_vehicle-vehicle_type_bus-fuel_source_na",
                "Average bus",
                "PassengerOverDistance",
            )
        ]
    )
    estimator = ClimatiqEmissionEstimator(
        climatiq_client=client,
        factor_retriever=retriever,
    )

    result = estimator.estimate(
        _event("bus_ride"),
        {"distance": 5, "distance_unit": "km", "transport_mode": "bus_ride"},
    )

    assert result.ok is True
    assert client.calls == [
        (
            "passenger_vehicle-vehicle_type_bus-fuel_source_na",
            {"distance": 5, "distance_unit": "km", "passengers": 1},
        )
    ]


def test_climatiq_client_posts_basic_estimate_documented_endpoint(monkeypatch):
    captured = {}

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"co2e": 1.25, "co2e_unit": "kg"}

    def fake_post(url, headers, json, timeout):
        captured.update({"url": url, "json": json})
        return Response()

    monkeypatch.setattr("app.services.climatiq_api.requests.post", fake_post)
    client = ClimatiqClient(api_key="test", base_url="https://api.climatiq.io", data_version="^33")

    result = client.estimate(
        "passenger_vehicle-vehicle_type_business_travel_medium_car-fuel_source_petrol",
        {"distance": 6, "distance_unit": "km"},
    )

    assert result.ok is True
    assert captured["url"] == "https://api.climatiq.io/data/v1/estimate"
    assert captured["json"] == {
        "emission_factor": {
            "activity_id": (
                "passenger_vehicle-vehicle_type_business_travel_medium_car-fuel_source_petrol"
            ),
            "data_version": "^33",
        },
        "parameters": {"distance": 6, "distance_unit": "km"},
    }


def _record(activity_id, name, unit_type):
    return {
        "activity_id": activity_id,
        "name": name,
        "category": "Vehicles",
        "sector": "Transport",
        "unit_type": unit_type,
    }


def _event(activity_type):
    return CarbonEvent(
        raw_text="transport",
        category="transport",
        activity_type=activity_type,
        confidence=Confidence.from_score(0.8),
    )
