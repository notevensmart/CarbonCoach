from fastapi.testclient import TestClient

from app.app import app
from app.pipeline import CarbonPipeline, pipeline


client = TestClient(app)


def test_estimate_v2_api_response_shape():
    response = client.post(
        "/api/estimate-v2",
        json={"journal": "I turned on the heater for 3 hours."},
    )

    assert response.status_code == 200
    data = response.json()
    detail = data["details"][0]

    assert data["version"] == "v2"
    assert data["total"]["unit"] == "kg"
    assert data["total"]["confidence"] == {"score": 0.6, "level": "medium"}
    assert data["total"]["source_breakdown"] == {
        "estimated": 0.0,
        "fallback_estimated": 2.7,
        "not_estimated": 0.0,
    }
    assert detail["raw_text"] == "I turned on the heater for 3 hours."
    assert detail["status"] == "fallback_estimated"
    assert detail["parameters"]["energy"] == 4.5
    assert detail["assumptions"][0]["code"] == "space_heater.default_power"
    assert detail["issues"] == []


def test_estimate_v2_requires_journal_field():
    response = client.post("/api/estimate-v2", json={})

    assert response.status_code == 400
    assert response.json()["error"] == "Missing 'journal' field"


def test_v1_pipeline_still_imports():
    assert callable(pipeline)
    assert CarbonPipeline is not None

