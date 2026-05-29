from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import statistics
import sys
import time
from typing import Any
from urllib import error, request


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.pipeline_v2.emission_estimator import EmissionEstimateResult
from app.pipeline_v2.pipeline import CarbonPipelineV2


INCLUDED_STATUSES = {"estimated", "fallback_estimated"}
ATTENTION_STATUSES = {"unresolved", "failed"}


@dataclass(frozen=True)
class ExpectedEvent:
    activity_type: str
    category: str
    status_group: str
    parameters: dict[str, Any] | None = None
    assumption_expected: bool = False
    max_confidence_level: str | None = None


@dataclass(frozen=True)
class EvalCase:
    name: str
    journal: str
    expected: tuple[ExpectedEvent, ...]


class DeterministicEmissionEstimator:
    """Provider-free test double for extraction, parameter, and trust evals."""

    def estimate(self, event, parameters):
        co2e = self._co2e(event, parameters)
        if co2e is None:
            return EmissionEstimateResult(ok=False, failure_status="unresolved")
        return EmissionEstimateResult(
            ok=True,
            co2e=round(co2e, 3),
            co2e_unit="kg",
            activity_id=f"eval.factor.{event.activity_type}",
        )

    def _co2e(self, event, parameters) -> float | None:
        if event.category == "energy" and "energy" in parameters:
            return float(parameters["energy"]) * 0.6
        if event.category == "waste" and "weight" in parameters:
            rates = {
                ("recycling", "plastic"): 0.021,
                ("recycling", "cardboard"): 0.05,
                ("recycling", "paper"): 0.04,
                ("recycling", "glass"): 0.03,
                ("composting", "food_waste"): 0.1,
                ("landfill", "plastic"): 0.12,
                ("landfill", "food_waste"): 0.75,
                ("landfill", "general_waste"): 0.5,
                ("landfill", "mixed_packaging"): 0.5,
            }
            rate = rates.get((parameters.get("disposal_method"), parameters.get("material_class")))
            return None if rate is None else float(parameters["weight"]) * rate
        if event.category == "goods_services":
            if "money" in parameters:
                return None
            rates = {
                "coffee": 0.25,
                "beef_burrito": 2.0,
                "burger": 2.5,
                "fries": 0.55,
                "pizza": 1.8,
                "sandwich": 1.2,
                "beef": 27.0,
                "soft_drink": 0.25,
                "milk": 1.2,
                "bread": 0.7,
                "snacks": 0.4,
            }
            product = parameters.get("product_class")
            rate = rates.get(product)
            if rate is None:
                return None
            amount = parameters.get("number", parameters.get("weight"))
            return None if amount is None else float(amount) * rate
        if event.activity_type == "bus_ride" and "distance" in parameters:
            return float(parameters["distance"]) * 0.1
        if event.activity_type == "train_ride" and "distance" in parameters:
            return float(parameters["distance"]) * 0.04
        if event.activity_type == "flight" and "distance" in parameters:
            return float(parameters["distance"]) * 0.15
        if event.category == "transport" and "distance" in parameters:
            rates = {
                ("medium", "petrol"): 0.192,
                ("medium", "diesel"): 0.209,
                ("medium", "hybrid"): 0.115,
                ("medium", "electric"): 0.09,
                ("large", "petrol"): 0.25,
                ("large", "diesel"): 0.27,
                ("large", "hybrid"): 0.165,
                ("large", "electric"): 0.12,
            }
            rate = rates.get((parameters.get("vehicle_size"), parameters.get("fuel_type")))
            return None if rate is None else float(parameters["distance"]) * rate
        return None


