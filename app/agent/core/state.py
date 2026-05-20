
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class AgentState:
    text: str
    candidates: Optional[List[Dict[str, Any]]] = None
    activity_id: Optional[str] = None
    quantity: Optional[Dict[str, Any]] = None
    estimate: Optional[Dict[str, Any]] = None
    errors: List[str] = field(default_factory=list)
    activities: List[Dict[str, Any]] = field(default_factory=list)
    total_co2e: float = 0.0
    unit: str = "kg CO2e"
