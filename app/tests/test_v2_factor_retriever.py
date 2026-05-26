from app.domain.models import CarbonEvent, Confidence, FactorCandidate
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


def test_energy_factor_ranking_filters_distance_metadata_and_reports_evidence():
    retriever = ClimatiqFactorRetriever(
        local_records_provider=lambda: [
            _record(
                "passenger_vehicle-vehicle_type_business_travel_medium_car-fuel_source_petrol",
                "Petrol car (medium) - Business travel",
                "Distance",
            ),
            _energy_record(
                "electricity-supply_grid-source_residual_mix",
                "Electricity grid residual mix Australia",
                vector_score=0.90,
            ),
        ],
        remote_search=lambda *args, **kwargs: [],
    )

    candidates = retriever.retrieve(
        _energy_event("electricity_use"),
        {"energy": 5, "energy_unit": "kWh"},
    )

    assert [candidate.activity_id for candidate in candidates] == [
        "electricity-supply_grid-source_residual_mix"
    ]
    assert any("unit_type matched required energy parameters" in reason for reason in candidates[0].match_reasons)
    assert any("record vector_score score" in reason for reason in candidates[0].match_reasons)


def test_weak_metadata_only_factor_is_rejected_and_remote_fallback_is_attempted():
    remote_calls = []
    retriever = ClimatiqFactorRetriever(
        local_records_provider=lambda: [
            {
                "activity_id": "fixture.energy.unrelated",
                "name": "Industrial equipment process",
                "sector": "Energy",
                "unit_type": "Energy",
            }
        ],
        remote_search=lambda *args, **kwargs: remote_calls.append(args) or [],
    )

    candidates = retriever.retrieve(
        _energy_event("electricity_use"),
        {"energy": 5, "energy_unit": "kWh"},
    )

    assert candidates == []
    assert remote_calls


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


def test_unseen_local_factor_record_ranks_by_transport_metadata_without_code_changes():
    retriever = ClimatiqFactorRetriever(
        local_records_provider=lambda: [
            {
                "activity_id": "fixture.community_coach.distance",
                "name": "Community coach passenger service",
                "description": "Average coach travel per passenger kilometre.",
                "category": "Vehicles",
                "sector": "Transport",
                "unit_type": "PassengerOverDistance",
                "semantic_score": 0.94,
                "source_quality_score": 0.80,
            }
        ],
        remote_search=lambda *args, **kwargs: [],
    )

    candidates = retriever.retrieve(
        _event("bus_ride"),
        {"distance": 9, "distance_unit": "km", "transport_mode": "bus_ride"},
    )

    assert candidates[0].activity_id == "fixture.community_coach.distance"
    assert candidates[0].score >= 0.75
    assert any("unit_type matched required distance parameters" in reason for reason in candidates[0].match_reasons)
    assert any("record semantic_score score: 0.94" in reason for reason in candidates[0].match_reasons)


def test_irrelevant_record_does_not_change_selected_compatible_factor():
    selected = _record(
        "passenger_vehicle-vehicle_type_business_travel_medium_car-fuel_source_petrol",
        "Petrol car (medium) - Business travel",
        "Distance",
    )
    parameters = {
        "distance": 6,
        "distance_unit": "km",
        "fuel_type": "petrol",
        "vehicle_size": "medium",
    }
    baseline = ClimatiqFactorRetriever(
        local_records_provider=lambda: [selected],
        remote_search=lambda *args, **kwargs: [],
    ).retrieve(_event("car_ride"), parameters)
    with_noise = ClimatiqFactorRetriever(
        local_records_provider=lambda: [
            selected,
            _energy_record("fixture.energy.noise", "Grid electricity residual mix"),
        ],
        remote_search=lambda *args, **kwargs: [],
    ).retrieve(_event("car_ride"), parameters)

    assert baseline[0].activity_id == with_noise[0].activity_id


