"""Minimal FRED API client for reproducible macro collection."""
from __future__ import annotations
import os, time
from datetime import datetime, timezone
from typing import Any
import requests
from .config import FRED_API_URL, FRED_SERIES

def _api_key() -> str:
    key = os.getenv("FRED_API_KEY", "").strip()
    if not key:
        raise ValueError("FRED_API_KEY is not set")
    return key

def fetch_series(series_id: str, observation_start: str | None = None, timeout: int = 30) -> dict[str, Any]:
    if series_id not in FRED_SERIES:
        raise ValueError(f"Unsupported FRED series: {series_id}")
    params = {"series_id": series_id, "api_key": _api_key(), "file_type": "json", "sort_order": "asc"}
    if observation_start:
        params["observation_start"] = observation_start
    started = time.monotonic()
    response = requests.get(FRED_API_URL, params=params, timeout=timeout)
    response.raise_for_status()
    payload = response.json()
    elapsed = round(time.monotonic() - started, 3)
    observations = payload.get("observations")
    if not isinstance(observations, list):
        raise ValueError(f"Unexpected FRED response for {series_id}: observations missing")
    retrieved_at = datetime.now(timezone.utc).isoformat()
    rows = []
    for obs in observations:
        if obs.get("date"):
            rows.append({"observation_date": obs["date"], "value": obs.get("value"), "series_id": series_id, "source": "FRED", "retrieved_at": retrieved_at})
    return {"series_id": series_id, "name": FRED_SERIES[series_id]["name"], "unit": FRED_SERIES[series_id]["unit"], "frequency": FRED_SERIES[series_id]["frequency"], "rows": rows, "rows_received": len(rows), "last_observation": rows[-1]["observation_date"] if rows else None, "retrieved_at": retrieved_at, "duration_sec": elapsed}
