from __future__ import annotations

from dataclasses import dataclass
import csv
import os
from pathlib import Path

from dotenv import load_dotenv
import requests


load_dotenv(dotenv_path="climatiq.env")

CLIMATIQ_BASE_URL = "https://api.climatiq.io"
CLIMATIQ_API_KEY = os.getenv("CLIMATIQ_API_KEY")

_activity_lookup: dict[str, str] = {}
_activity_metadata: dict[str, dict] = {}


@dataclass(frozen=True)
class ClimatiqEstimate:
    co2e: float | None
    co2e_unit: str | None
    ok: bool
    source: str = "climatiq"
    error: str = ""


class ClimatiqClient:
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = CLIMATIQ_BASE_URL,
        data_version: str = "^22",
        timeout: int = 20,
    ) -> None:
        self.api_key = api_key if api_key is not None else CLIMATIQ_API_KEY
        self.base_url = base_url.rstrip("/")
        self.data_version = data_version
        self.timeout = timeout

    def estimate(self, activity_id: str, parameters: dict) -> ClimatiqEstimate:
        if not self.api_key:
            return ClimatiqEstimate(
                co2e=None,
                co2e_unit=None,
                ok=False,
                error="Missing CLIMATIQ_API_KEY.",
            )

        payload = {
            "emission_factor": {
                "activity_id": activity_id,
                "data_version": self.data_version,
            },
            "parameters": parameters,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            response = requests.post(
                f"{self.base_url}/estimate",
                headers=headers,
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()
            return ClimatiqEstimate(
                co2e=data.get("co2e"),
                co2e_unit=data.get("co2e_unit"),
                ok=data.get("co2e") is not None,
            )
        except requests.RequestException as exc:
            message = str(exc)
            if getattr(exc, "response", None) is not None:
                message = f"{exc.response.status_code}: {exc.response.text}"
            return ClimatiqEstimate(
                co2e=None,
                co2e_unit=None,
                ok=False,
                error=message,
            )


def load_activity_lookup(data_dir: str | Path | None = None) -> dict[str, str]:
    lookup, metadata = load_activity_data(data_dir)
    set_activity_lookup(lookup, metadata)
    return lookup


def load_activity_data(data_dir: str | Path | None = None) -> tuple[dict[str, str], dict[str, dict]]:
    directory = _resolve_data_dir(data_dir)
    lookup: dict[str, str] = {}
    metadata: dict[str, dict] = {}

    for filename in directory.iterdir():
        if filename.suffix.lower() != ".csv":
            continue
        with filename.open(encoding="utf-8", newline="") as file:
            reader = csv.DictReader(file)
            for row in reader:
                name = row.get("name", "").strip()
                activity_id = row.get("activity_id", "").strip()
                if not name or not activity_id:
                    continue

                lookup[name.lower()] = activity_id
                metadata[activity_id] = {
                    "activity_id": activity_id,
                    "name": name,
                    "category": row.get("category", "").strip(),
                    "sector": row.get("sector", "").strip(),
                    "source": row.get("source", "").strip(),
                    "unit_type": row.get("unit_type", "").strip().lower(),
                }

    return lookup, metadata


def set_activity_lookup(
    lookup: dict[str, str],
    metadata: dict[str, dict] | None = None,
) -> None:
    global _activity_lookup, _activity_metadata
    _activity_lookup = lookup
    if metadata is not None:
        _activity_metadata = metadata


def get_activity_lookup() -> dict[str, str]:
    if not _activity_lookup:
        raise RuntimeError("activity_lookup is not loaded yet.")
    return _activity_lookup


def get_activity_id(description: str) -> str | None:
    return get_activity_lookup().get(description.strip().lower())


def get_activity_metadata(activity_id: str) -> dict:
    return _activity_metadata.get(activity_id, {})


def extract_unit_info(activity_id: str) -> tuple[str, str]:
    metadata = get_activity_metadata(activity_id)
    return metadata.get("unit_type", "unknown"), metadata.get("unit", "unknown")


def estimate_activity(activity_id: str, parameters: dict) -> ClimatiqEstimate:
    return ClimatiqClient().estimate(activity_id, parameters)


def get_emissions(activity_id: str, parameters: dict) -> tuple[float | None, str | None]:
    result = estimate_activity(activity_id, parameters)
    return result.co2e, result.co2e_unit


def search_activity_ids(query: str, limit: int = 3) -> list[dict]:
    if not CLIMATIQ_API_KEY:
        return []

    payload = {
        "query": query,
        "results_per_page": limit,
        "data_version": "^22",
    }
    headers = {
        "Authorization": f"Bearer {CLIMATIQ_API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.get(
            f"{CLIMATIQ_BASE_URL}/data/v1/search",
            headers=headers,
            params=payload,
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
    except requests.RequestException:
        return []

    return [
        {
            "activity_id": hit.get("activity_id"),
            "name": hit.get("name"),
            "category": hit.get("category"),
            "unit_type": hit.get("unit_type"),
            "unit": hit.get("unit"),
        }
        for hit in data.get("results", [])
    ]


def _resolve_data_dir(data_dir: str | Path | None) -> Path:
    candidates = []
    if data_dir:
        candidates.append(Path(data_dir))
    env_dir = os.getenv("CLIMATIQ_DATA_DIR")
    if env_dir:
        candidates.append(Path(env_dir))

    app_dir = Path(__file__).resolve().parents[1]
    project_dir = app_dir.parent
    candidates.extend(
        [
            app_dir / "tmp" / "data",
            project_dir / "tmp" / "data",
            Path("/tmp/data"),
            Path("C:/tmp/data"),
        ]
    )

    for candidate in candidates:
        if candidate.exists() and any(candidate.glob("*.csv")):
            return candidate

    searched = ", ".join(str(path) for path in candidates)
    raise FileNotFoundError(f"No Climatiq CSV data found. Searched: {searched}")
