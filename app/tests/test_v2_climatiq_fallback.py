from fastapi.testclient import TestClient

from app import app as app_module
from app.app import app
from app.domain.activity_taxonomy import ACTIVITY_TAXONOMY
from app.domain.fallback_factors import FallbackFactor
from app.domain.models import CarbonEvent, Confidence, FactorCandidate
from app.pipeline_v2.emission_estimator import ClimatiqEmissionEstimator
from app.pipeline_v2.fallback_estimator import LocalFallbackEstimator
from app.pipeline_v2.pipeline import CarbonPipelineV2
from app.services.climatiq_api import ClimatiqEstimate


client = TestClient(app)


class FixedRetriever:
    def __init__(self, candidates):
        self.candidates = candidates

    def retrieve(self, event, parameters, limit=5):
        return list(self.candidates)


class RecordingClient:
    def __init__(self, responses=None):
        self.responses = responses or {}
        self.calls = []

    def estimate(self, activity_id, parameters, selector_filters=None):
        self.calls.append((activity_id, dict(parameters), selector_filters))
        return self.responses.get(
            activity_id,
            ClimatiqEstimate(co2e=None, co2e_unit=None, ok=False, error="API unavailable"),
        )


def test_successful_validated_climatiq_estimate_stays_estimated():
    client = RecordingClient(
        {"fixture.energy": ClimatiqEstimate(co2e=1.75, co2e_unit="kg", ok=True)}
    )
    pipeline = _pipeline([_energy_factor("fixture.energy")], client)

    detail = pipeline.run("I used 5 kWh of electricity.").model_dump()["details"][0]

    assert detail["status"] == "estimated"
    assert detail["source"] == "climatiq"
    assert detail["co2e"] == 1.75
    assert client.calls == [
        (
            "fixture.energy",
            {"energy": 5.0, "energy_unit": "kWh"},
            {"region": "AU", "region_fallback": True},
        )
    ]


def test_validation_failure_skips_candidate_and_tries_next_before_api_call():
    client = RecordingClient(
        {"fixture.energy.valid": ClimatiqEstimate(co2e=2.0, co2e_unit="kg", ok=True)}
    )
    estimator = ClimatiqEmissionEstimator(
        climatiq_client=client,
        factor_retriever=FixedRetriever(
            [
                _transport_factor("fixture.distance.invalid"),
                _energy_factor("fixture.energy.valid"),
            ]
        ),
    )

    result = estimator.estimate(_electricity_event(), {"energy": 5, "energy_unit": "kWh"})

    assert result.ok is True
    assert result.factor.activity_id == "fixture.energy.valid"
    assert [call[0] for call in client.calls] == ["fixture.energy.valid"]


def test_missing_activity_id_is_rejected_before_climatiq_call():
    client = RecordingClient()
    estimator = ClimatiqEmissionEstimator(
        climatiq_client=client,
        factor_retriever=FixedRetriever([_energy_factor("")]),
    )

    result = estimator.estimate(_electricity_event(), {"energy": 5, "energy_unit": "kWh"})

    assert result.ok is False
    assert result.failure_status == "unresolved"
    assert result.issues[0].code == "climatiq.factor_incompatible"
    assert client.calls == []


def test_invalid_factors_use_declared_local_fallback_without_api_call():
    client = RecordingClient()
    pipeline = _pipeline([_transport_factor("fixture.wrong.unit")], client)

    result = pipeline.run("I used 5 kWh of electricity.").model_dump()
    detail = result["details"][0]

    assert detail["status"] == "fallback_estimated"
    assert detail["source"] == "fallback"
    assert detail["co2e"] == 2.0
    assert "climatiq.factor_incompatible" in _issue_codes(detail)
    assert "fallback_factor.energy.au_electricity" in _assumption_codes(detail)
    assert result["total"]["source_breakdown"]["fallback_estimated"] == 2.0
    assert client.calls == []


