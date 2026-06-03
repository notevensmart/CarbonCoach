from __future__ import annotations

import json
import os
import re
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
COACHING_SEED_ENV = "CARBONCOACH_V2_COACHING_SEED"
DEFAULT_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_COACHING_MODEL = "deepseek/deepseek-chat-v3-0324:free"
DEFAULT_COACHING_SEED = 42
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
SUMMARY_REPEAT_PATTERNS = (
    r"\bbiggest opportunity\b",
    r"\blargest contributor\b",
    r"\blargest included activity\b",
    r"\blargest estimated\b",
    r"\bmakes up\b",
    r"\baccounts for\b",
    r"\bwhat stood out\b",
)


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
        client: LLMCoachingClient | None = None,
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
        context = build_coaching_context(journal_entry, estimate)
        if self.client is None:
            return build_deterministic_coaching_recommendation(context)
        try:
            payload = self.client.generate_coaching_json(build_coaching_prompt(context))
            recommendation = parse_coaching_recommendation(payload)
            if coaching_repeats_summary(recommendation):
                return build_deterministic_coaching_recommendation(context)
            return recommendation
        except Exception:
            return build_deterministic_coaching_recommendation(context)


def build_sustainability_coach(
    client: LLMCoachingClient | None = None,
    enabled: bool | None = None,
) -> SustainabilityCoach | None:
    is_enabled = coaching_enabled() if enabled is None else enabled
    if not is_enabled:
        return None
    if client is None:
        client = build_default_coaching_client()
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
        seed=_coaching_seed(),
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
        seed: int | None = DEFAULT_COACHING_SEED,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.seed = seed
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
            if self.seed is not None:
                kwargs["seed"] = self.seed
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


def build_deterministic_coaching_recommendation(
    context: Mapping[str, Any],
) -> CoachingRecommendation | None:
    estimated = list(context.get("estimated_activities") or [])
    lower_carbon = list(context.get("lower_carbon_choices") or [])
    attention = list(context.get("unresolved_or_failed_activities") or [])
    if not estimated and not lower_carbon and not attention:
        return None

    top_detail = _top_existing_estimated_activity(estimated)
    action_detail = top_detail or (attention[0] if attention else None)
    positive_feedback = _positive_feedback(lower_carbon)
    action = _deterministic_action(action_detail)
    confidence_note = (
        "This advice is directional because it is based on the activities CarbonCoach could estimate."
        if (context.get("estimate_quality") or {}).get("directional_advice_required")
        else None
    )

    if top_detail:
        category = _category_label(str(top_detail.get("category") or "activity"))
        headline = _action_headline(category, top_detail)
        message = _action_message(category, top_detail)
    elif attention:
        headline = "Add one detail to unlock better guidance"
        message = (
            "CarbonCoach found an activity that needs more detail before it can be "
            "estimated, so the next best coaching step is to clarify that activity."
        )
    else:
        headline = "Keep the lower-carbon choices going"
        message = (
            "This entry includes lower-carbon choices. Keeping those choices repeatable "
            "is a practical way to keep future estimates lower."
        )

    return CoachingRecommendation(
        headline=headline,
        message=message,
        positive_feedback=positive_feedback,
        actions=[action] if action is not None else [],
        confidence_note=confidence_note,
    )


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
        "- Do not repeat the deterministic Summary or 'What stood out' card.\n"
        "- Avoid phrases like biggest opportunity, largest contributor, makes up, "
        "or accounts for.\n"
        "- Focus on the next practical action, not a recap of the estimate.\n"
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


def coaching_repeats_summary(recommendation: CoachingRecommendation) -> bool:
    text = " ".join(
        [
            recommendation.headline,
            recommendation.message,
            recommendation.confidence_note or "",
            *recommendation.positive_feedback,
            *[
                f"{action.title} {action.reason} {action.activity_ref or ''}"
                for action in recommendation.actions
            ],
        ]
    ).lower()
    return any(re.search(pattern, text) for pattern in SUMMARY_REPEAT_PATTERNS)


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


def _top_existing_estimated_activity(
    estimated: list[Mapping[str, Any]],
) -> Mapping[str, Any] | None:
    if not estimated:
        return None
    return max(estimated, key=lambda detail: float(detail.get("co2e") or 0.0))


