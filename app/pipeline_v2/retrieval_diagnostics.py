from __future__ import annotations

from app.domain.factor_intents import FactorIntent
from app.domain.models import FactorCandidate


def empty_factor_diagnostics(intent: FactorIntent | None, search_query: str) -> dict:
    return {
        "intent_key": intent.intent_key if intent else None,
        "intent": intent.model_dump() if intent else None,
        "search_query": search_query,
        "selector_filters": intent.selector_filters if intent else {},
        "candidate_count": 0,
        "selected_activity_id": None,
        "selected_reason": None,
        "top_rejections": [],
        "fallback_used": False,
        "fallback_reason": None,
    }


def build_factor_diagnostics(
    *,
    intent: FactorIntent | None,
    search_query: str,
    selector_filters: dict,
    candidate_count: int,
    selected: FactorCandidate | None,
    rejections: list[dict],
    fallback_used: bool = False,
    fallback_reason: str | None = None,
) -> dict:
    return {
        "intent_key": intent.intent_key if intent else None,
        "intent": intent.model_dump() if intent else None,
        "search_query": search_query,
        "selector_filters": selector_filters,
        "candidate_count": candidate_count,
        "selected_activity_id": selected.activity_id if selected else None,
        "selected_reason": _selected_reason(selected),
        "top_rejections": rejections[:8],
        "fallback_used": fallback_used,
        "fallback_reason": fallback_reason,
    }


def combine_attempt_diagnostics(attempts: list[dict]) -> dict | None:
    if not attempts:
        return None
    selected = next(
        (attempt for attempt in attempts if attempt.get("selected_activity_id")),
        attempts[-1],
    )
    combined = dict(selected)
    combined["attempts"] = attempts
    combined["candidate_count"] = sum(
        int(attempt.get("candidate_count") or 0) for attempt in attempts
    )
    if not combined.get("top_rejections"):
        combined["top_rejections"] = [
            rejection
            for attempt in attempts
            for rejection in attempt.get("top_rejections", [])
        ][:8]
    return combined


def with_selected_candidate(diagnostics: dict | None, candidate: FactorCandidate | None) -> dict | None:
    if diagnostics is None:
        return None
    updated = dict(diagnostics)
    updated["selected_activity_id"] = candidate.activity_id if candidate else None
    updated["selected_reason"] = _selected_reason(candidate)
    return updated


def with_fallback(
    diagnostics: dict | None,
    *,
    reason: str,
    assumption_code: str | None = None,
) -> dict | None:
    if diagnostics is None:
        return None
    updated = dict(diagnostics)
    updated["fallback_used"] = True
    updated["fallback_reason"] = reason
    if assumption_code:
        updated["fallback_assumption_code"] = assumption_code
    return updated


def _selected_reason(candidate: FactorCandidate | None) -> str | None:
    if candidate is None:
        return None
    if candidate.match_reasons:
        return "; ".join(candidate.match_reasons[:4])
    return f"selected compatible factor with fit score {candidate.score:.2f}"
