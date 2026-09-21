"""CSV storage for the v0.1 macro layer."""
from __future__ import annotations
from pathlib import Path
from typing import Any
import pandas as pd
ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "data" / "macro" / "raw"
PROCESSED_DIR = ROOT / "data" / "macro" / "processed"

def save_raw(series_id: str, rows: list[dict[str, Any]]) -> Path:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    path = RAW_DIR / f"{series_id}.csv"
    new = pd.DataFrame(rows, columns=["observation_date","value","series_id","source","retrieved_at"])
    if path.exists():
        old = pd.read_csv(path, dtype=str)
        new = pd.concat([old, new.astype(str)], ignore_index=True)
    if not new.empty:
        new["observation_date"] = new["observation_date"].astype(str)
        new = new.drop_duplicates(subset=["observation_date"], keep="last").sort_values("observation_date")
    new.to_csv(path, index=False)
    return path

def rebuild_processed(series_ids: list[str]) -> Path:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    frames = []
    for series_id in series_ids:
        path = RAW_DIR / f"{series_id}.csv"
        if path.exists():
            df = pd.read_csv(path)
            if not df.empty:
                df["value"] = pd.to_numeric(df["value"], errors="coerce")
                frames.append(df[["observation_date","series_id","value"]])
    out_path = PROCESSED_DIR / "macro_daily.csv"
    if not frames:
        pd.DataFrame(columns=["observation_date"]).to_csv(out_path, index=False)
        return out_path
    all_rows = pd.concat(frames, ignore_index=True)
    pivot = all_rows.pivot_table(index="observation_date", columns="series_id", values="value", aggfunc="last").reset_index().sort_values("observation_date")
    pivot.to_csv(out_path, index=False)
    return out_path
