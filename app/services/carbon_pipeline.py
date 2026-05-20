from __future__ import annotations

import csv
import os
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

import requests
from rapidfuzz import fuzz


CLIMATIQ_ESTIMATE_URL = "https://api.climatiq.io/data/v1/estimate"
DEFAULT_DATA_VERSION = "^21"


@dataclass(frozen=True)
class Factor:
    activity_id: str
    name: str
    category: str
    sector: str
    source: str
    unit_type: str
    file_group: str

    @property
    def search_text(self) -> str:
        return " ".join(
            [
                self.activity_id.replace("_", " ").replace("-", " "),
                self.name,
                self.category,
                self.sector,
                self.source,
                self.unit_type,
            ]
        ).lower()

    @property
    def unit_options(self) -> list[str]:
        return [part.strip() for part in self.unit_type.split(",") if part.strip()]


MATCH_RULES: list[dict[str, Any]] = [
    {
        "kind": "flight",
        "keywords": ("flight", "flew", "plane", "airplane", "airport"),
        "query": "International short-haul flight economy",
        "preferred_units": ("PassengerOverDistance",),
        "defaults": {"distance": 800.0, "distance_unit": "km", "passengers": 1},
        "fallback_factor": 0.255,
        "fallback_basis": "kg per passenger-km",
    },
    {
        "kind": "train",
        "keywords": ("train", "rail", "tram", "subway", "metro"),
        "query": "Train",
        "preferred_units": ("PassengerOverDistance",),
        "defaults": {"distance": 8.0, "distance_unit": "km", "passengers": 1},
        "fallback_factor": 0.041,
        "fallback_basis": "kg per passenger-km",
    },
    {
        "kind": "bus",
        "keywords": ("bus", "coach"),
        "query": "Average local bus",
        "preferred_units": ("PassengerOverDistance", "Distance"),
        "defaults": {"distance": 5.0, "distance_unit": "km", "passengers": 1},
        "fallback_factor": 0.105,
        "fallback_basis": "kg per passenger-km",
    },
    {
        "kind": "taxi",
        "keywords": ("taxi", "uber", "rideshare", "ride share"),
        "query": "Regular taxi",
        "preferred_units": ("PassengerOverDistance", "Distance"),
        "defaults": {"distance": 5.0, "distance_unit": "km", "passengers": 1},
        "fallback_factor": 0.21,
        "fallback_basis": "kg per passenger-km",
    },
    {
        "kind": "car",
        "keywords": ("car", "drove", "drive", "driving", "road trip"),
        "query": "Car (medium) - Passenger vehicles",
        "preferred_units": ("Distance", "PassengerOverDistance"),
        "defaults": {"distance": 8.0, "distance_unit": "km", "passengers": 1},
        "fallback_factor": 0.192,
        "fallback_basis": "kg per vehicle-km",
    },
    {
        "kind": "shower",
        "keywords": ("shower", "hot water"),
        "query": "Electricity - Use: sanitary hot water",
        "preferred_units": ("Energy",),
        "defaults": {"energy": 2.0, "energy_unit": "kWh"},
        "fallback_factor": 0.55,
        "fallback_basis": "kg per kWh",
    },
    {
        "kind": "heating",
        "keywords": ("heater", "heating", "heated", "heat pump"),
        "query": "Electricity - Use: heating",
        "preferred_units": ("Energy",),
        "defaults": {"energy": 3.0, "energy_unit": "kWh"},
        "fallback_factor": 0.55,
        "fallback_basis": "kg per kWh",
    },
    {
        "kind": "cooling",
        "keywords": ("air conditioning", "aircon", "ac ", "cooling"),
        "query": "Electricity - Use: air conditioning",
        "preferred_units": ("Energy",),
        "defaults": {"energy": 3.0, "energy_unit": "kWh"},
        "fallback_factor": 0.55,
        "fallback_basis": "kg per kWh",
    },
    {
        "kind": "electricity",
        "keywords": ("electricity", "power", "kwh", "lights", "lighting"),
        "query": "Electricity supplied from grid",
        "preferred_units": ("Energy",),
        "defaults": {"energy": 5.0, "energy_unit": "kWh"},
        "fallback_factor": 0.55,
        "fallback_basis": "kg per kWh",
    },
    {
        "kind": "beef",
        "keywords": ("beef", "burger", "steak"),
        "query": "Beef (fresh)",
        "preferred_units": ("Weight",),
        "defaults": {"weight": 0.25, "weight_unit": "kg"},
        "fallback_factor": 27.0,
        "fallback_basis": "kg per kg",
    },
    {
        "kind": "chicken",
        "keywords": ("chicken", "poultry"),
        "query": "Broiler chicken fresh",
        "preferred_units": ("Weight",),
        "defaults": {"weight": 0.25, "weight_unit": "kg"},
        "fallback_factor": 6.0,
        "fallback_basis": "kg per kg",
    },
    {
        "kind": "coffee",
        "keywords": ("coffee", "latte", "cappuccino"),
        "query": "Coffee",
        "preferred_units": ("Weight", "Money"),
        "defaults": {"weight": 0.02, "weight_unit": "kg", "money": 5.0, "money_unit": "aud"},
        "fallback_factor": 15.0,
        "fallback_basis": "kg per kg",
    },
    {
        "kind": "vegetarian meal",
        "keywords": ("vegetarian", "vegetable", "vegan", "salad"),
        "query": "Vegetables (fresh)",
        "preferred_units": ("Weight",),
        "defaults": {"weight": 0.5, "weight_unit": "kg"},
        "fallback_factor": 2.0,
        "fallback_basis": "kg per kg",
    },
    {
        "kind": "meal",
        "keywords": ("meal", "lunch", "dinner", "breakfast", "takeaway", "restaurant", "cooked"),
        "query": "Restaurant meals",
        "preferred_units": ("Money",),
        "defaults": {"money": 15.0, "money_unit": "aud"},
        "fallback_factor": 0.2,
        "fallback_basis": "kg per AUD",
    },
    {
        "kind": "food waste",
        "keywords": ("food waste", "compost", "leftovers"),
        "query": "Food Waste - Landfilled",
        "preferred_units": ("Weight",),
        "defaults": {"weight": 0.5, "weight_unit": "kg"},
        "fallback_factor": 0.7,
        "fallback_basis": "kg per kg",
    },
    {
        "kind": "waste",
        "keywords": ("waste", "trash", "garbage", "rubbish", "landfill"),
        "query": "Mixed MSW - Landfilled",
        "preferred_units": ("Weight",),
        "defaults": {"weight": 1.0, "weight_unit": "kg"},
        "fallback_factor": 0.6,
        "fallback_basis": "kg per kg",
    },
]


