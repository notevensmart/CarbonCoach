from app.domain.models import CarbonEvent, Confidence
from app.domain.activity_taxonomy import ACTIVITY_TAXONOMY
from app.pipeline_v2.emission_estimator import ClimatiqEmissionEstimator
from app.pipeline_v2.factor_retriever import ClimatiqFactorRetriever
from app.pipeline_v2.pipeline import CarbonPipelineV2
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


def test_named_specificity_search_prefers_a_direct_climatiq_metadata_match():
    remote_calls = []
    retriever = ClimatiqFactorRetriever(
        local_records_provider=lambda: [
            _record(
                "passenger_vehicle-vehicle_type_business_travel_medium_car-fuel_source_petrol",
                "Petrol car (medium) - Business travel",
                "Distance",
            )
        ],
        remote_search=lambda query, limit, **kwargs: remote_calls.append(query) or [
            _record(
                "passenger_vehicle-vehicle_type_mazda_3-fuel_source_petrol",
                "Mazda 3 petrol car",
                "Distance",
                description="Passenger car travel in a Mazda 3.",
            )
        ],
    )

    candidates = retriever.retrieve(
        _event("car_ride"),
        {
            "distance": 5,
            "distance_unit": "km",
            "fuel_type": "petrol",
            "vehicle_size": "medium",
            "vehicle_description": "Mazda 3",
        },
    )

    assert "Mazda 3" in remote_calls[0]
    assert candidates[0].activity_id == "passenger_vehicle-vehicle_type_mazda_3-fuel_source_petrol"
    assert candidates[0].specificity_match is True
    assert any("specific supplied description" in reason for reason in candidates[0].match_reasons)


def test_fuzzy_generic_remote_result_does_not_claim_a_specific_description_match():
    retriever = ClimatiqFactorRetriever(
        local_records_provider=lambda: [
            _record(
                "passenger_vehicle-vehicle_type_business_travel_medium_car-fuel_source_petrol",
                "Petrol car (medium) - Business travel",
                "Distance",
            )
        ],
        remote_search=lambda *args, **kwargs: [
            _record(
                "passenger_vehicle-vehicle_type_business_travel_car-fuel_source_petrol",
                "Petrol car (average) - Business travel",
                "Distance",
            )
        ],
    )

    candidates = retriever.retrieve(
        _event("car_ride"),
        {
            "distance": 5,
            "distance_unit": "km",
            "fuel_type": "petrol",
            "vehicle_size": "medium",
            "vehicle_description": "Mazda 3",
        },
    )

    assert candidates[0].specificity_match is False
    assert "medium_car" in candidates[0].activity_id


def test_specific_text_match_cannot_override_explicit_trait_evidence():
    retriever = ClimatiqFactorRetriever(
        local_records_provider=lambda: [
            _record(
                "passenger_vehicle-vehicle_type_business_travel_medium_car-fuel_source_bev",
                "Battery EV car (medium) - Business travel",
                "Distance",
            )
        ],
        remote_search=lambda *args, **kwargs: [
            _record(
                "passenger_vehicle-vehicle_type_mazda_3-fuel_source_petrol",
                "Mazda 3 petrol car",
                "Distance",
            )
        ],
    )
    event = CarbonEvent(
        raw_text="electric Mazda 3",
        category="transport",
        activity_type="car_ride",
        entities={"fuel_type_source": "user"},
        confidence=Confidence.from_score(0.8),
    )

    candidates = retriever.retrieve(
        event,
        {
            "distance": 5,
            "distance_unit": "km",
            "fuel_type": "electric",
            "vehicle_size": "medium",
            "vehicle_description": "Mazda 3",
        },
    )

    assert "fuel_source_bev" in candidates[0].activity_id
    assert candidates[0].specificity_match is False


def test_specific_text_match_without_required_explicit_trait_is_rejected():
    retriever = ClimatiqFactorRetriever(
        local_records_provider=lambda: [
            _record(
                "passenger_vehicle-vehicle_type_business_travel_medium_car-fuel_source_bev",
                "Battery EV car (medium) - Business travel",
                "Distance",
            )
        ],
        remote_search=lambda *args, **kwargs: [
            _record(
                "passenger_vehicle-vehicle_type_mazda_3-fuel_source_na",
                "Mazda 3 passenger car",
                "Distance",
            )
        ],
    )
    event = CarbonEvent(
        raw_text="electric Mazda 3",
        category="transport",
        activity_type="car_ride",
        entities={"fuel_type_source": "user"},
        confidence=Confidence.from_score(0.8),
    )

    candidates = retriever.retrieve(
        event,
        {
            "distance": 5,
            "distance_unit": "km",
            "fuel_type": "electric",
            "vehicle_size": "medium",
            "vehicle_description": "Mazda 3",
        },
    )

    assert "fuel_source_bev" in candidates[0].activity_id
    assert candidates[0].specificity_match is False


