"""Templeton S FastAPI adapter.

The API intentionally delegates market data and score calculation to the
existing Python modules. React is a presentation layer; no score logic is
duplicated here.
"""
from __future__ import annotations

import time
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from config import SYMBOLS
from kis_client import KISClient
from market_data import fetch_all_prices
from market_overview import fetch_market_overview
from score_engine import calculate_templeton_score
from decision_log import recent_decisions, decisions_as_table_rows

app = FastAPI(title="Templeton S API", version="0.1.0")

# Same-origin production use does not require CORS, but this keeps local Vite
# development possible without changing the production Caddy setup.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)

_client = KISClient()
_scores_cache: dict[str, Any] = {"expires": 0.0, "data": None}
_market_cache: dict[str, Any] = {"expires": 0.0, "data": None}
_CACHE_SECONDS = 60


def _get_scores(force: bool = False) -> list[dict[str, Any]]:
    now = time.time()
    if not force and _scores_cache["data"] is not None and now < _scores_cache["expires"]:
        return _scores_cache["data"]

    prices = fetch_all_prices(_client)
    by_symbol = {str(row.get("symbol")): row for row in prices}

    # The existing score engine expects financial-ratio fields on each row.
    for symbol, row in by_symbol.items():
        if row.get("error"):
            row["score"] = None
            continue
        try:
            row.update(_client.get_financial_ratios(symbol))
        except Exception as exc:
            # Preserve the existing score engine's neutral fallback behavior.
            row["financial_error"] = str(exc)

    market = by_symbol.get("069500")
    out: list[dict[str, Any]] = []

    for symbol in SYMBOLS:
        row = by_symbol.get(symbol, {"symbol": symbol, "name": SYMBOLS[symbol]})
        if row.get("error"):
            out.append({
                "symbol": symbol,
                "name": SYMBOLS[symbol],
                "error": row["error"],
                "score": None,
            })
            continue

        score = calculate_templeton_score(row, market)
        out.append({
            **row,
            "score": score,
        })

    _scores_cache["data"] = out
    _scores_cache["expires"] = now + _CACHE_SECONDS
    return out


@app.get("/")
def root() -> dict[str, Any]:
    return {"ok": True, "message": "Templeton S - Oracle Cloud", "version": "0.1.0"}


@app.get("/health")
def health() -> dict[str, Any]:
    return {"status": "ok"}


@app.get("/scores")
def scores(force: bool = Query(False)) -> dict[str, Any]:
    try:
        return {"ok": True, "items": _get_scores(force=force)}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"market data unavailable: {exc}") from exc


@app.get("/prices/{symbol}/history")
def price_history(
    symbol: str,
    count: int = Query(60, ge=1, le=120),
) -> dict[str, Any]:
    symbol = symbol.strip()
    if symbol not in SYMBOLS:
        raise HTTPException(status_code=404, detail=f"unknown symbol: {symbol}")

    try:
        bars = _client.get_daily_bars(symbol, count)
        return {
            "ok": True,
            "symbol": symbol,
            "name": SYMBOLS[symbol],
            "bars": bars,
            # Convenience form for chart components that only need closes.
            "closes": list(reversed([b["close"] for b in bars])),
        }
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"history unavailable: {exc}") from exc


@app.get("/market-overview")
def market_overview(force: bool = Query(False)) -> dict[str, Any]:
    now = time.time()
    if not force and _market_cache["data"] is not None and now < _market_cache["expires"]:
        return {"ok": True, "items": _market_cache["data"]}

    try:
        data = fetch_market_overview(_client)
        _market_cache["data"] = data
        _market_cache["expires"] = now + _CACHE_SECONDS
        return {"ok": True, "items": data}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"market overview unavailable: {exc}") from exc


@app.get("/decisions")
def decisions(
    limit: int = Query(50, ge=1, le=200),
    symbol: Optional[str] = Query(None),
) -> dict[str, Any]:
    records = recent_decisions(limit=limit, symbol=symbol)
    return {
        "ok": True,
        "items": records,
        "rows": decisions_as_table_rows(records),
    }
