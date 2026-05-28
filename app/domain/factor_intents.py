from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.domain.models import ActivityType, Assumption, Category


class FactorIntent(BaseModel):
    """Structured search contract between validated events and factor retrieval."""

    model_config = ConfigDict(extra="forbid")

    intent_key: str
    category: Category
    activity_type: ActivityType
    unit_type: str
    required_parameters: dict[str, Any] = Field(default_factory=dict)
    semantic_dimensions: dict[str, str] = Field(default_factory=dict)
    hard_constraints: dict[str, str] = Field(default_factory=dict)
    preferred_terms: list[str] = Field(default_factory=list)
    excluded_terms: list[str] = Field(default_factory=list)
    search_query: str
    selector_filters: dict[str, str] = Field(default_factory=dict)
    fallback_strategy: list[str] = Field(default_factory=list)
    assumption_if_generic_fallback_used: Assumption | None = None
