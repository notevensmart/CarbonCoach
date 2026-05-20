from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable


@dataclass(frozen=True)
class ParameterResult:
    parameters: dict
    source: str
    confidence: str
    notes: str = ""


@dataclass(frozen=True)
class QuantityCandidate:
    value: float
    dimension: str
    unit: str | None
    start: int
    end: int
    raw: str


class JournalParameterExtractor:
    def extract(
        self,
        unit_type: str | None,
        journal_entry: str,
        label: str = "",
        category: str = "",
    ) -> ParameterResult:
        return build_climatiq_parameters(unit_type, journal_entry, label, category)

    def quantities(self, journal_entry: str) -> list[QuantityCandidate]:
        return parse_quantity_candidates(journal_entry)


class FallbackEstimator:
    def estimate(self, category: str, unit_type: str | None, parameters: dict) -> dict:
        return estimate_fallback_emissions(category, unit_type, parameters)


DEFAULT_PARAMETERS = {
    "distance": {"distance": 10, "distance_unit": "km"},
    "passengeroverdistance": {"passengers": 1, "distance": 10, "distance_unit": "km"},
    "energy": {"energy": 5, "energy_unit": "kWh"},
    "weight": {"weight": 0.3, "weight_unit": "kg"},
    "money": {"money": 15, "money_unit": "usd"},
    "area": {"area": 0.5, "area_unit": "m2"},
    "number": {"number": 1},
    "volume": {"volume": 0.5, "volume_unit": "l"},
}

CATEGORY_DEFAULTS = {
    "transport": DEFAULT_PARAMETERS["distance"],
    "waste": DEFAULT_PARAMETERS["weight"],
    "energy": DEFAULT_PARAMETERS["energy"],
    "goods_services": DEFAULT_PARAMETERS["number"],
}

FALLBACK_FACTORS_KG_CO2E = {
    "transport:distance": 0.18,
    "transport:passengeroverdistance": 0.09,
    "energy:energy": 0.4,
    "waste:weight": 0.45,
    "goods_services:money": 0.5,
    "goods_services:number": 2.0,
    "goods_services:weight": 3.0,
    "default:distance": 0.18,
    "default:energy": 0.4,
    "default:weight": 1.0,
    "default:money": 0.5,
    "default:number": 1.0,
    "default:volume": 0.2,
    "default:area": 0.05,
}

NUMBER_WORDS = {
    "a": 1,
    "an": 1,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "couple": 2,
}

UNIT_ALIASES = {
    "km": ("distance", "km", 1.0),
    "kilometer": ("distance", "km", 1.0),
    "kilometers": ("distance", "km", 1.0),
    "kilometre": ("distance", "km", 1.0),
    "kilometres": ("distance", "km", 1.0),
    "m": ("distance", "km", 0.001),
    "meter": ("distance", "km", 0.001),
    "meters": ("distance", "km", 0.001),
    "metre": ("distance", "km", 0.001),
    "metres": ("distance", "km", 0.001),
    "mi": ("distance", "km", 1.60934),
    "mile": ("distance", "km", 1.60934),
    "miles": ("distance", "km", 1.60934),
    "kwh": ("energy", "kWh", 1.0),
    "kwhr": ("energy", "kWh", 1.0),
    "kilowatt hour": ("energy", "kWh", 1.0),
    "kilowatt hours": ("energy", "kWh", 1.0),
    "wh": ("energy", "kWh", 0.001),
    "kg": ("weight", "kg", 1.0),
    "kilogram": ("weight", "kg", 1.0),
    "kilograms": ("weight", "kg", 1.0),
    "g": ("weight", "kg", 0.001),
    "gram": ("weight", "kg", 0.001),
    "grams": ("weight", "kg", 0.001),
    "lb": ("weight", "kg", 0.453592),
    "lbs": ("weight", "kg", 0.453592),
    "pound": ("weight", "kg", 0.453592),
    "pounds": ("weight", "kg", 0.453592),
    "usd": ("money", "usd", 1.0),
    "dollar": ("money", "usd", 1.0),
    "dollars": ("money", "usd", 1.0),
    "$": ("money", "usd", 1.0),
    "aud": ("money", "usd", 0.67),
    "l": ("volume", "l", 1.0),
    "liter": ("volume", "l", 1.0),
    "liters": ("volume", "l", 1.0),
    "litre": ("volume", "l", 1.0),
    "litres": ("volume", "l", 1.0),
    "ml": ("volume", "l", 0.001),
    "milliliter": ("volume", "l", 0.001),
    "milliliters": ("volume", "l", 0.001),
    "m2": ("area", "m2", 1.0),
    "sqm": ("area", "m2", 1.0),
    "square meter": ("area", "m2", 1.0),
    "square meters": ("area", "m2", 1.0),
}