def test_climatiq_error_becomes_fallback_when_local_factor_exists():
    client = RecordingClient()
    pipeline = _pipeline([_energy_factor("fixture.energy")], client)

    detail = pipeline.run("I used 5 kWh of electricity.").model_dump()["details"][0]

    assert detail["status"] == "fallback_estimated"
    assert detail["source"] == "fallback"
    assert detail["co2e"] == 2.0
    assert "climatiq.estimate_failed" in _issue_codes(detail)
    assert "fallback_factor.energy.au_electricity" in _assumption_codes(detail)
    assert len(client.calls) == 1


def test_failed_specific_candidate_does_not_claim_specificity_for_local_fallback():
    candidate = FactorCandidate(
        activity_id="fixture.mazda.3",
        name="Mazda 3 petrol car",
        sector="Transport",
        category="Vehicles",
        unit_type="Distance",
        score=0.9,
        specificity_match=True,
    )
    pipeline = _pipeline([candidate], RecordingClient())

    detail = pipeline.run("I took a 5 km car ride in a Mazda 3.").model_dump()["details"][0]

    assert detail["status"] == "fallback_estimated"
    assert detail["parameters"]["fuel_type"] == "petrol"
    assert "factor_specificity" not in detail["parameters"]
    assert "vehicle.named.default_petrol_medium" in _assumption_codes(detail)
    assert "vehicle.named_model.unmapped" in _issue_codes(detail)


def test_factor_retrieval_error_is_isolated_and_eligible_for_fallback():
    class RaisingRetriever:
        def retrieve(self, event, parameters, limit=5):
            raise RuntimeError("factor cache unavailable")

    pipeline = CarbonPipelineV2(
        emission_estimator=ClimatiqEmissionEstimator(
            climatiq_client=RecordingClient(),
            factor_retriever=RaisingRetriever(),
        )
    )

    detail = pipeline.run("I used 5 kWh of electricity.").model_dump()["details"][0]

    assert detail["status"] == "fallback_estimated"
    assert detail["issues"][-1]["code"] == "climatiq.factor_retrieval_failed"


def test_api_failure_without_declared_fallback_remains_failed():
    client = RecordingClient()
    pipeline = _pipeline([_flight_factor("fixture.flight")], client)

    detail = pipeline.run("I flew 100 km on a domestic economy flight.").model_dump()["details"][0]

    assert detail["activity_type"] == "flight"
    assert detail["status"] == "failed"
    assert detail["source"] == "climatiq"
    assert detail["co2e"] is None
    assert _assumption_codes(detail) == ["flight.default_factor_parameters"]


def test_missing_factor_without_declared_fallback_is_unresolved():
    pipeline = _pipeline([], RecordingClient())

    detail = pipeline.run("I flew 100 km on a domestic economy flight.").model_dump()["details"][0]

    assert detail["status"] == "unresolved"
    assert detail["source"] == "unresolved"
    assert detail["issues"][-1]["code"] == "climatiq.factor_unavailable"


def test_failure_in_one_event_does_not_prevent_another_climatiq_estimate():
    class PerEventRetriever:
        def retrieve(self, event, parameters, limit=5):
            if event.category == "energy":
                return [_energy_factor("fixture.energy")]
            return [_transport_factor("fixture.car")]

    client = RecordingClient(
        {"fixture.car": ClimatiqEstimate(co2e=0.72, co2e_unit="kg", ok=True)}
    )
    pipeline = CarbonPipelineV2(
        emission_estimator=ClimatiqEmissionEstimator(
            climatiq_client=client,
            factor_retriever=PerEventRetriever(),
        )
    )

    result = pipeline.run(
        "I used 5 kWh of electricity and drove 4 km in a petrol car."
    ).model_dump()

    assert [detail["status"] for detail in result["details"]] == [
        "fallback_estimated",
        "estimated",
    ]
    assert result["total"]["co2e"] == 2.72
    assert result["total"]["source_breakdown"] == {
        "estimated": 0.72,
        "fallback_estimated": 2.0,
        "not_estimated": 0.0,
    }
    assert [call[0] for call in client.calls] == ["fixture.energy", "fixture.car"]


