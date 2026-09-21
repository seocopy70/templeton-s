#!/usr/bin/env python3
"""Collect Templeton S v0.1 FRED macro data. Collection only."""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from macro.config import FRED_SERIES
from macro.fred import fetch_series
from macro.storage import RAW_DIR, rebuild_processed, save_raw
from macro.validate import validate_raw

OVERLAP_DAYS = 7


def _observation_start(series_id: str) -> str | None:
    """Return an overlap start date to avoid refetching full history."""
    path = RAW_DIR / f"{series_id}.csv"
    if not path.exists():
        return None

    try:
        df = pd.read_csv(path, usecols=["observation_date"])
        dates = pd.to_datetime(df["observation_date"], errors="coerce").dropna()
        if dates.empty:
            return None
        start = dates.max().date() - timedelta(days=OVERLAP_DAYS)
        return start.isoformat()
    except Exception as exc:
        print(f"[macro] WARN {series_id}: cannot determine incremental start: {exc}")
        return None


def main() -> int:
    started = datetime.now(timezone.utc)
    total = len(FRED_SERIES)
    successes = failures = 0

    print(
        f"[macro] start={started.isoformat()} "
        f"series={total} overlap_days={OVERLAP_DAYS}"
    )

    for series_id in FRED_SERIES:
        try:
            observation_start = _observation_start(series_id)
            result = fetch_series(
                series_id, observation_start=observation_start
            )
            path = save_raw(series_id, result["rows"])
            issues = validate_raw(path, series_id)

            hard = [
                x
                for x in issues
                if "missing columns" in x
                or "raw file missing" in x
                or "cannot read" in x
            ]
            if hard:
                failures += 1
                print(
                    f"[macro] FAIL {series_id}: {'; '.join(hard)}"
                )
                continue

            successes += 1
            print(
                f"[macro] OK {series_id} start={observation_start or 'full'} "
                f"rows={result['rows_received']} "
                f"last={result['last_observation']} "
                f"duration={result['duration_sec']}s "
                f"warnings={len(issues)}"
            )
            for issue in issues:
                print(f"[macro] WARN {issue}")

        except Exception as exc:
            failures += 1
            print(f"[macro] FAIL {series_id}: {exc}")

    processed = rebuild_processed(list(FRED_SERIES))
    print(f"[macro] processed={processed}")
    print(
        f"[macro] done success={successes}/{total} failure={failures}"
    )
    return 0 if successes > 0 and failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
