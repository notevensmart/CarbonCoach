from __future__ import annotations

from typing import Literal


ConfidenceLevel = Literal["high", "medium", "low"]


def confidence_level(score: float) -> ConfidenceLevel:
    if score >= 0.80:
        return "high"
    if score >= 0.50:
        return "medium"
    return "low"


def clamp_score(score: float) -> float:
    return max(0.0, min(1.0, score))