COUNT_NOUNS = (
    "item",
    "items",
    "shirt",
    "shirts",
    "meal",
    "meals",
    "coffee",
    "coffees",
    "ticket",
    "tickets",
    "phone",
    "phones",
    "laptop",
    "laptops",
    "bag",
    "bags",
)

UNIT_PATTERN = "|".join(
    re.escape(unit) for unit in sorted(UNIT_ALIASES, key=len, reverse=True)
)
NUMBER_PATTERN = r"\d+(?:\.\d+)?|a|an|one|two|three|four|five|six|seven|eight|nine|ten|couple"
QUANTITY_RE = re.compile(
    rf"(?P<number>{NUMBER_PATTERN})\s*(?P<unit>{UNIT_PATTERN})\b",
    re.IGNORECASE,
)
MONEY_PREFIX_RE = re.compile(r"(?P<unit>\$)\s*(?P<number>\d+(?:\.\d+)?)")
COUNT_RE = re.compile(
    rf"\b(?P<number>{NUMBER_PATTERN})\s+(?P<noun>{'|'.join(COUNT_NOUNS)})\b",
    re.IGNORECASE,
)


def normalize_unit_type(unit_type: str | None) -> str:
    if not unit_type:
        return "unknown"
    normalized = re.sub(r"[^a-z0-9]", "", unit_type.lower())
    aliases = {
        "passengeroverdistance": "passengeroverdistance",
        "passengertransport": "passengeroverdistance",
        "distance": "distance",
        "energy": "energy",
        "weight": "weight",
        "mass": "weight",
        "money": "money",
        "number": "number",
        "volume": "volume",
        "area": "area",
    }
    return aliases.get(normalized, normalized)


def generate_params(unit_type: str) -> dict | None:
    return DEFAULT_PARAMETERS.get(normalize_unit_type(unit_type))


def get_default_params(category: str) -> dict:
    return dict(CATEGORY_DEFAULTS.get(category, DEFAULT_PARAMETERS["number"]))


def build_climatiq_parameters(
    unit_type: str | None,
    journal_entry: str,
    label: str = "",
    category: str = "",
) -> ParameterResult:
    normalized_type = normalize_unit_type(unit_type)
    candidates = parse_quantity_candidates(journal_entry)
    required_dimension = _dimension_for_unit_type(normalized_type, category)
    quantity = choose_quantity(candidates, required_dimension, label, journal_entry)

    if quantity:
        return ParameterResult(
            parameters=_parameters_from_quantity(normalized_type, quantity),
            source="journal",
            confidence="high",
            notes=f"Extracted '{quantity.raw}' from the journal.",
        )

    default = generate_params(normalized_type) or get_default_params(category)
    return ParameterResult(
        parameters=dict(default),
        source="default",
        confidence="low",
        notes=f"No {required_dimension or normalized_type} quantity found in the journal.",
    )


def parse_quantity_candidates(text: str) -> list[QuantityCandidate]:
    candidates: list[QuantityCandidate] = []

    for match in MONEY_PREFIX_RE.finditer(text):
        candidates.append(_candidate_from_match(match, "$", match.group("number")))

    for match in QUANTITY_RE.finditer(text):
        candidates.append(_candidate_from_match(match, match.group("unit"), match.group("number")))

    for match in COUNT_RE.finditer(text):
        value = _parse_number(match.group("number"))
        if value is not None:
            candidates.append(
                QuantityCandidate(
                    value=value,
                    dimension="number",
                    unit=None,
                    start=match.start(),
                    end=match.end(),
                    raw=match.group(0),
                )
            )

    return _dedupe_candidates(candidates)


