from fastapi.testclient import TestClient

from app import app as app_module
from app.app import app
from app.pipeline import CarbonPipeline, pipeline


client = TestClient(app)


def test_estimate_v2_api_response_shape(v2_api_pipeline):
    app_module.is_ready = True
    app_module.preload_error = None
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
        "estimated": 2.7,
        "fallback_estimated": 0.0,
        "not_estimated": 0.0,
    }
    assert detail["raw_text"] == "I turned on the heater for 3 hours."
    assert detail["status"] == "estimated"
    assert detail["source"] == "climatiq"
    assert detail["parameters"]["energy"] == 4.5
    assert detail["assumptions"][0]["code"] == "space_heater.default_power"
    assert detail["issues"] == []


def test_estimate_v2_requires_journal_field():
    app_module.is_ready = True
    app_module.preload_error = None
    response = client.post("/api/estimate-v2", json={})

    assert response.status_code == 400
    assert response.json()["error"] == "Missing 'journal' field"


def test_estimate_v2_rejects_malformed_journal_type_without_crashing():
    app_module.is_ready = True
    app_module.preload_error = None
    response = client.post("/api/estimate-v2", json={"journal": ["not", "text"]})

    assert response.status_code == 400
    assert response.json()["error"] == "'journal' must be a string"


def test_v1_estimate_route_remains_available(monkeypatch):
    app_module.is_ready = True
    app_module.preload_error = None
    monkeypatch.setattr(
        app_module,
        "pipeline",
        lambda journal: {"result": {"co2e": 1.0, "unit": "kg", "details": []}},
    )

    response = client.post("/api/estimate", json={"journal": "legacy request"})

    assert response.status_code == 200
    assert response.json()["result"]["co2e"] == 1.0


def test_root_serves_react_shell_not_legacy_inline_form():
    response = client.get("/")

    assert response.status_code in {200, 503}
    assert "root" in response.text or "CarbonCoach frontend build not found" in response.text
    assert "Enter Your Daily Journal" not in response.text
    assert 'action="/process"' not in response.text


def test_v1_pipeline_still_imports():
    assert callable(pipeline)
    assert CarbonPipeline is not None
