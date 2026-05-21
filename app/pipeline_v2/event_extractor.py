from __future__ import annotations

import re

from app.domain.models import CarbonEvent, Confidence, PreprocessedJournal


HEATER_RE = re.compile(r"\b(space\s+heater|heater|heating)\b", re.IGNORECASE)
ELECTRICITY_RE = re.compile(r"\b(electricity|kwh|kilowatt\s+hours?)\b", re.IGNORECASE)


class JournalEventExtractor:
    def extract(self, journal: PreprocessedJournal) -> list[CarbonEvent]:
        cleaned = journal.cleaned_journal

        if HEATER_RE.search(cleaned):
            return [
                CarbonEvent(
                    raw_text=journal.raw_journal.strip(),
                    category="energy",
                    activity_type="space_heater_use",
                    entities={"device": "heater", "power_source": "electricity"},
                    confidence=Confidence.from_score(0.80),
                )
            ]

        if ELECTRICITY_RE.search(cleaned):
            return [
                CarbonEvent(
                    raw_text=journal.raw_journal.strip(),
                    category="energy",
                    activity_type="electricity_use",
                    entities={"power_source": "electricity"},
                    confidence=Confidence.from_score(0.85),
                )
            ]

        return []