def test_explicit_fuel_trait_changes_ranking_using_metadata_values():
    records = [
        _record(
            "fixture.medium_car-fuel_source_bev",
            "Battery EV car (medium) - Business travel",
            "Distance",
        ),
        _record(
            "fixture.medium_car-fuel_source_diesel",
            "Diesel car (medium) - Business travel",
            "Distance",
        ),
    ]
    retriever = ClimatiqFactorRetriever(
        local_records_provider=lambda: records,
        remote_search=lambda *args, **kwargs: [],
    )
    electric_event = CarbonEvent(
        raw_text="electric car",
        category="transport",
        activity_type="car_ride",
        entities={"fuel_type_source": "user"},
        confidence=Confidence.from_score(0.8),
    )
    diesel_event = CarbonEvent(
        raw_text="diesel car",
        category="transport",
        activity_type="car_ride",
        entities={"fuel_type_source": "user"},
        confidence=Confidence.from_score(0.8),
    )

    electric = retriever.retrieve(
        electric_event,
        {"distance": 5, "distance_unit": "km", "fuel_type": "electric", "vehicle_size": "medium"},
    )
    diesel = retriever.retrieve(
        diesel_event,
        {"distance": 5, "distance_unit": "km", "fuel_type": "diesel", "vehicle_size": "medium"},
    )

    assert electric[0].activity_id.endswith("fuel_source_bev")
    assert diesel[0].activity_id.endswith("fuel_source_diesel")


def test_estimator_rejects_injected_wrong_unit_and_low_score_before_api_call():
    class FixedRetriever:
        def retrieve(self, event, parameters, limit=5):
            return [
                FactorCandidate(
                    activity_id="fixture.energy.wrong_unit",
                    name="Electricity",
                    sector="Energy",
                    category="Electricity",
                    unit_type="Energy",
                    score=0.90,
                ),
                FactorCandidate(
                    activity_id="fixture.transport.weak",
                    name="Weak car match",
                    sector="Transport",
                    category="Vehicles",
                    unit_type="Distance",
                    score=0.40,
                ),
            ]

    class FakeClient:
        def __init__(self):
            self.calls = []

        def estimate(self, activity_id, parameters):
            self.calls.append((activity_id, parameters))
            return ClimatiqEstimate(co2e=1, co2e_unit="kg", ok=True)

    client = FakeClient()
    estimator = ClimatiqEmissionEstimator(
        climatiq_client=client,
        factor_retriever=FixedRetriever(),
    )

    result = estimator.estimate(
        _event("car_ride"),
        {"distance": 5, "distance_unit": "km", "fuel_type": "petrol", "vehicle_size": "medium"},
    )

    assert result.ok is False
    assert client.calls == []
    assert result.issues[0].code == "climatiq.factor_incompatible"


def test_real_retrieval_processes_energy_and_transport_events_independently():
    class FakeClient:
        def __init__(self):
            self.calls = []

        def estimate(self, activity_id, parameters, selector_filters=None):
            self.calls.append(activity_id)
            return ClimatiqEstimate(co2e=0.5, co2e_unit="kg", ok=True)

    client = FakeClient()
    retriever = ClimatiqFactorRetriever(
        local_records_provider=lambda: [
            _record(
                "fixture.transport.petrol_medium",
                "Petrol car (medium) - Business travel",
                "Distance",
            ),
            _energy_record(
                "fixture.energy.grid",
                "Electricity grid residual mix Australia",
                vector_score=0.90,
            ),
        ],
        remote_search=lambda *args, **kwargs: [],
    )
    pipeline = CarbonPipelineV2(
        emission_estimator=ClimatiqEmissionEstimator(
            climatiq_client=client,
            factor_retriever=retriever,
        )
    )

    result = pipeline.run(
        "I drove 4 km in a petrol car and used the heater for 1 hour."
    ).model_dump()

    assert [detail["activity_type"] for detail in result["details"]] == [
        "car_ride",
        "space_heater_use",
    ]
    assert [detail["factor"]["activity_id"] for detail in result["details"]] == [
        "fixture.transport.petrol_medium",
        "fixture.energy.grid",
    ]
    assert client.calls == ["fixture.transport.petrol_medium", "fixture.energy.grid"]


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


def _energy_record(activity_id, name, vector_score=None):
    record = {
        "activity_id": activity_id,
        "name": name,
        "description": "Residential electricity grid residual mix supply.",
        "category": "Electricity",
        "sector": "Energy",
        "unit_type": "Energy",
        "source_quality_score": 0.85,
    }
    if vector_score is not None:
        record["vector_score"] = vector_score
    return record


def _event(activity_type):
    return CarbonEvent(
        raw_text="transport",
        category="transport",
        activity_type=activity_type,
        confidence=Confidence.from_score(0.8),
    )


def _energy_event(activity_type):
    return CarbonEvent(
        raw_text="electricity",
        category="energy",
        activity_type=activity_type,
        confidence=Confidence.from_score(0.8),
    )
