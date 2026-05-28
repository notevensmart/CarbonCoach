from __future__ import annotations

import os

from app.domain.activity_taxonomy import ACTIVITY_TAXONOMY
from app.domain.models import CarbonEvent, PreprocessedJournal
from app.pipeline_v2.event_extractor import JournalEventExtractor
from app.pipeline_v2.extraction_schema import parse_llm_events_json
from app.pipeline_v2.extractor_protocol import EventExtractor, LLMExtractionClient


EXTRACTOR_MODE_ENV = "CARBONCOACH_V2_EXTRACTOR_MODE"
SUPPORTED_EXTRACTOR_MODES = {"heuristic", "llm", "hybrid"}


class LLMStructuredEventExtractor:
    def __init__(
        self,
        client: LLMExtractionClient,
        fallback_extractor: EventExtractor | None = None,
    ) -> None:
        self.client = client
        self.fallback_extractor = fallback_extractor or JournalEventExtractor()

    def extract(self, journal: PreprocessedJournal) -> list[CarbonEvent]:
        try:
            payload = self.client.extract_events_json(build_extraction_prompt(journal))
            if not payload or not payload.strip():
                return self._fallback(journal)
            events = parse_llm_events_json(payload, journal)
            if not events:
                return self._fallback(journal)
            return events
        except Exception:
            return self._fallback(journal)

    def _fallback(self, journal: PreprocessedJournal) -> list[CarbonEvent]:
        return self.fallback_extractor.extract(journal)


def build_event_extractor(
    mode: str | None = None,
    llm_client: LLMExtractionClient | None = None,
    fallback_extractor: EventExtractor | None = None,
) -> EventExtractor:
    requested_mode = (mode or os.getenv(EXTRACTOR_MODE_ENV, "heuristic")).strip().lower()
    if requested_mode not in SUPPORTED_EXTRACTOR_MODES:
        requested_mode = "heuristic"

    fallback = fallback_extractor or JournalEventExtractor()
    if requested_mode == "llm" and llm_client is not None:
        return LLMStructuredEventExtractor(llm_client, fallback)

    # Ticket 9 owns true hybrid merging. Until then, hybrid config remains a
    # safe heuristic path unless an explicit extractor is dependency-injected.
    return fallback


def build_extraction_prompt(journal: PreprocessedJournal) -> str:
    categories = "transport, energy, waste, goods_services"
    activity_lines = "\n".join(
        f"- {activity_type}: category={metadata['category']}"
        for activity_type, metadata in sorted(ACTIVITY_TAXONOMY.items())
    )
    return (
        "You extract candidate carbon-relevant events from a personal journal.\n"
        "Return JSON only: no markdown, no prose, no comments.\n"
        "The top-level JSON object must be exactly {\"events\": [...]}.\n"
        "Return candidate events, not final emissions estimates.\n"
        "Allowed categories: "
        f"{categories}.\n"
        "Allowed activity types and categories:\n"
        f"{activity_lines}\n"
        "Rules:\n"
        "- Use only the controlled categories and activity types listed above.\n"
        "- Preserve short raw_text spans copied from the journal.\n"
        "- Include carbon-relevant unsupported activities rather than dropping them.\n"
        "- Avoid estimating quantities that are not stated by the user.\n"
        "- Use goods_services for food, coffee, meals, drinks, clothing, electronics, and purchases.\n"
        "- Use waste only when disposal, recycling, composting, landfill, or rubbish-removal context exists.\n"
        "- Distinguish owning or mentioning an object from disposing of it.\n"
        "- Do not include co2e, activity_id, final confidence, factor metadata, assumptions, or issue codes.\n"
        "- Quantities are hints only. Include a quantity only when its surface text appears in raw_text.\n"
        "- Never invent distance, weight, money, power, duration, or mass.\n"
        "Event JSON shape:\n"
        "{\"raw_text\":\"...\",\"category\":\"...\",\"activity_type\":\"...\","
        "\"quantities\":[{\"value\":1,\"unit\":\"item\",\"dimension\":\"number\","
        "\"surface\":\"two coffees\",\"evidence\":\"explicit\"}],"
        "\"entities\":{\"item\":\"coffee\"}}\n"
        "Journal raw text:\n"
        f"{journal.raw_journal}\n"
        "Journal cleaned text:\n"
        f"{journal.cleaned_journal}"
    )