BENCHMARK: tuple[EvalCase, ...] = (
    EvalCase(
        "explicit electricity",
        "I used 5 kWh of electricity.",
        (ExpectedEvent("electricity_use", "energy", "included", {"energy": 5.0}),),
    ),
    EvalCase(
        "heater duration assumption",
        "I turned on the heater for 3 hours.",
        (
            ExpectedEvent(
                "space_heater_use",
                "energy",
                "included",
                {"energy": 4.5, "duration": 3.0},
                assumption_expected=True,
                max_confidence_level="medium",
            ),
        ),
    ),
    EvalCase(
        "heater power and duration",
        "I used a 2 kW heater for 3 hours.",
        (
            ExpectedEvent(
                "space_heater_use",
                "energy",
                "included",
                {"energy": 6.0, "power": 2.0, "duration": 3.0},
                assumption_expected=True,
            ),
        ),
    ),
    EvalCase(
        "missing appliance power",
        "I ran the air conditioner for 2 hours.",
        (ExpectedEvent("air_conditioner_use", "energy", "attention", {"duration": 2.0}),),
    ),
    EvalCase(
        "petrol car distance",
        "I drove 10 km in a petrol car.",
        (ExpectedEvent("car_ride", "transport", "included", {"distance": 10.0}),),
    ),
    EvalCase(
        "diesel SUV distance",
        "I drove 12 km in a diesel SUV.",
        (
            ExpectedEvent(
                "car_ride",
                "transport",
                "included",
                {"distance": 12.0, "fuel_type": "diesel", "vehicle_size": "large"},
            ),
        ),
    ),
    EvalCase(
        "compact transport distance",
        "I took a 7k ride in a Toyota Camry.",
        (
            ExpectedEvent(
                "car_ride",
                "transport",
                "included",
                {"distance": 7.0},
                assumption_expected=True,
                max_confidence_level="medium",
            ),
        ),
    ),
    EvalCase(
        "bus with distance",
        "I rode the bus 8 km to work.",
        (ExpectedEvent("bus_ride", "transport", "included", {"distance": 8.0}),),
    ),
    EvalCase(
        "train with distance",
        "I took the train 20 km.",
        (ExpectedEvent("train_ride", "transport", "included", {"distance": 20.0}),),
    ),
    EvalCase(
        "walking boundary",
        "I walked 2 km to the shop.",
        (ExpectedEvent("walking", "transport", "not_included", {"distance": 2.0}),),
    ),
    EvalCase(
        "bicycle boundary",
        "I cycled 5 km along the river.",
        (ExpectedEvent("bicycle_ride", "transport", "not_included", {"distance": 5.0}),),
    ),
    EvalCase(
        "bus missing distance",
        "I took a bus across town.",
        (ExpectedEvent("bus_ride", "transport", "attention"),),
    ),
    EvalCase(
        "recycling plastic mass",
        "I recycled 500 g of plastic packaging.",
        (ExpectedEvent("recycling", "waste", "included", {"weight": 0.5}),),
    ),
    EvalCase(
        "composting food waste",
        "I composted 1 kg of food scraps.",
        (ExpectedEvent("composting", "waste", "included", {"weight": 1.0}),),
    ),
    EvalCase(
        "landfill plastic mass",
        "I threw away 0.3 kg of plastic packaging in the general waste.",
        (ExpectedEvent("landfill_waste", "waste", "included", {"weight": 0.3}),),
    ),
    EvalCase(
        "recycling missing mass",
        "I recycled some cardboard boxes.",
        (ExpectedEvent("recycling", "waste", "attention"),),
    ),
    EvalCase(
        "coffee count",
        "I bought two coffees.",
        (ExpectedEvent("coffee_purchase", "goods_services", "included", {"number": 2.0}),),
    ),
    EvalCase(
        "coffee spend unresolved",
        "I bought coffee for $6.",
        (ExpectedEvent("coffee_purchase", "goods_services", "attention", {"money": 6.0}),),
    ),
    EvalCase(
        "restaurant singular assumption",
        "I bought a beef burrito.",
        (
            ExpectedEvent(
                "restaurant_meal",
                "goods_services",
                "included",
                {"number": 1.0},
                assumption_expected=True,
                max_confidence_level="medium",
            ),
        ),
    ),
    EvalCase(
        "food weight",
        "I bought 0.5 kg of beef.",
        (ExpectedEvent("food_purchase", "goods_services", "included", {"weight": 0.5}),),
    ),
    EvalCase(
        "mixed commute and energy",
        "I drove 10 km in a petrol car and used 5 kWh of electricity.",
        (
            ExpectedEvent("car_ride", "transport", "included", {"distance": 10.0}),
            ExpectedEvent("electricity_use", "energy", "included", {"energy": 5.0}),
        ),
    ),
    EvalCase(
        "mixed partial journal",
        "I took a bus across town, used the heater for 3 hours, and recycled 500 g plastic.",
        (
            ExpectedEvent("bus_ride", "transport", "attention"),
            ExpectedEvent(
                "space_heater_use",
                "energy",
                "included",
                {"duration": 3.0},
                assumption_expected=True,
                max_confidence_level="medium",
            ),
            ExpectedEvent("recycling", "waste", "included", {"weight": 0.5}),
        ),
    ),
    EvalCase(
        "not included plus estimate",
        "I walked 2 km and bought two coffees.",
        (
            ExpectedEvent("walking", "transport", "not_included", {"distance": 2.0}),
            ExpectedEvent("coffee_purchase", "goods_services", "included", {"number": 2.0}),
        ),
    ),
    EvalCase(
        "unsupported energy and goods",
        "I used a gas heater for 2 hours and bought coffee for $5.",
        (
            ExpectedEvent("space_heater_use", "energy", "attention", {"duration": 2.0}),
            ExpectedEvent("coffee_purchase", "goods_services", "attention", {"money": 5.0}),
        ),
    ),
)