class CarbonEstimator:
    """Journal text to activity matches to Climatiq estimates."""

    def __init__(
        self,
        api_key: str | None = None,
        data_dir: Path | None = None,
        data_version: str | None = None,
        allow_api: bool = True,
        timeout_seconds: float = 12.0,
    ) -> None:
        self.project_root = Path(__file__).resolve().parents[2]
        self.data_dir = data_dir or self.project_root / "Data"
        self.api_key = api_key if api_key is not None else self._load_api_key()
        self.data_version = data_version or os.getenv("CLIMATIQ_DATA_VERSION", DEFAULT_DATA_VERSION)
        offline = os.getenv("CARBONCOACH_OFFLINE", "").strip().lower() in {"1", "true", "yes"}
        self.allow_api = allow_api and not offline
        self.timeout_seconds = timeout_seconds

    def estimate(self, journal: str) -> dict[str, Any]:
        journal = (journal or "").strip()
        if not journal:
            return {
                "journal": journal,
                "co2e": 0.0,
                "unit": "kg CO2e",
                "activities": [],
                "matches": [],
                "errors": ["Add a journal entry before estimating emissions."],
                "used_api": False,
            }

        drafts = self.extract_activities(journal)
        if not drafts:
            return {
                "journal": journal,
                "co2e": 0.0,
                "unit": "kg CO2e",
                "activities": [],
                "matches": [],
                "errors": ["No carbon-relevant activities were detected."],
                "used_api": False,
            }

        activities: list[dict[str, Any]] = []
        matches: list[dict[str, Any]] = []
        errors: list[str] = []
        used_api = False

        for draft in drafts:
            factor, confidence = self.match_factor(draft)
            parameters, quantity, assumptions = self.build_parameters(draft, factor)
            api_result = self._estimate_with_api(factor, parameters)

            if api_result["ok"]:
                co2e = float(api_result["payload"].get("co2e", 0.0))
                method = "climatiq"
                used_api = True
                notices = api_result["payload"].get("notices", [])
                response_factor = api_result["payload"].get("emission_factor") or {}
            else:
                co2e = self._fallback_estimate(draft, parameters, factor)
                method = "fallback"
                notices = [{"severity": "warning", "message": api_result["error"], "code": "local_fallback"}]
                response_factor = {}
                errors.append(f"{draft['label']}: {api_result['error']}")

            activity = {
                "label": draft["label"],
                "kind": draft["kind"],
                "activity_id": factor.activity_id,
                "factor_name": response_factor.get("name") or factor.name,
                "category": response_factor.get("category") or factor.category,
                "sector": factor.sector,
                "source": response_factor.get("source") or factor.source,
                "unit_type": self._select_unit_type(factor, draft),
                "quantity": quantity,
                "parameters": parameters,
                "co2e": round(co2e, 4),
                "unit": "kg CO2e",
                "confidence": confidence,
                "method": method,
                "assumptions": assumptions,
                "notices": notices,
            }
            activities.append(activity)
            matches.append(
                {
                    "label": draft["label"],
                    "activity_id": factor.activity_id,
                    "factor_name": factor.name,
                    "confidence": confidence,
                }
            )

        total = round(sum(activity["co2e"] for activity in activities), 4)
        return {
            "journal": journal,
            "co2e": total,
            "unit": "kg CO2e",
            "activities": activities,
            "matches": matches,
            "errors": errors,
            "used_api": used_api,
            "data_version": self.data_version,
        }

    def extract_activities(self, journal: str) -> list[dict[str, Any]]:
        clauses = self._split_clauses(journal)
        drafts: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()

        for clause in clauses:
            lower_clause = f" {clause.lower()} "
            rule = self._rule_for_clause(lower_clause)
            if not rule:
                continue

            key = (rule["kind"], clause.lower())
            if key in seen:
                continue
            seen.add(key)

            extracted = self._extract_quantities(clause)
            drafts.append(
                {
                    "label": clause,
                    "kind": rule["kind"],
                    "query": rule["query"],
                    "preferred_units": rule["preferred_units"],
                    "defaults": rule["defaults"],
                    "fallback_factor": rule["fallback_factor"],
                    "fallback_basis": rule["fallback_basis"],
                    "extracted": extracted,
                }
            )

        return drafts

    def match_factor(self, draft: dict[str, Any]) -> tuple[Factor, int]:
        factors = self._factors()
        query = draft["query"].lower()
        preferred_units = set(draft["preferred_units"])
        best: tuple[int, Factor] | None = None

        for factor in factors:
            unit_bonus = 12 if preferred_units.intersection(factor.unit_options) else 0
            sector_bonus = 5 if self._sector_matches(draft["kind"], factor) else 0
            score = fuzz.token_set_ratio(query, factor.search_text) + unit_bonus + sector_bonus
            if best is None or score > best[0]:
                best = (int(min(score, 100)), factor)

        if best is None:
            raise RuntimeError("No emission factors are available. Check the Data directory.")
        return best[1], best[0]

    def build_parameters(
        self, draft: dict[str, Any], factor: Factor
    ) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
        unit_type = self._select_unit_type(factor, draft)
        values = {**draft["defaults"], **draft["extracted"]}
        assumptions = [
            f"Assumed {name.replace('_', ' ')} = {value}"
            for name, value in draft["defaults"].items()
            if name not in draft["extracted"]
        ]

        if unit_type == "PassengerOverDistance":
            parameters = {
                "passengers": int(values.get("passengers", 1)),
                "distance": float(values["distance"]),
                "distance_unit": values.get("distance_unit", "km"),
            }
        elif unit_type == "Distance":
            parameters = {
                "distance": float(values["distance"]),
                "distance_unit": values.get("distance_unit", "km"),
            }
        elif unit_type == "Energy":
            parameters = {
                "energy": float(values["energy"]),
                "energy_unit": values.get("energy_unit", "kWh"),
            }
        elif unit_type == "Weight":
            parameters = {
                "weight": float(values["weight"]),
                "weight_unit": values.get("weight_unit", "kg"),
            }
        elif unit_type == "Money":
            parameters = {
                "money": float(values["money"]),
                "money_unit": values.get("money_unit", "aud").lower(),
            }
        elif unit_type == "Number":
            parameters = {"number": float(values.get("number", 1))}
        else:
            parameters = self._fallback_parameters_for_unknown(values)
            assumptions.append(f"Used fallback parameter mapping for unit type {unit_type}.")

        quantity = {
            "value": next(iter(parameters.values())),
            "parameters": parameters,
            "unit_type": unit_type,
        }
        return parameters, quantity, assumptions

    def _estimate_with_api(self, factor: Factor, parameters: dict[str, Any]) -> dict[str, Any]:
        if not self.allow_api:
            return {"ok": False, "error": "API calls are disabled for this run."}
        if not self.api_key:
            return {"ok": False, "error": "CLIMATIQ_API_KEY is not configured; used local fallback factors."}

        body = {
            "emission_factor": {
                "activity_id": factor.activity_id,
                "data_version": self.data_version,
            },
            "parameters": parameters,
        }
        region = os.getenv("CLIMATIQ_REGION", "").strip()
        if region:
            body["emission_factor"]["region"] = region
        try:
            response = requests.post(
                CLIMATIQ_ESTIMATE_URL,
                json=body,
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=self.timeout_seconds,
            )
        except requests.RequestException as exc:
            return {"ok": False, "error": f"Climatiq request failed: {exc}"}

        if response.ok:
            return {"ok": True, "payload": response.json()}

        detail = response.text.strip()
        if len(detail) > 240:
            detail = detail[:237] + "..."
        return {"ok": False, "error": f"Climatiq returned {response.status_code}: {detail}"}

    def _fallback_estimate(self, draft: dict[str, Any], parameters: dict[str, Any], factor: Factor) -> float:
        base = float(draft["fallback_factor"])
        unit_type = self._select_unit_type(factor, draft)
        if unit_type == "PassengerOverDistance":
            return base * float(parameters.get("distance", 0.0)) * float(parameters.get("passengers", 1))
        if unit_type == "Distance":
            return base * float(parameters.get("distance", 0.0))
        if unit_type == "Energy":
            return base * float(parameters.get("energy", 0.0))
        if unit_type == "Weight":
            return base * float(parameters.get("weight", 0.0))
        if unit_type == "Money":
            return base * float(parameters.get("money", 0.0))
        return base * float(parameters.get("number", 1.0))

    def _select_unit_type(self, factor: Factor, draft: dict[str, Any]) -> str:
        options = factor.unit_options or [factor.unit_type]
        for preferred in draft["preferred_units"]:
            if preferred in options:
                return preferred
        for supported in ("PassengerOverDistance", "Distance", "Energy", "Weight", "Money", "Number"):
            if supported in options:
                return supported
        return options[0]

    def _fallback_parameters_for_unknown(self, values: dict[str, Any]) -> dict[str, Any]:
        if "energy" in values:
            return {"energy": float(values["energy"]), "energy_unit": values.get("energy_unit", "kWh")}
        if "distance" in values:
            return {"distance": float(values["distance"]), "distance_unit": values.get("distance_unit", "km")}
        if "weight" in values:
            return {"weight": float(values["weight"]), "weight_unit": values.get("weight_unit", "kg")}
        if "money" in values:
            return {"money": float(values["money"]), "money_unit": values.get("money_unit", "aud").lower()}
        return {"number": float(values.get("number", 1))}

    def _split_clauses(self, journal: str) -> list[str]:
        parts = re.split(r"[.;\n]+|,|\band then\b|\bthen\b|\band\b", journal, flags=re.IGNORECASE)
        return [part.strip(" -") for part in parts if part.strip(" -")]

    def _rule_for_clause(self, lower_clause: str) -> dict[str, Any] | None:
        for rule in MATCH_RULES:
            if any(f" {keyword} " in lower_clause or keyword in lower_clause for keyword in rule["keywords"]):
                return rule
        return None

    def _extract_quantities(self, text: str) -> dict[str, Any]:
        values: dict[str, Any] = {}
        lower = text.lower()

        distance_match = re.search(
            r"(\d+(?:\.\d+)?)\s*(kilometers?|kilometres?|kms?|km|miles?|mi|meters?|metres?|m)\b",
            lower,
        )
        if distance_match:
            amount = float(distance_match.group(1))
            unit = distance_match.group(2)
            values["distance"], values["distance_unit"] = self._normalise_distance(amount, unit)

        energy_match = re.search(r"(\d+(?:\.\d+)?)\s*(kwh|kw h|mwh|wh)\b", lower)
        if energy_match:
            amount = float(energy_match.group(1))
            unit = energy_match.group(2).replace(" ", "")
            values["energy"], values["energy_unit"] = self._normalise_energy(amount, unit)

        weight_match = re.search(
            r"(\d+(?:\.\d+)?)\s*(kilograms?|kgs?|kg|grams?|g|pounds?|lbs?|lb|tonnes?|tons?)\b",
            lower,
        )
        if weight_match:
            amount = float(weight_match.group(1))
            unit = weight_match.group(2)
            values["weight"], values["weight_unit"] = self._normalise_weight(amount, unit)

        money_match = re.search(r"(?:\$|aud\s*|usd\s*)(\d+(?:\.\d+)?)|(\d+(?:\.\d+)?)\s*(?:aud|usd|dollars?)", lower)
        if money_match:
            amount = float(money_match.group(1) or money_match.group(2))
            currency = "usd" if "usd" in lower else "aud"
            values["money"] = amount
            values["money_unit"] = currency

        count_match = re.search(r"\b(\d+)\s*(?:people|passengers|meals|coffees|items|times|loads)\b", lower)
        if count_match:
            count = int(count_match.group(1))
            if any(word in lower for word in ("people", "passengers")):
                values["passengers"] = count
            else:
                values["number"] = count

        return values

    def _normalise_distance(self, amount: float, unit: str) -> tuple[float, str]:
        if unit in {"kilometer", "kilometers", "kilometre", "kilometres", "kms", "km"}:
            return amount, "km"
        if unit in {"mile", "miles", "mi"}:
            return amount, "mi"
        return amount, "m"

    def _normalise_energy(self, amount: float, unit: str) -> tuple[float, str]:
        if unit == "mwh":
            return amount, "MWh"
        if unit == "wh":
            return amount, "Wh"
        return amount, "kWh"

    def _normalise_weight(self, amount: float, unit: str) -> tuple[float, str]:
        if unit in {"gram", "grams", "g"}:
            return amount / 1000.0, "kg"
        if unit in {"pound", "pounds", "lb", "lbs"}:
            return amount * 0.453592, "kg"
        if unit in {"tonne", "tonnes", "ton", "tons"}:
            return amount * 1000.0, "kg"
        return amount, "kg"

    def _sector_matches(self, kind: str, factor: Factor) -> bool:
        sector = factor.sector.lower()
        if kind in {"bus", "train", "taxi", "car", "flight"}:
            return "transport" in sector or "travel" in factor.category.lower()
        if kind in {"electricity", "shower", "heating", "cooling"}:
            return "energy" in sector
        if "waste" in kind:
            return "waste" in sector
        return "consumer goods" in sector or "food" in factor.category.lower()

    def _load_api_key(self) -> str | None:
        env_value = os.getenv("CLIMATIQ_API_KEY")
        if env_value:
            return env_value.strip()

        for path in [self.project_root / "climatiq.env", self.project_root / "key.env", self.project_root / ".env"]:
            value = self._read_env_value(path, "CLIMATIQ_API_KEY")
            if value:
                return value
        return None

    def _read_env_value(self, path: Path, key: str) -> str | None:
        if not path.exists():
            return None
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            name, value = line.split("=", 1)
            if name.strip() == key:
                return value.strip().strip('"').strip("'")
        return None

    def _factors(self) -> list[Factor]:
        return _load_factors(str(self.data_dir))


@lru_cache(maxsize=4)
def _load_factors(data_dir: str) -> list[Factor]:
    directory = Path(data_dir)
    factors: list[Factor] = []
    for file_path in sorted(directory.glob("Climatiq_*_ActivityIDs.csv")):
        file_group = file_path.stem.replace("Climatiq_", "").replace("_ActivityIDs", "").lower()
        with file_path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                factors.append(
                    Factor(
                        activity_id=row.get("activity_id", "").strip(),
                        name=row.get("name", "").strip(),
                        category=row.get("category", "").strip(),
                        sector=row.get("sector", "").strip(),
                        source=row.get("source", "").strip(),
                        unit_type=row.get("unit_type", "").strip(),
                        file_group=file_group,
                    )
                )
    return [factor for factor in factors if factor.activity_id and factor.name]
