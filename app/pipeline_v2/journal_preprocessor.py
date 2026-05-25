from __future__ import annotations

import re

from app.domain.models import PreprocessedJournal, PreprocessingCorrection


UNIT_RE = re.compile(
    r"(?P<number>\d+(?:\.\d+)?)\s*(?P<unit>kwh|kw|kms?|kilometers?|kilometres?|hrs?|hours?)\b",
    re.IGNORECASE,
)

DOMAIN_TYPO_CORRECTIONS = {
    "toytoa": ("toyota", 0.95),
    "camery": ("camry", 0.90),
}


class JournalPreprocessor:
    """Conservatively normalizes surface formatting without changing meaning."""

    def preprocess(self, journal_entry: str) -> PreprocessedJournal:
        raw = journal_entry
        cleaned = re.sub(r"\s+", " ", raw.strip())
        corrections: list[PreprocessingCorrection] = []

        def replace_unit(match: re.Match) -> str:
            number = match.group("number")
            raw_unit = match.group("unit")
            canonical_unit = _canonical_unit(raw_unit, number)
            replacement = f"{number} {canonical_unit}"
            original = match.group(0)
            if original != replacement:
                corrections.append(
                    PreprocessingCorrection(
                        from_text=original,
                        to=replacement,
                        type="unit_formatting",
                        confidence=0.99,
                    )
                )
            return replacement

        cleaned = UNIT_RE.sub(replace_unit, cleaned)
        cleaned = self._correct_known_domain_typos(cleaned, corrections)

        return PreprocessedJournal(
            raw_journal=raw,
            cleaned_journal=cleaned,
            corrections=corrections,
        )

    def _correct_known_domain_typos(
        self,
        text: str,
        corrections: list[PreprocessingCorrection],
    ) -> str:
        cleaned = text

        for typo, (replacement, confidence) in DOMAIN_TYPO_CORRECTIONS.items():
            pattern = re.compile(rf"\b{re.escape(typo)}\b", re.IGNORECASE)

            def replace_typo(match: re.Match) -> str:
                original = match.group(0)
                corrections.append(
                    PreprocessingCorrection(
                        from_text=original,
                        to=replacement,
                        type="spelling",
                        confidence=confidence,
                    )
                )
                return replacement

            cleaned = pattern.sub(replace_typo, cleaned)

        return cleaned


def _canonical_unit(raw_unit: str, number: str) -> str:
    normalized = raw_unit.lower()
    if normalized == "kw":
        return "kW"
    if normalized == "kwh":
        return "kWh"
    if normalized in {"km", "kms", "kilometer", "kilometers", "kilometre", "kilometres"}:
        return "km"
    if normalized in {"hr", "hrs"}:
        return "hour" if number == "1" else "hours"
    if normalized in {"hour", "hours"}:
        return raw_unit.lower()
    return raw_unit