def test_fallback_is_invariant_to_wording_after_parameters_normalize():
    pipeline = _pipeline([], RecordingClient())

    direct = pipeline.run("I used 5 kWh of electricity.").model_dump()["details"][0]
    surrounding = pipeline.run(
        "After lunch I used 5kwh of electricity before reading."
    ).model_dump()["details"][0]

    assert direct["parameters"] == surrounding["parameters"]
    assert direct["co2e"] == surrounding["co2e"] == 2.0
    assert direct["status"] == surrounding["status"] == "fallback_estimated"


def test_new_catalog_factor_uses_same_dimension_and_unit_path(monkeypatch):
    monkeypatch.setitem(
        ACTIVITY_TAXONOMY["electricity_use"],
        "fallback_factor_key",
        "fixture.energy.local",
    )
    fallback = LocalFallbackEstimator(
        factor_catalog={
            "fixture.energy.local": FallbackFactor(
                key="fixture.energy.local",
                name="fixture renewable supply",
                category="energy",
                dimension="energy",
                amount_parameter="energy",
                unit_parameter="energy_unit",
                unit="kWh",
                kg_co2e_per_unit=0.1,
                confidence=0.65,
                source_reference="Deterministic test fixture.",
            )
        }
    )
    pipeline = CarbonPipelineV2(
        emission_estimator=ClimatiqEmissionEstimator(
            climatiq_client=RecordingClient(),
            factor_retriever=FixedRetriever([]),
        ),
        fallback_estimator=fallback,
    )

    detail = pipeline.run("I used 5 kWh of electricity.").model_dump()["details"][0]

    assert detail["status"] == "fallback_estimated"
    assert detail["co2e"] == 0.5
    assert "fallback_factor.fixture.energy.local" in _assumption_codes(detail)


def test_estimate_v2_api_serializes_fallback_status_and_breakdown(monkeypatch):
    pipeline = _pipeline([_energy_factor("fixture.energy")], RecordingClient())
    monkeypatch.setattr(
        app_module,
        "pipeline_v2",
        lambda journal: pipeline.run(journal).model_dump(by_alias=True),
    )
    app_module.is_ready = True
    app_module.preload_error = None

    response = client.post(
        "/api/estimate-v2",
        json={"journal": "I used 5 kWh of electricity."},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["details"][0]["status"] == "fallback_estimated"
    assert data["details"][0]["source"] == "fallback"
    assert data["total"]["source_breakdown"]["fallback_estimated"] == 2.0


def _pipeline(candidates, client):
    return CarbonPipelineV2(
        emission_estimator=ClimatiqEmissionEstimator(
            climatiq_client=client,
            factor_retriever=FixedRetriever(candidates),
        )
    )


def _electricity_event():
    return CarbonEvent(
        raw_text="I used 5 kWh of electricity.",
        category="energy",
        activity_type="electricity_use",
        confidence=Confidence.from_score(0.95),
    )


def _energy_factor(activity_id):
    return FactorCandidate(
        activity_id=activity_id,
        name="Australian grid electricity",
        sector="Energy",
        category="Electricity",
        unit_type="Energy",
        score=0.9,
    )


def _transport_factor(activity_id):
    return FactorCandidate(
        activity_id=activity_id,
        name="Passenger car",
        sector="Transport",
        category="Vehicles",
        unit_type="Distance",
        score=0.9,
    )


def _flight_factor(activity_id):
    return FactorCandidate(
        activity_id=activity_id,
        name="Domestic passenger flight",
        sector="Transport",
        category="Vehicles",
        unit_type="PassengerOverDistance",
        score=0.9,
    )


def _assumption_codes(detail):
    return [assumption["code"] for assumption in detail["assumptions"]]


def _issue_codes(detail):
    return [issue["code"] for issue in detail["issues"]]
