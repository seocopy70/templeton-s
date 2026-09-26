"""Single source of truth for scheduled Templeton S collection."""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from typing import Any

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from config import SYMBOLS, validate_config
from kis_client import KISClient
from market_data import fetch_all_prices
from market_overview import fetch_market_overview
from macro.fred import fetch_series
from macro.config import FRED_SERIES
from score_engine import calculate_templeton_score, MARKET_BENCHMARK_SYMBOL

from db.neon_client import (
    begin_collection_run, finish_collection_run, insert_snapshot,
    insert_score, insert_ai_judgment, insert_panic_state,
    latest_panic_state,
)
from .ai import get_provider, PROMPT_VERSION
from .panic import evaluate


def _macro_snapshot() -> dict[str, Any]:
    result: dict[str, Any] = {}
    for series_id in FRED_SERIES:
        try:
            data = fetch_series(series_id)
            last = data.get("rows", [])[-1] if data.get("rows") else None
            result[series_id] = {
                "observation": last,
                "retrieved_at": data.get("retrieved_at"),
                "frequency": data.get("frequency"),
            }
        except Exception as exc:
            result[series_id] = {"error": str(exc)}
    return result


def run_collection(slot: str | None = None) -> str:
    validate_config()
    captured_at = datetime.now(timezone.utc)
    run_id = begin_collection_run(slot=slot, captured_at=captured_at)
    try:
        client = KISClient()
        prices = fetch_all_prices(client)
        by_symbol = {str(x.get("symbol")): x for x in prices}

        for symbol, row in by_symbol.items():
            if row.get("error"):
                continue
            try:
                row.update(client.get_financial_ratios(symbol))
            except Exception as exc:
                row["financial_error"] = str(exc)

        market = by_symbol.get(MARKET_BENCHMARK_SYMBOL)
        overview = fetch_market_overview(client)
        macro = _macro_snapshot()
        snapshot_id = insert_snapshot(
            run_id=run_id,
            captured_at=captured_at,
            market_data={"symbols": prices, "overview": overview},
            macro_data=macro,
        )

        provider = get_provider()
        ai_context = {"overview": overview, "macro": macro}
        for symbol in SYMBOLS:
            row = by_symbol.get(symbol, {"symbol": symbol, "name": SYMBOLS[symbol], "error": "missing"})
            if row.get("error"):
                continue
            score = calculate_templeton_score(row, market)
            insert_score(snapshot_id, row, score)

            judgment = provider.judge(name=row["name"], code=symbol, score=score, context=ai_context)
            insert_ai_judgment(
                snapshot_id=snapshot_id,
                symbol=symbol,
                provider=getattr(provider, "name", "none"),
                model=judgment.get("_model") or getattr(provider, "model", "none"),
                model_version=getattr(provider, "version", "v1"),
                prompt_version=PROMPT_VERSION,
                input_data={"score": score, "context": ai_context},
                output_data=judgment,
            )

            previous = latest_panic_state(symbol)
            panic = evaluate(row, market, previous)
            insert_panic_state(snapshot_id, symbol, panic)

        finish_collection_run(run_id, status="success", snapshot_id=snapshot_id)
        return str(snapshot_id)
    except Exception as exc:
        finish_collection_run(run_id, status="failed", error=str(exc), snapshot_id=None)
        raise