GENERATED_CHALLENGE_FIXTURE = (
    Path(__file__).resolve().parent / "fixtures" / "llm_generated_challenge_set.json"
)


def run_offline_eval(verbose: bool = False) -> dict[str, Any]:
    return {
        "curated_regression": evaluate_cases(BENCHMARK, verbose=verbose),
        "llm_generated_challenge": evaluate_cases(
            load_fixture_cases(GENERATED_CHALLENGE_FIXTURE),
            verbose=verbose,
        ),
    }


def evaluate_cases(cases: tuple[EvalCase, ...], verbose: bool = False) -> dict[str, Any]:
    pipeline = CarbonPipelineV2(emission_estimator=DeterministicEmissionEstimator())
    counters = {
        "expected_events": 0,
        "matched_events": 0,
        "status_checks": 0,
        "status_pass": 0,
        "parameter_checks": 0,
        "parameter_pass": 0,
        "assumption_checks": 0,
        "assumption_pass": 0,
        "confidence_checks": 0,
        "confidence_pass": 0,
        "partial_checks": 0,
        "partial_pass": 0,
        "total_integrity_checks": 0,
        "total_integrity_pass": 0,
    }
    failures: list[str] = []

    for case in cases:
        result = pipeline.run(case.journal).model_dump(by_alias=True)
        details = result["details"]
        used_indexes: set[int] = set()
        case_has_attention = any(item.status_group == "attention" for item in case.expected)
        counters["partial_checks"] += 1
        partial = bool(result.get("coverage", {}).get("estimate_is_partial"))
        if partial == case_has_attention:
            counters["partial_pass"] += 1
        else:
            failures.append(f"{case.name}: partial={partial}, expected {case_has_attention}")

        counters["total_integrity_checks"] += 1
        included_total = round(
            sum(float(detail.get("co2e") or 0) for detail in details if detail["status"] in INCLUDED_STATUSES),
            3,
        )
        if abs(included_total - float(result["total"]["co2e"])) <= 0.001:
            counters["total_integrity_pass"] += 1
        else:
            failures.append(
                f"{case.name}: total {result['total']['co2e']} != included detail sum {included_total}"
            )

        for expected in case.expected:
            counters["expected_events"] += 1
            match_index, detail = _match_detail(details, expected, used_indexes)
            if detail is None:
                failures.append(f"{case.name}: missing {expected.category}/{expected.activity_type}")
                continue
            used_indexes.add(match_index)
            counters["matched_events"] += 1

            counters["status_checks"] += 1
            if _status_group(detail["status"]) == expected.status_group:
                counters["status_pass"] += 1
            else:
                failures.append(
                    f"{case.name}: {expected.activity_type} status {detail['status']} != {expected.status_group}"
                )

            for key, expected_value in (expected.parameters or {}).items():
                counters["parameter_checks"] += 1
                actual_value = detail.get("parameters", {}).get(key)
                if _value_matches(actual_value, expected_value):
                    counters["parameter_pass"] += 1
                else:
                    failures.append(
                        f"{case.name}: {expected.activity_type}.{key}={actual_value!r}, expected {expected_value!r}"
                    )

            if expected.assumption_expected:
                counters["assumption_checks"] += 1
                if detail.get("assumptions"):
                    counters["assumption_pass"] += 1
                else:
                    failures.append(f"{case.name}: expected visible assumption on {expected.activity_type}")

            if expected.max_confidence_level:
                counters["confidence_checks"] += 1
                actual_level = detail.get("confidence", {}).get("level")
                if _confidence_lte(actual_level, expected.max_confidence_level):
                    counters["confidence_pass"] += 1
                else:
                    failures.append(
                        f"{case.name}: confidence {actual_level} exceeds {expected.max_confidence_level}"
                    )

        if verbose:
            print(f"\n{case.name}: {case.journal}")
            for detail in details:
                print(
                    f"  - {detail['category']}/{detail['activity_type']} "
                    f"{detail['status']} params={detail.get('parameters', {})}"
                )

    metrics = {
        "benchmark_cases": len(cases),
        "expected_events": counters["expected_events"],
        "activity_extraction_recall": _ratio(counters["matched_events"], counters["expected_events"]),
        "status_correctness": _ratio(counters["status_pass"], counters["status_checks"]),
        "quantity_parameter_accuracy": _ratio(counters["parameter_pass"], counters["parameter_checks"]),
        "assumption_visibility": _ratio(counters["assumption_pass"], counters["assumption_checks"]),
        "confidence_discipline": _ratio(counters["confidence_pass"], counters["confidence_checks"]),
        "partial_coverage_correctness": _ratio(counters["partial_pass"], counters["partial_checks"]),
        "total_integrity": _ratio(counters["total_integrity_pass"], counters["total_integrity_checks"]),
        "failures": failures,
    }
    return metrics


