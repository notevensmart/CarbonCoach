from __future__ import annotations

import re

from app.domain.activity_taxonomy import TRANSPORT_TAXONOMY
from app.domain.models import CarbonEvent, Quantity


QUANTITY_RE = re.compile(
    r"(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>kwh|kw|kms?|kilometers?|kilometres?|hrs?|hours?|mins?|minutes?|kg|kilograms?|g|grams?)\b",
    re.IGNORECASE,
)
COMPACT_K_RE = re.compile(r"\b(?P<value>\d+(?:\.\d+)?)\s*k\b", re.IGNORECASE)
MONEY_RE = re.compile(r"\$(?P<value>\d+(?:\.\d+)?)\b")
HALF_KILOGRAM_RE = re.compile(r"\bhalf\s+(?:a\s+)?kilogram\b", re.IGNORECASE)
COUNT_RE = re.compile(
    r"\b(?P<value>\d+(?:\.\d+)?)\s+(?:coffees?|flat\s+whites?|burritos?|"
    r"burgers?|hamburgers?|servings?|orders?\s+of\s+fries|fries|hot\s+chips|"
    r"pizzas?|sandwich(?:es)?|soft\s+drinks?|sodas?|milks?|loaves|"
    r"bread\s+loaves|snacks?)\b",
    re.IGNORECASE,
)
WORD_COUNT_RE = re.compile(
    r"\b(?P<value>one|two|three|four|five)\s+(?:coffees?|flat\s+whites?|"
    r"burritos?|burgers?|hamburgers?|servings?|orders?\s+of\s+fries|fries|"
    r"hot\s+chips|pizzas?|sandwich(?:es)?|soft\s+drinks?|sodas?|milks?|"
    r"loaves|bread\s+loaves|snacks?)\b",
    re.IGNORECASE,
)
WORD_COUNTS = {"one": 1.0, "two": 2.0, "three": 3.0, "four": 4.0, "five": 5.0}
TRANSPORT_DISTANCE_CONTEXT_RE = re.compile(
    rf"\b(?:{'|'.join(re.escape(term) for metadata in TRANSPORT_TAXONOMY.values() for term in metadata['mode_synonyms'])}|run|ran)\b",
    re.IGNORECASE,
)


class QuantityNormalizer:
    def normalize(self, text: str, event: CarbonEvent | None = None) -> list[Quantity]:
        quantities: list[Quantity] = []
        for match in QUANTITY_RE.finditer(text):
            raw_unit = match.group("unit")
            value = float(match.group("value"))
            dimension, unit = _dimension_and_unit(raw_unit)
            if raw_unit.lower() in {"min", "mins", "minute", "minutes"}:
                value /= 60
            if raw_unit.lower() in {"g", "gram", "grams"}:
                value /= 1000
            quantities.append(
                Quantity(
                    value=value,
                    unit=unit,
                    dimension=dimension,
                    surface=match.group(0),
                    confidence=0.95,
                )
            )
        for match in MONEY_RE.finditer(text):
            quantities.append(
                Quantity(
                    value=float(match.group("value")),
                    unit="USD",
                    dimension="money",
                    surface=match.group(0),
                    confidence=0.95,
                )
            )
        for match in HALF_KILOGRAM_RE.finditer(text):
            quantities.append(
                Quantity(
                    value=0.5,
                    unit="kg",
                    dimension="weight",
                    surface=match.group(0),
                    confidence=0.90,
                )
            )
        for pattern in (COUNT_RE, WORD_COUNT_RE):
            for match in pattern.finditer(text):
                raw_value = match.group("value").lower()
                value = WORD_COUNTS[raw_value] if raw_value in WORD_COUNTS else float(raw_value)
                quantities.append(
                    Quantity(
                        value=value,
                        unit="item",
                        dimension="number",
                        surface=match.group(0),
                        confidence=0.95,
                    )
                )
        quantities.extend(_compact_k_quantities(text, event))
        return quantities


def _dimension_and_unit(raw_unit: str) -> tuple[str, str]:
    normalized = raw_unit.lower()
    if normalized == "kwh":
        return "energy", "kWh"
    if normalized == "kw":
        return "power", "kW"
    if normalized in {"km", "kms", "kilometer", "kilometers", "kilometre", "kilometres"}:
        return "distance", "km"
    if normalized in {"kg", "kilogram", "kilograms"}:
        return "weight", "kg"
    if normalized in {"g", "gram", "grams"}:
        return "weight", "kg"
    return "duration", "hours"


def _compact_k_quantities(text: str, event: CarbonEvent | None) -> list[Quantity]:
    if not _supports_compact_k_as_distance(text, event):
        return []

    quantities: list[Quantity] = []
    occupied_spans = [match.span() for match in QUANTITY_RE.finditer(text)]
    for match in COMPACT_K_RE.finditer(text):
        if any(_spans_overlap(match.span(), occupied) for occupied in occupied_spans):
            continue
        quantities.append(
            Quantity(
                value=float(match.group("value")),
                unit="km",
                dimension="distance",
                surface=match.group(0),
                confidence=0.72,
            )
        )
    return quantities


def _supports_compact_k_as_distance(text: str, event: CarbonEvent | None) -> bool:
    if event is not None and event.category == "transport":
        return True
    return bool(TRANSPORT_DISTANCE_CONTEXT_RE.search(text))


def _spans_overlap(first: tuple[int, int], second: tuple[int, int]) -> bool:
    return first[0] < second[1] and second[0] < first[1]