def choose_quantity(
    candidates: Iterable[QuantityCandidate],
    dimension: str | None,
    label: str,
    journal_entry: str,
) -> QuantityCandidate | None:
    dimension_matches = [
        candidate for candidate in candidates if not dimension or candidate.dimension == dimension
    ]
    if not dimension_matches:
        return None

    label_position = _best_label_position(label, journal_entry)
    if label_position is None:
        return dimension_matches[0]

    return min(
        dimension_matches,
        key=lambda candidate: min(
            abs(candidate.start - label_position),
            abs(candidate.end - label_position),
        ),
    )


def estimate_fallback_emissions(category: str, unit_type: str | None, parameters: dict) -> dict:
    normalized_type = normalize_unit_type(unit_type)
    factor_key = f"{category}:{normalized_type}"
    factor = FALLBACK_FACTORS_KG_CO2E.get(
        factor_key, FALLBACK_FACTORS_KG_CO2E.get(f"default:{normalized_type}", 1.0)
    )
    activity_amount = _amount_from_parameters(normalized_type, parameters)
    co2e = round(activity_amount * factor, 3)

    return {
        "co2e": co2e,
        "co2e_unit": "kg",
        "source": "fallback",
        "factor": factor,
        "message": "Used local fallback factor because Climatiq did not return an estimate.",
    }


def _candidate_from_match(match: re.Match, raw_unit: str, raw_number: str) -> QuantityCandidate:
    dimension, unit, multiplier = UNIT_ALIASES[raw_unit.lower()]
    value = _parse_number(raw_number)
    if value is None:
        value = 1.0

    return QuantityCandidate(
        value=round(value * multiplier, 6),
        dimension=dimension,
        unit=unit,
        start=match.start(),
        end=match.end(),
        raw=match.group(0),
    )


def _parse_number(value: str) -> float | None:
    normalized = value.strip().lower()
    if normalized in NUMBER_WORDS:
        return float(NUMBER_WORDS[normalized])
    try:
        return float(normalized)
    except ValueError:
        return None


def _parameters_from_quantity(unit_type: str, quantity: QuantityCandidate) -> dict:
    if unit_type == "passengeroverdistance":
        return {"passengers": 1, "distance": quantity.value, "distance_unit": "km"}
    if unit_type == "distance":
        return {"distance": quantity.value, "distance_unit": "km"}
    if unit_type == "energy":
        return {"energy": quantity.value, "energy_unit": "kWh"}
    if unit_type == "weight":
        return {"weight": quantity.value, "weight_unit": "kg"}
    if unit_type == "money":
        return {"money": quantity.value, "money_unit": quantity.unit or "usd"}
    if unit_type == "volume":
        return {"volume": quantity.value, "volume_unit": quantity.unit or "l"}
    if unit_type == "area":
        return {"area": quantity.value, "area_unit": quantity.unit or "m2"}
    if unit_type == "number":
        return {"number": quantity.value}
    return dict(DEFAULT_PARAMETERS["number"])


def _dimension_for_unit_type(unit_type: str, category: str) -> str | None:
    if unit_type == "passengeroverdistance":
        return "distance"
    if unit_type in {"distance", "energy", "weight", "money", "number", "volume", "area"}:
        return unit_type
    if category in CATEGORY_DEFAULTS:
        default = CATEGORY_DEFAULTS[category]
        return next(iter(default)).replace("_unit", "")
    return None


def _amount_from_parameters(unit_type: str, parameters: dict) -> float:
    if unit_type == "passengeroverdistance":
        return float(parameters.get("distance", 1)) * float(parameters.get("passengers", 1))
    for key in ("distance", "energy", "weight", "money", "number", "volume", "area"):
        if key in parameters:
            return float(parameters[key])
    return 1.0


def _best_label_position(label: str, journal_entry: str) -> int | None:
    if not label:
        return None
    lowered = journal_entry.lower()
    label_tokens = [
        token for token in re.findall(r"[a-z0-9]+", label.lower()) if len(token) > 2
    ]
    positions = [lowered.find(token) for token in label_tokens if lowered.find(token) >= 0]
    if not positions:
        return None
    return min(positions)


def _dedupe_candidates(candidates: list[QuantityCandidate]) -> list[QuantityCandidate]:
    seen: set[tuple[int, int, str]] = set()
    deduped: list[QuantityCandidate] = []
    for candidate in candidates:
        key = (candidate.start, candidate.end, candidate.dimension)
        if key not in seen:
            seen.add(key)
            deduped.append(candidate)
    return sorted(deduped, key=lambda item: item.start)
