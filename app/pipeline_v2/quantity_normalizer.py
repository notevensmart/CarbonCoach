from __future__ import annotations

import re

from app.domain.activity_taxonomy import TRANSPORT_TAXONOMY
from app.domain.models import CarbonEvent, Quantity


QUANTITY_RE = re.compile(
    r"(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>kwh|kw|kms?|kilometers?|kilometres?|hrs?|hours?|mins?|minutes?)\b",
    re.IGNORECASE,
)
COMPACT_K_RE = re.compile(r"\b(?P<value>\d+(?:\.\d+)?)\s*k\b", re.IGNORECASE)
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
            quantities.append(
                Quantity(
                    value=value,
                    unit=unit,
                    dimension=dimension,
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
