#!/usr/bin/env python3
"""Collect Templeton S v0.1 FRED macro data. Collection only."""
from __future__ import annotations
import sys
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/"src"))
from macro.config import FRED_SERIES
from macro.fred import fetch_series
from macro.storage import rebuild_processed, save_raw
from macro.validate import validate_raw

def main()->int:
    started=datetime.now(timezone.utc); total=len(FRED_SERIES); successes=failures=0
    print(f"[macro] start={started.isoformat()} series={total}")
    for series_id in FRED_SERIES:
        try:
            result=fetch_series(series_id); path=save_raw(series_id,result["rows"]); issues=validate_raw(path,series_id)
            hard=[x for x in issues if "missing columns" in x or "raw file missing" in x or "cannot read" in x]
            if hard: failures+=1; print(f"[macro] FAIL {series_id}: {'; '.join(hard)}"); continue
            successes+=1
            print(f"[macro] OK {series_id} rows={result['rows_received']} last={result['last_observation']} duration={result['duration_sec']}s warnings={len(issues)}")
            for issue in issues: print(f"[macro] WARN {issue}")
        except Exception as exc:
            failures+=1; print(f"[macro] FAIL {series_id}: {exc}")
    processed=rebuild_processed(list(FRED_SERIES)); print(f"[macro] processed={processed}")
    print(f"[macro] done success={successes}/{total} failure={failures}")
    return 0 if successes>0 and failures==0 else 1

if __name__=="__main__": raise SystemExit(main())
