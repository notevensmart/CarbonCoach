from app.domain.models import CarbonEvent, Confidence
from app.domain.vehicle_metadata import (
    CachedVehicleMetadataProvider,
    VehicleMetadataRecord,
)
from app.pipeline_v2.emission_estimator import ClimatiqEmissionEstimator
from app.pipeline_v2.entity_enricher import EntityEnricher
from app.pipeline_v2.pipeline import CarbonPipelineV2
from app.services.climatiq_api import ClimatiqEstimate


def test_provider_record_enriches_arbitrary_vehicle_without_extraction_branch(
    fake_climatiq_estimator,
):
    provider = CachedVehicleMetadataProvider(
        [
            VehicleMetadataRecord(
                record_id="fixture.acme.horizon.hybrid",
                display_name="Acme Horizon Touring",
                aliases=("acme horizon touring",),
                vehicle_make="acme",
                vehicle_model="horizon touring",
                vehicle_size="large",
                fuel_type="hybrid",
                fuel_certainty="fixed",
                confidence=0.82,
                assumption_code="vehicle.fixture.acme_horizon.default_hybrid_large",
            )
        ]
    )
    pipeline = _pipeline(provider, fake_climatiq_estimator)

    detail = pipeline.run("I drove 8 km in an Acme Horizon Touring.").model_dump()["details"][0]

    assert detail["parameters"]["vehicle_description"] == "Acme Horizon Touring"
    assert detail["parameters"]["vehicle_metadata_record_id"] == "fixture.acme.horizon.hybrid"
    assert detail["parameters"]["fuel_type"] == "hybrid"
    assert detail["parameters"]["vehicle_size"] == "large"
    assert detail["status"] == "estimated"


def test_ambiguous_provider_variants_do_not_guess_fuel(fake_climatiq_estimator):
    provider = CachedVehicleMetadataProvider(
        [
            _record("fixture.northwind.orbit.petrol", "petrol"),
            _record("fixture.northwind.orbit.electric", "electric"),
        ]
    )
    pipeline = _pipeline(provider, fake_climatiq_estimator)

    detail = pipeline.run("I drove 5 km in a Northwind Orbit.").model_dump()["details"][0]

    assert detail["parameters"]["fuel_type"] == "petrol"
    assert "vehicle_metadata_record_id" not in detail["parameters"]
    assert "vehicle.metadata.ambiguous" in _issue_codes(detail)
    assert "vehicle.named.default_petrol_medium" in _assumption_codes(detail)


def test_explicit_user_fuel_overrides_provider_default(fake_climatiq_estimator):
    provider = CachedVehicleMetadataProvider(
        [
            VehicleMetadataRecord(
                record_id="fixture.contoso.trail.diesel",
                display_name="Contoso Trail",
                aliases=("contoso trail",),
                vehicle_make="contoso",
                vehicle_model="trail",
                vehicle_size="large",
                fuel_type="diesel",
                fuel_certainty="default",
                assumption_code="vehicle.fixture.contoso_trail.default_diesel",
            )
        ]
    )
    pipeline = _pipeline(provider, fake_climatiq_estimator)

    detail = pipeline.run("I drove 4 km in an electric Contoso Trail.").model_dump()["details"][0]

    assert detail["parameters"]["fuel_type"] == "electric"
    assert "vehicle.fuel_type.user_override" in _assumption_codes(detail)


def test_year_specific_provider_record_resolves_variant(fake_climatiq_estimator):
    provider = CachedVehicleMetadataProvider(
        [
            VehicleMetadataRecord(
                record_id="fixture.meridian.arc.2022.petrol",
                display_name="2022 Meridian Arc",
                aliases=("meridian arc",),
                vehicle_make="meridian",
                vehicle_model="arc",
                year=2022,
                vehicle_size="medium",
                fuel_type="petrol",
                fuel_certainty="fixed",
            ),
            VehicleMetadataRecord(
                record_id="fixture.meridian.arc.2023.electric",
                display_name="2023 Meridian Arc",
                aliases=("meridian arc",),
                vehicle_make="meridian",
                vehicle_model="arc",
                year=2023,
                vehicle_size="medium",
                fuel_type="electric",
                fuel_certainty="fixed",
            ),
        ]
    )
    pipeline = _pipeline(provider, fake_climatiq_estimator)

    detail = pipeline.run("I drove 5 km in a 2023 Meridian Arc.").model_dump()["details"][0]

    assert detail["parameters"]["vehicle_year"] == 2023
    assert detail["parameters"]["vehicle_metadata_record_id"] == "fixture.meridian.arc.2023.electric"
    assert detail["parameters"]["fuel_type"] == "electric"


def test_provider_failure_keeps_visible_named_vehicle_estimate(fake_climatiq_estimator):
    class FailingProvider:
        def lookup(self, query):
            raise RuntimeError("cache unavailable")

    pipeline = _pipeline(FailingProvider(), fake_climatiq_estimator)
    detail = pipeline.run("I drove 5 km in a Fabrikam Metro.").model_dump()["details"][0]

    assert detail["parameters"]["vehicle_description"] == "Fabrikam Metro"
    assert detail["parameters"]["fuel_type"] == "petrol"
    assert detail["status"] == "estimated"
    assert "vehicle.metadata.unavailable" in _issue_codes(detail)


def test_climatiq_estimator_uses_only_compatible_remote_factor_and_dimensions():
    search_queries = []

    class FakeClient:
        def __init__(self):
            self.calls = []

        def estimate(self, activity_id, parameters):
            self.calls.append((activity_id, parameters))
            return ClimatiqEstimate(co2e=1.5, co2e_unit="kg", ok=True)

    client = FakeClient()

    def fake_search(query, limit):
        search_queries.append((query, limit))
        return [
            {
                "activity_id": "wrong",
                "name": "Grid electricity",
                "sector": "Energy",
                "unit_type": "energy",
            },
            {
                "activity_id": "climatiq.transport.distance",
                "name": "Battery EV car (large) - Business travel",
                "sector": "Transport",
                "unit_type": "distance",
            },
        ]

    estimator = ClimatiqEmissionEstimator(climatiq_client=client, activity_search=fake_search)
    event = CarbonEvent(
        raw_text="I drove 5 km in an electric SUV.",
        category="transport",
        activity_type="car_ride",
        confidence=Confidence.from_score(0.9),
    )
    result = estimator.estimate(
        event,
        {
            "distance": 5,
            "distance_unit": "km",
            "fuel_type": "electric",
            "vehicle_size": "large",
        },
    )

    assert result.ok is True
    assert "electric large" in search_queries[0][0]
    assert client.calls == [
        ("climatiq.transport.distance", {"distance": 5, "distance_unit": "km"})
    ]


def _pipeline(provider, fake_climatiq_estimator):
    return CarbonPipelineV2(
        entity_enricher=EntityEnricher(vehicle_metadata_provider=provider),
        emission_estimator=fake_climatiq_estimator,
    )


def _record(record_id, fuel_type):
    return VehicleMetadataRecord(
        record_id=record_id,
        display_name="Northwind Orbit",
        aliases=("northwind orbit",),
        vehicle_make="northwind",
        vehicle_model="orbit",
        vehicle_size="medium",
        fuel_type=fuel_type,
        fuel_certainty="unknown",
        assumption_code=f"vehicle.fixture.northwind_orbit.default_{fuel_type}",
    )


def _assumption_codes(detail):
    return [assumption["code"] for assumption in detail["assumptions"]]


def _issue_codes(detail):
    return [issue["code"] for issue in detail["issues"]]
