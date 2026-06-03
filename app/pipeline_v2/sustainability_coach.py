from __future__ import annotations

import json
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from dotenv import load_dotenv
from pydantic import ValidationError

from app.domain.models import (
    CarbonEstimateResponse,
    CoachingRecommendation,
    EstimateDetail,
)


COACHING_ENABLED_ENV = "CARBONCOACH_V2_COACHING_ENABLED"
COACHING_MODEL_ENV = "CARBONCOACH_V2_COACHING_MODEL"
COACHING_BASE_URL_ENV = "CARBONCOACH_V2_COACHING_BASE_URL"
COACHING_API_KEY_ENV = "CARBONCOACH_V2_COACHING_API_KEY"
DEFAULT_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_COACHING_MODEL = "deepseek/deepseek-chat-v3-0324:free"
GREEN_ACTIVITY_TYPES = {"walking", "bicycle_ride", "recycling", "composting"}
INCLUDED_STATUSES = {"estimated", "fallback_estimated"}
ATTENTION_STATUSES = {"unresolved", "failed"}
MAX_CONTEXT_TEXT_LENGTH = 1200
MAX_CONTEXT_ITEMS = 8
CONTEXT_PARAMETER_KEYS = {
    "calculation_boundary",
    "device",
    "disposal_method",
    "distance",
    "distance_unit",
    "duration",
    "duration_unit",
    "emissions_boundary",
    "energy",
    "energy_unit",
    "fuel_type",
    "material_class",
    "money",
    "money_unit",
    "number",
    "number_unit",
    "origin",
    "destination",
    "power",
    "power_source",
    "power_unit",
    "product_class",
    "vehicle_class",
    "vehicle_description",
    "vehicle_size",
    "weight",
    "weight_unit",
}


@runtime_checkable
class LLMCoachingClient(Protocol):
    def generate_coaching_json(self, prompt: str) -> str:
        ...


@runtime_checkable
class SustainabilityCoachService(Protocol):
    def recommend(
        self,
        journal_entry: str,
        estimate: CarbonEstimateResponse,
    ) -> CoachingRecommendation | None:
        ...


class SustainabilityCoach:
    def __init__(
        self,
        client: LLMCoachingClient,
        enabled: bool | None = None,
    ) -> None:
        self.client = client
        self.enabled = coaching_enabled() if enabled is None else enabled

    def recommend(
        self,
        journal_entry: str,
        estimate: CarbonEstimateResponse,
    ) -> CoachingRecommendation | None:
        if not self.enabled:
            return None
        try:
            context = build_coaching_context(journal_entry, estimate)
            payload = self.client.generate_coaching_json(build_coaching_prompt(context))
            return parse_coaching_recommendation(payload)
        except Exception:
            return None


def build_sustainability_coach(
    client: LLMCoachingClient | None = None,
    enabled: bool | None = None,
) -> SustainabilityCoach | None:
    is_enabled = coaching_enabled() if enabled is None else enabled
    if not is_enabled:
        return None
    if client is None:
        client = build_default_coaching_client()
    if client is None:
        return None
    return SustainabilityCoach(client=client, enabled=True)


def build_default_coaching_client() -> LLMCoachingClient | None:
    _load_env_file("key.env")
    api_key = (
        os.getenv(COACHING_API_KEY_ENV)
        or os.getenv("OPENROUTER_API_KEY")
        or os.getenv("OPENAI_API_KEY")
    )
    if not api_key:
        return None

    base_url = os.getenv(COACHING_BASE_URL_ENV)
    if base_url is None and os.getenv("OPENROUTER_API_KEY"):
        base_url = DEFAULT_OPENROUTER_BASE_URL

    return LangChainCoachingClient(
        api_key=api_key,
        base_url=base_url,
        model=os.getenv(COACHING_MODEL_ENV, DEFAULT_COACHING_MODEL),
    )


def coaching_enabled() -> bool:
    _load_env_file("key.env")
    configured = os.getenv(COACHING_ENABLED_ENV)
    if configured is None:
        return True
    return configured.strip().lower() not in {"0", "false", "no", "off"}


class LangChainCoachingClient:
    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_COACHING_MODEL,
        base_url: str | None = DEFAULT_OPENROUTER_BASE_URL,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self._llm = None

    def generate_coaching_json(self, prompt: str) -> str:
        response = self._model().invoke(prompt)
        return str(getattr(response, "content", response)).strip()

    def _model(self):
        if self._llm is None:
            from langchain_openai import ChatOpenAI

            kwargs: dict[str, Any] = {
                "model": self.model,
                "api_key": self.api_key,
                "temperature": 0,
            }
            if self.base_url:
                kwargs["base_url"] = self.base_url
            self._llm = ChatOpenAI(**kwargs)
        return self._llm


