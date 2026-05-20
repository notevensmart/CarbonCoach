import asyncio

from fastapi.testclient import TestClient

from app import main
from app.agent.core.agent import CarbonCoachAgent
from app.agent.core.state import AgentState
from app.services.carbon_pipeline import CarbonEstimator


def test_agent_estimates_journal_activities_without_live_api():
    agent = CarbonCoachAgent(estimator=CarbonEstimator(api_key=None, allow_api=False))
    state = asyncio.run(agent.run("Took a 10 km bus ride and had a vegetarian lunch"))
    assert isinstance(state, AgentState)
    assert state.text.startswith("Took a 10 km bus ride")
    assert state.activity_id
    assert state.total_co2e > 0
    assert len(state.activities) == 2
    assert state.estimate["used_api"] is False


def test_estimate_endpoint_returns_activity_breakdown_without_live_api():
    main.estimator = CarbonEstimator(api_key=None, allow_api=False)
    client = TestClient(main.app)

    response = client.post("/api/estimate", json={"journal": "Used 4 kWh of electricity"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["co2e"] > 0
    assert payload["activities"][0]["parameters"]["energy"] == 4.0
