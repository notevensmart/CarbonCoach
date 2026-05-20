from .state import AgentState
from ...services.carbon_pipeline import CarbonEstimator

class CarbonCoachAgent:
    def __init__(self, estimator: CarbonEstimator | None = None):
        self.state: AgentState | None = None
        self.estimator = estimator or CarbonEstimator()

    async def run(self, text: str) -> AgentState:
        """Estimate carbon emissions from a natural-language journal entry."""
        result = self.estimator.estimate(text)
        activities = result.get("activities", [])
        first = activities[0] if activities else {}
        self.state = AgentState(
            text=text,
            candidates=result.get("matches", []),
            activity_id=first.get("activity_id"),
            quantity=first.get("quantity"),
            estimate=result,
            errors=result.get("errors", []),
            activities=activities,
            total_co2e=result.get("co2e", 0.0),
            unit=result.get("unit", "kg CO2e"),
        )
        return self.state