def build_coaching_context(
    journal_entry: str,
    estimate: CarbonEstimateResponse,
) -> dict[str, Any]:
    details = list(estimate.details)
    estimated_details = [
        _compact_detail(detail)
        for detail in details
        if detail.status in INCLUDED_STATUSES
    ][:MAX_CONTEXT_ITEMS]
    attention_details = [
        _compact_detail(detail)
        for detail in details
        if detail.status in ATTENTION_STATUSES
    ][:MAX_CONTEXT_ITEMS]
    not_estimated_details = [
        _compact_detail(detail)
        for detail in details
        if detail.status == "not_estimated"
    ][:MAX_CONTEXT_ITEMS]
    lower_carbon_choices = [
        _compact_detail(detail)
        for detail in details
        if detail.activity_type in GREEN_ACTIVITY_TYPES
    ][:MAX_CONTEXT_ITEMS]
    uses_fallback = any(
        detail.status == "fallback_estimated" or detail.source == "fallback"
        for detail in details
    )
    is_low_confidence = estimate.total.confidence.level == "low"
    is_partial = bool(estimate.coverage and estimate.coverage.estimate_is_partial)

    return {
        "journal_text": _truncate(journal_entry),
        "total": {
            "co2e": estimate.total.co2e,
            "unit": estimate.total.unit,
            "confidence": estimate.total.confidence.model_dump(),
            "source_breakdown": estimate.total.source_breakdown.model_dump(),
        },
        "coverage": estimate.coverage.model_dump() if estimate.coverage else None,
        "comparison": _compact_comparison(estimate),
        "estimate_quality": {
            "partial": is_partial,
            "low_confidence": is_low_confidence,
            "uses_fallback": uses_fallback,
            "directional_advice_required": is_partial or is_low_confidence or uses_fallback,
        },
        "estimated_activities": estimated_details,
        "not_estimated_activities": not_estimated_details,
        "lower_carbon_choices": lower_carbon_choices,
        "unresolved_or_failed_activities": attention_details,
    }


def build_coaching_prompt(context: Mapping[str, Any]) -> str:
    return (
        "You are SustainabilityCoach for CarbonCoach.\n"
        "CarbonCoach has already calculated the emissions estimate. You are a "
        "post-estimation coaching layer only.\n"
        "Return JSON only: no markdown, no prose outside JSON, no comments.\n"
        "The JSON object must match exactly this shape:\n"
        "{"
        '"headline":"...",'
        '"message":"...",'
        '"positive_feedback":["..."],'
        '"actions":[{"title":"...","reason":"...","activity_ref":"..."}],'
        '"confidence_note":"..."'
        "}\n"
        "Rules:\n"
        "- Do not calculate, recalculate, override, or mutate emissions totals, "
        "activity details, confidence, or coverage.\n"
        "- Do not invent activities, distances, quantities, prices, emissions "
        "values, or user intent.\n"
        "- Use only the post-estimate context supplied below.\n"
        "- Use supportive, non-shaming language.\n"
        "- Give at most one or two practical actions.\n"
        "- Include positive_feedback when lower-carbon choices are present.\n"
        "- If estimate_quality.directional_advice_required is true, include a "
        "confidence_note saying the advice is directional.\n"
        "- Avoid medical, financial, legal, or lifestyle claims that are not "
        "supported by the estimate.\n"
        "Post-estimate context JSON:\n"
        f"{json.dumps(context, sort_keys=True, separators=(',', ':'))}"
    )


def parse_coaching_recommendation(payload: str) -> CoachingRecommendation:
    data = json.loads(payload)
    if isinstance(data, dict) and set(data.keys()) == {"coaching"}:
        data = data["coaching"]
    try:
        return CoachingRecommendation.model_validate(data)
    except (TypeError, ValidationError) as exc:
        raise ValueError("Invalid coaching recommendation") from exc


def _compact_detail(detail: EstimateDetail) -> dict[str, Any]:
    compact: dict[str, Any] = {
        "raw_text": _truncate(detail.raw_text, 240),
        "category": detail.category,
        "activity_type": detail.activity_type,
        "status": detail.status,
        "source": detail.source,
        "co2e": detail.co2e,
        "unit": detail.unit,
        "confidence": detail.confidence.model_dump(),
    }
    parameters = _compact_parameters(detail.parameters)
    if parameters:
        compact["parameters"] = parameters
    assumptions = _messages(detail.assumptions)
    if assumptions:
        compact["assumptions"] = assumptions
    issues = _messages(detail.issues)
    if issues:
        compact["issues"] = issues
    return compact


def _compact_parameters(parameters: Mapping[str, Any]) -> dict[str, Any]:
    compact = {}
    for key in sorted(CONTEXT_PARAMETER_KEYS):
        if key not in parameters:
            continue
        value = parameters[key]
        if isinstance(value, str):
            compact[key] = _truncate(value, 160)
        elif isinstance(value, (int, float, bool)) or value is None:
            compact[key] = value
    return compact


def _compact_comparison(estimate: CarbonEstimateResponse) -> dict[str, Any] | None:
    comparison = estimate.comparison
    if comparison is None:
        return None
    return {
        "message": comparison.message,
        "reference_label": comparison.reference_label,
        "approximate": comparison.approximate,
    }


def _messages(items: list[Any]) -> list[str]:
    messages = []
    for item in items[:3]:
        message = getattr(item, "message", None) or str(item)
        if message:
            messages.append(_truncate(message, 240))
    return messages


def _truncate(value: str, limit: int = MAX_CONTEXT_TEXT_LENGTH) -> str:
    text = " ".join(str(value).split())
    return text if len(text) <= limit else f"{text[: limit - 3]}..."


def _load_env_file(filename: str) -> None:
    here = Path(__file__).resolve()
    for parent in [here.parent, *here.parents]:
        candidate = parent / filename
        if candidate.exists():
            load_dotenv(dotenv_path=candidate)
            return
