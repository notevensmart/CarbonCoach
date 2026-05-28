from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.domain.models import CarbonEvent, PreprocessedJournal


@runtime_checkable
class EventExtractor(Protocol):
    def extract(self, journal: PreprocessedJournal) -> list[CarbonEvent]:
        ...


@runtime_checkable
class LLMExtractionClient(Protocol):
    def extract_events_json(self, prompt: str) -> str:
        ...