def _positive_feedback(lower_carbon: list[Mapping[str, Any]]) -> list[str]:
    feedback = []
    seen = set()
    for detail in lower_carbon:
        activity_type = str(detail.get("activity_type") or "")
        if activity_type in seen:
            continue
        seen.add(activity_type)
        label = _activity_label(activity_type)
        if activity_type in {"walking", "bicycle_ride"}:
            feedback.append(f"{label} was a lower-carbon transport choice in this entry.")
        elif activity_type in {"recycling", "composting"}:
            feedback.append(f"{label} kept waste-handling choices visible in this entry.")
    return feedback[:2]


def _deterministic_action(detail: Mapping[str, Any] | None):
    if detail is None:
        return None
    activity = _activity_label(str(detail.get("activity_type") or "activity"))
    raw_text = detail.get("raw_text")
    category = detail.get("category")
    activity_type = detail.get("activity_type")

    if activity_type in {"car_ride", "rideshare"}:
        title = "Compare a lower-carbon trip option"
        reason = "For a similar trip, compare one realistic alternative such as transit, carpooling, or combining errands."
    elif category == "energy":
        title = _energy_action_title(activity_type)
        reason = _energy_action_reason(activity_type)
    elif category == "goods_services":
        title = "Clarify the purchase detail"
        reason = "More specific purchase details can make the next estimate more useful."
    elif category == "waste":
        title = "Keep waste details specific"
        reason = "Material and weight details make waste guidance more useful."
    else:
        title = "Focus on the clearest activity"
        reason = f"{activity} is the best available coaching reference in this estimate."

    return {
        "title": title,
        "reason": reason,
        "activity_ref": str(raw_text) if raw_text else None,
    }


def _action_headline(category: str, detail: Mapping[str, Any]) -> str:
    activity_type = detail.get("activity_type")
    if activity_type in {"car_ride", "rideshare"}:
        return "Try one transport swap"
    if category == "Energy":
        if activity_type == "space_heater_use":
            return "Try one heater tweak next time"
        return "Try one energy-use tweak next time"
    if category == "Goods":
        return "Add purchase detail next time"
    if category == "Waste":
        return "Keep waste details specific"
    return "Choose one practical next step"


def _action_message(category: str, detail: Mapping[str, Any]) -> str:
    activity_type = detail.get("activity_type")
    if activity_type in {"car_ride", "rideshare"}:
        return (
            "For the next similar trip, pick one alternative you would realistically use "
            "and compare it with driving."
        )
    if activity_type == "space_heater_use":
        return (
            "If you use the heater again, try one small change you can repeat, such as "
            "setting a timer for a shorter session, then log the duration next time."
        )
    if category == "Energy":
        return (
            "For the next similar day, choose one energy-use habit to adjust and log the "
            "same detail again so the estimate is easier to compare."
        )
    if category == "Goods":
        return (
            "For the next purchase entry, add the item type and amount so CarbonCoach can "
            "give more useful guidance."
        )
    if category == "Waste":
        return (
            "For the next waste entry, include the material and approximate weight so the "
            "advice can be more specific."
        )
    return "Pick one small, repeatable change for the next similar entry."


def _energy_action_title(activity_type: str | None) -> str:
    if activity_type == "space_heater_use":
        return "Use a timer for the heater"
    return "Log one repeat energy habit"


def _energy_action_reason(activity_type: str | None) -> str:
    if activity_type == "space_heater_use":
        return "A shorter heater session is a clear change you can compare in a future entry."
    return "Repeating the same detail next time makes it easier to compare energy-use changes."


def _activity_label(activity_type: str) -> str:
    return activity_type.replace("_", " ").title() if activity_type else "Activity"


def _category_label(category: str) -> str:
    return {
        "transport": "Transport",
        "energy": "Energy",
        "waste": "Waste",
        "goods_services": "Goods",
    }.get(category, _activity_label(category))


def _load_env_file(filename: str) -> None:
    here = Path(__file__).resolve()
    for parent in [here.parent, *here.parents]:
        candidate = parent / filename
        if candidate.exists():
            load_dotenv(dotenv_path=candidate)
            return


def _coaching_seed() -> int | None:
    configured = os.getenv(COACHING_SEED_ENV)
    if configured is None or configured.strip() == "":
        return DEFAULT_COACHING_SEED
    if configured.strip().lower() in {"none", "off", "false"}:
        return None
    try:
        return int(configured)
    except ValueError:
        return DEFAULT_COACHING_SEED
