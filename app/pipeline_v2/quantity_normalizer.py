from __future__ import annotations

import re

from app.domain.models import Quantity


QUANTITY_RE = re.compile(
    r"(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>kwh|kw|hrs?|hours?)\b",
    re.IGNORECASE,
)


class QuantityNormalizer:
    def normalize(self, text: str) -> list[Quantity]:
        quantities: list[Quantity] = []
        for match in QUANTITY_RE.finditer(text):
            raw_unit = match.group("unit")
            value = float(match.group("value"))
            dimension, unit = _dimension_and_unit(raw_unit)
            quantities.append(
                Quantity(
                    value=value,
                    unit=unit,
                    dimension=dimension,
                    surface=match.group(0),
                    confidence=0.95,
                )
            )
        return quantities


def _dimension_and_unit(raw_unit: str) -> tuple[str, str]:
    normalized = raw_unit.lower()
    if normalized == "kwh":
        return "energy", "kWh"
    if normalized == "kw":
        return "power", "kW"
    return "duration", "hours"