def test_taxonomy_declared_identity_evidence_is_not_vehicle_specific(monkeypatch):
    monkeypatch.setitem(
        ACTIVITY_TAXONOMY["electricity_use"],
        "factor_identity_fields",
        ("supply_description",),
    )
    retriever = ClimatiqFactorRetriever(
        local_records_provider=lambda: [],
        remote_search=lambda query, limit, **kwargs: [
            {
                "activity_id": "electricity-supply_harbour_green_grid",
                "name": "Harbour Green Grid electricity supply",
                "description": "Electricity delivered by Harbour Green Grid.",
                "category": "Electricity",
                "sector": "Energy",
                "unit_type": "Energy",
            }
        ],
    )
    event = CarbonEvent(
        raw_text="used green electricity",
        category="energy",
        activity_type="electricity_use",
        confidence=Confidence.from_score(0.8),
    )

    candidates = retriever.retrieve(
        event,
        {
            "energy": 3,
            "energy_unit": "kWh",
            "supply_description": "Harbour Green Grid",
        },
    )

    assert candidates[0].specificity_match is True
    assert candidates[0].activity_id == "electricity-supply_harbour_green_grid"


def test_specific_factor_is_visible_and_replaces_named_vehicle_generic_fallback():
    class FakeClient:
        def estimate(self, activity_id, parameters):
            return ClimatiqEstimate(co2e=0.7, co2e_unit="kg", ok=True)

    retriever = ClimatiqFactorRetriever(
        local_records_provider=lambda: [],
        remote_search=lambda *args, **kwargs: [
            _record(
                "passenger_vehicle-vehicle_type_mazda_3-fuel_source_petrol",
                "Mazda 3 petrol car",
                "Distance",
            )
        ],
    )
    pipeline = CarbonPipelineV2(
        emission_estimator=ClimatiqEmissionEstimator(
            climatiq_client=FakeClient(),
            factor_retriever=retriever,
        )
    )

    detail = pipeline.run("I took a 5 km car ride in a Mazda 3.").model_dump()["details"][0]

    assert detail["factor"]["specificity_match"] is True
    assert detail["parameters"]["factor_specificity"] == "supplied_description"
    assert "fuel_type" not in detail["parameters"]
    assert "vehicle_size" not in detail["parameters"]
    assert detail["confidence"]["level"] == "high"
    assert "vehicle.named.default_petrol_medium" not in [
        assumption["code"] for assumption in detail["assumptions"]
    ]
    assert "vehicle.named_model.unmapped" not in [
        issue["code"] for issue in detail["issues"]
    ]


def test_specific_factor_preserves_explicit_fuel_and_removes_unneeded_size_default():
    class FakeClient:
        def estimate(self, activity_id, parameters):
            return ClimatiqEstimate(co2e=0.2, co2e_unit="kg", ok=True)

    retriever = ClimatiqFactorRetriever(
        local_records_provider=lambda: [],
        remote_search=lambda *args, **kwargs: [
            _record(
                "passenger_vehicle-vehicle_type_mazda_3-fuel_source_bev",
                "Battery EV Mazda 3 car",
                "Distance",
            )
        ],
    )
    pipeline = CarbonPipelineV2(
        emission_estimator=ClimatiqEmissionEstimator(
            climatiq_client=FakeClient(),
            factor_retriever=retriever,
        )
    )

    detail = pipeline.run("I drove 5 km in an electric Mazda 3.").model_dump()["details"][0]

    assert detail["factor"]["specificity_match"] is True
    assert detail["parameters"]["fuel_type"] == "electric"
    assert "vehicle_size" not in detail["parameters"]
    assert detail["assumptions"] == []


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


def _record(activity_id, name, unit_type, description=""):
    return {
        "activity_id": activity_id,
        "name": name,
        "description": description,
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
