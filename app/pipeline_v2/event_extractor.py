from __future__ import annotations

import re

from app.domain.models import CarbonEvent, Confidence, PreprocessedJournal


HEATER_RE = re.compile(r"\b(space\s+heater|heater|heating)\b", re.IGNORECASE)
ELECTRICITY_RE = re.compile(r"\b(electricity|kwh|kilowatt\s+hours?)\b", re.IGNORECASE)
CLAUSE_SPLIT_RE = re.compile(r"\s*(?:[.;]|\bthen\b|\band\b)\s+", re.IGNORECASE)


class JournalEventExtractor:
    def extract(self, journal: PreprocessedJournal) -> list[CarbonEvent]:
        events: list[CarbonEvent] = []

        for clause in _candidate_clauses(journal.cleaned_journal):
            if HEATER_RE.search(clause):
                events.append(
                    CarbonEvent(
                        raw_text=clause,
                        category="energy",
                        activity_type="space_heater_use",
                        entities={"device": "heater", "power_source": "electricity"},
                        confidence=Confidence.from_score(0.80),
                    )
                )
                continue

            if ELECTRICITY_RE.search(clause):
                events.append(
                    CarbonEvent(
                        raw_text=clause,
                        category="energy",
                        activity_type="electricity_use",
                        entities={"power_source": "electricity"},
                        confidence=Confidence.from_score(0.85),
                    )
                )

        return events


def _candidate_clauses(text: str) -> list[str]:
    clauses = [clause.strip(" ,") for clause in CLAUSE_SPLIT_RE.split(text)]
    return [clause for clause in clauses if clause]