def run_deployed_eval(url: str, iterations: int, timeout_seconds: int) -> dict[str, Any]:
    journals = [case.journal for case in BENCHMARK[: min(10, len(BENCHMARK))]]
    timings: list[float] = []
    failures: list[str] = []
    for index in range(iterations):
        journal = journals[index % len(journals)]
        started = time.perf_counter()
        try:
            response = _post_json(url, {"journal": journal}, timeout_seconds)
            elapsed = time.perf_counter() - started
            timings.append(elapsed)
            if not isinstance(response, dict) or "total" not in response or "details" not in response:
                failures.append(f"iteration {index + 1}: unexpected response shape")
        except Exception as exc:  # pragma: no cover - network diagnostic path
            failures.append(f"iteration {index + 1}: {exc}")
    return {
        "url": url,
        "iterations": iterations,
        "success_count": len(timings),
        "failure_count": len(failures),
        "success_rate": _ratio(len(timings), iterations),
        "median_seconds": _rounded(statistics.median(timings)) if timings else None,
        "p95_seconds": _rounded(_percentile(timings, 95)) if timings else None,
        "max_seconds": _rounded(max(timings)) if timings else None,
        "failures": failures,
    }


def load_fixture_cases(path: Path) -> tuple[EvalCase, ...]:
    fixture = json.loads(path.read_text(encoding="utf-8"))
    cases = []
    for raw_case in fixture["cases"]:
        cases.append(
            EvalCase(
                name=raw_case["name"],
                journal=raw_case["journal"],
                expected=tuple(
                    ExpectedEvent(
                        activity_type=raw_expected["activity_type"],
                        category=raw_expected["category"],
                        status_group=raw_expected["status_group"],
                        parameters=raw_expected.get("parameters"),
                        assumption_expected=raw_expected.get("assumption_expected", False),
                        max_confidence_level=raw_expected.get("max_confidence_level"),
                    )
                    for raw_expected in raw_case["expected"]
                ),
            )
        )
    return tuple(cases)


def _match_detail(
    details: list[dict[str, Any]],
    expected: ExpectedEvent,
    used_indexes: set[int],
) -> tuple[int, dict[str, Any] | None]:
    for index, detail in enumerate(details):
        if index in used_indexes:
            continue
        if detail.get("category") == expected.category and detail.get("activity_type") == expected.activity_type:
            return index, detail
    return -1, None


def _status_group(status: str) -> str:
    if status in INCLUDED_STATUSES:
        return "included"
    if status in ATTENTION_STATUSES:
        return "attention"
    if status == "not_estimated":
        return "not_included"
    return "other"


def _value_matches(actual: Any, expected: Any) -> bool:
    if isinstance(expected, (int, float)):
        return isinstance(actual, (int, float)) and abs(float(actual) - float(expected)) <= 0.001
    return actual == expected


def _confidence_lte(actual: str | None, maximum: str) -> bool:
    order = {"low": 0, "medium": 1, "high": 2}
    return order.get(str(actual), 99) <= order[maximum]


def _ratio(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return round((numerator / denominator) * 100, 1)


def _rounded(value: float) -> float:
    return round(float(value), 3)


def _percentile(values: list[float], percentile: int) -> float:
    if not values:
        return 0.0
    sorted_values = sorted(values)
    index = max(0, min(len(sorted_values) - 1, round((percentile / 100) * (len(sorted_values) - 1))))
    return sorted_values[index]


def _post_json(url: str, payload: dict[str, Any], timeout_seconds: int) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with request.urlopen(req, timeout=timeout_seconds) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate CarbonCoach behavior and latency.")
    parser.add_argument("--offline", action="store_true", help="Run provider-free intelligence/trust eval.")
    parser.add_argument("--deployed-url", help="Run latency eval against a deployed /api/estimate-v2 URL.")
    parser.add_argument("--iterations", type=int, default=20, help="Deployed latency request count.")
    parser.add_argument("--timeout-seconds", type=int, default=30)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    report: dict[str, Any] = {}
    if args.offline or not args.deployed_url:
        report["offline"] = run_offline_eval(verbose=args.verbose)
    if args.deployed_url:
        report["deployed"] = run_deployed_eval(
            args.deployed_url,
            iterations=args.iterations,
            timeout_seconds=args.timeout_seconds,
        )

    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
