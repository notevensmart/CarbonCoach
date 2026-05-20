from app.chains.classify_chain import heuristic_classify_activities
from app.pipeline import CarbonPipeline
from app.services.climatiq_api import ClimatiqEstimate, extract_unit_info, load_activity_lookup
from app.services.param_utils import JournalParameterExtractor


class SuccessfulClimatiqClient:
    def estimate(self, activity_id, parameters):
        return ClimatiqEstimate(
            co2e=1.2345,
            co2e_unit="kg",
            ok=True,
        )


def test_regression_quantity_disambiguation_uses_activity_context():
    extractor = JournalParameterExtractor()
    journal = "I drove 10 km to the mall and bought 2 shirts."

    car = extractor.extract("Distance", journal, "car trip", "transport")
    shirts = extractor.extract("Number", journal, "shirts", "goods_services")

    assert car.parameters == {"distance": 10.0, "distance_unit": "km"}
    assert shirts.parameters == {"number": 2.0}


def test_regression_unit_metadata_comes_from_csv_not_scraping(tmp_path):
    data_file = tmp_path / "activities.csv"
    data_file.write_text(
        "activity_id,name,category,sector,source,unit_type\n"
        "activity_bus,CNG Bus,Vehicles,Transport,EPA,Distance\n",
        encoding="utf-8",
    )

    lookup = load_activity_lookup(tmp_path)

    assert lookup["cng bus"] == "activity_bus"
    assert extract_unit_info("activity_bus") == ("distance", "unknown")


def test_regression_classifier_has_llm_free_fallback():
    activities = heuristic_classify_activities(
        "I took a bus, recycled bottles, and used 3 kWh of electricity."
    )

    assert ("bus ride", "transport") in activities
    assert ("recycling", "waste") in activities
    assert ("electricity use", "energy") in activities


def test_regression_pipeline_prefers_successful_climatiq_result(monkeypatch):
    monkeypatch.setattr(
        "app.pipeline.classify_activities",
        lambda journal: [("bus ride", "transport")],
    )
    monkeypatch.setattr(
        "app.pipeline.retrieve_best_activities",
        lambda labels: {
            "bus ride": {
                "activity_name": "CNG Bus",
                "activity_id": "activity_bus",
            }
        },
    )
    monkeypatch.setattr(
        "app.pipeline.extract_unit_info",
        lambda activity_id: ("Distance", "km"),
    )

    result = CarbonPipeline(climatiq_client=SuccessfulClimatiqClient()).run(
        "I took a 12 km bus ride."
    )

    detail = result["result"]["details"][0]
    assert result["result"]["co2e"] == 1.234
    assert detail["status"] == "ok"
    assert detail["source"] == "climatiq"
    assert "fallback_factor" not in detail
