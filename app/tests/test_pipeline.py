from app.pipeline import CarbonPipeline
from app.services.climatiq_api import ClimatiqEstimate


class FailingClimatiqClient:
    def estimate(self, activity_id, parameters):
        return ClimatiqEstimate(
            co2e=None,
            co2e_unit=None,
            ok=False,
            error="API unavailable",
        )


def test_pipeline_uses_journal_quantity_and_fallback(monkeypatch):
    monkeypatch.setattr(
        "app.pipeline.classify_activities",
        lambda journal: [("bus ride", "transport")],
    )
    monkeypatch.setattr(
        "app.pipeline.retrieve_best_activities",
        lambda labels: {
            "bus ride": {
                "activity_name": "CNG Bus",
                "activity_id": "commercial_vehicle-vehicle_type_bus",
            }
        },
    )
    monkeypatch.setattr(
        "app.pipeline.extract_unit_info",
        lambda activity_id: ("Distance", "km"),
    )

    result = CarbonPipeline(climatiq_client=FailingClimatiqClient()).run(
        "I took a 12 km bus ride."
    )

    detail = result["result"]["details"][0]
    assert result["result"]["co2e"] == 2.16
    assert detail["status"] == "fallback"
    assert detail["source"] == "fallback"
    assert detail["parameters"] == {"distance": 12.0, "distance_unit": "km"}
    assert detail["parameter_source"] == "journal"
    assert detail["error_message"] == "API unavailable"
