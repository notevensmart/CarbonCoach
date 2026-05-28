import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from app.pipeline_v2.emission_estimator import EmissionEstimateResult
from app.pipeline_v2.pipeline import CarbonPipelineV2


class FakeClimatiqEmissionEstimator:
    """Deterministic Climatiq test double; production factors never run in tests."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def estimate(self, event, parameters):
        self.calls.append((event.activity_type, dict(parameters)))
        if event.category == "energy":
            co2e = float(parameters["energy"]) * 0.6
        elif event.category == "goods_services":
            rate = {
                "coffee": 0.25,
                "beef_burrito": 2.0,
                "beef": 27.0,
            }[parameters["product_class"]]
            amount = float(parameters.get("number", parameters.get("weight", 0)))
            co2e = amount * rate
        elif event.category == "waste":
            rate = {
                ("recycling", "plastic"): 0.021,
                ("recycling", "cardboard"): 0.05,
                ("composting", "food_waste"): 0.1,
                ("landfill", "general_waste"): 0.5,
                ("landfill", "mixed_packaging"): 0.5,
            }[(parameters["disposal_method"], parameters["material_class"])]
            co2e = float(parameters["weight"]) * rate
        elif event.activity_type == "bus_ride":
            co2e = float(parameters["distance"]) * 0.1
        elif event.activity_type == "train_ride":
            co2e = float(parameters["distance"]) * 0.04
        elif event.activity_type == "flight":
            co2e = float(parameters["distance"]) * 0.15
        else:
            rate = {
                ("medium", "petrol"): 0.192,
                ("medium", "diesel"): 0.209,
                ("medium", "hybrid"): 0.115,
                ("medium", "electric"): 0.09,
                ("large", "petrol"): 0.25,
                ("large", "diesel"): 0.27,
                ("large", "hybrid"): 0.165,
                ("large", "electric"): 0.12,
            }[(parameters["vehicle_size"], parameters["fuel_type"])]
            co2e = float(parameters["distance"]) * rate
        return EmissionEstimateResult(
            ok=True,
            co2e=round(co2e, 3),
            co2e_unit="kg",
            activity_id=f"fake.climatiq.{event.activity_type}",
        )


@pytest.fixture
def fake_climatiq_estimator():
    return FakeClimatiqEmissionEstimator()


@pytest.fixture
def v2_pipeline(fake_climatiq_estimator):
    return CarbonPipelineV2(emission_estimator=fake_climatiq_estimator)


@pytest.fixture
def v2_api_pipeline(monkeypatch, v2_pipeline):
    import app.app as app_module

    monkeypatch.setattr(
        app_module,
        "pipeline_v2",
        lambda journal: v2_pipeline.run(journal).model_dump(by_alias=True),
    )
    return v2_pipeline
