"""Small FRED API client for production snapshots.

The collector treats FRED as contextual macro data: failure to fetch macro
data must not prevent a KIS/Score snapshot from being stored.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

import requests

FRED_URL = "https://api.stlouisfed.org/fred/series/observations"
TIMEOUT = 15

# Keep the first version deliberately small and focused on the Templeton
# risk axes. Values are the latest published FRED observations.
SERIES = {
    "DGS10": {"name": "US 10Y Treasury", "unit": "percent"},
    "DFII10": {"name": "US 10Y Real Yield", "unit": "percent"},
    "BAA10Y": {"name": "Moody's Baa - 10Y Treasury Spread", "unit": "percent"},
    "FEDFUNDS": {"name": "Effective Federal Funds Rate", "unit": "percent"},
    "CPIAUCSL": {"name": "US CPI", "unit": "index"},
}


def fetch_fred_context() -> dict[str, Any]:
    """Fetch the latest observation for each configured FRED series.

    Returns a structured status object even when the key or network is
    unavailable. The snapshot collector can therefore preserve market data
    independently of macro-data availability.
    """
    api_key = os.getenv("FRED_API_KEY", "").strip()
    captured_at = datetime.now(timezone.utc).isoformat()

    result: dict[str, Any] = {
        "captured_at_utc": captured_at,
        "source": "fred",
        "status": "ok",
        "series": {},
    }

    if not api_key:
        result["status"] = "missing_api_key"
        result["error"] = "FRED_API_KEY not set"
        return result

    for series_id, meta in SERIES.items():
        try:
            response = requests.get(
                FRED_URL,
                params={
                    "api_key": api_key,
                    "series_id": series_id,
                    "file_type": "json",
                    "sort_order": "desc",
                    "limit": 1,
                },
                timeout=TIMEOUT,
            )
            response.raise_for_status()
            payload = response.json()
            observations = payload.get("observations") or []
            if not observations:
                raise RuntimeError("no observations")

            obs = observations[0]
            value = obs.get("value")
            if value in (None, ".", ""):
                raise RuntimeError(f"invalid observation value: {value!r}")

            result["series"][series_id] = {
                **meta,
                "value": float(value),
                "date": obs.get("date"),
            }
        except Exception as exc:
            result["status"] = "partial" if result["series"] else "error"
            result["series"][series_id] = {
                **meta,
                "value": None,
                "date": None,
                "error": str(exc),
            }

    return result
