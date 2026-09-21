"""Validation checks for collected FRED observations."""
from __future__ import annotations
from datetime import date
from pathlib import Path
import pandas as pd

def validate_raw(path: Path, series_id: str) -> list[str]:
    issues=[]
    if not path.exists(): return [f"{series_id}: raw file missing"]
    try: df=pd.read_csv(path)
    except Exception as exc: return [f"{series_id}: cannot read CSV: {exc}"]
    required={"observation_date","value","series_id","source","retrieved_at"}
    missing=required-set(df.columns)
    if missing: return [f"{series_id}: missing columns {sorted(missing)}"]
    if df.empty: return [f"{series_id}: no observations"]
    dates=pd.to_datetime(df["observation_date"], errors="coerce")
    values=pd.to_numeric(df["value"], errors="coerce")
    if dates.isna().any(): issues.append(f"{series_id}: invalid observation dates={int(dates.isna().sum())}")
    if values.isna().any(): issues.append(f"{series_id}: non-numeric/missing values={int(values.isna().sum())}")
    if df["observation_date"].duplicated().any(): issues.append(f"{series_id}: duplicate observation dates")
    if dates.notna().any():
        last_date=dates.max().date(); age=(date.today()-last_date).days
        if age>14: issues.append(f"{series_id}: last observation is {age} days old ({last_date})")
    return issues
