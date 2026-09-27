"""Templeton S FastAPI adapter.

The API intentionally delegates market data and score calculation to the
existing Python modules. React is a presentation layer; no score logic is
duplicated here.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Existing Templeton modules live under src/ and use direct module imports
# (config, kis_client, market_data, ...). Keep that module layout unchanged.
ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

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
from events.dart_client import DartClient
import os
import psycopg2
from dotenv import load_dotenv

load_dotenv(ROOT / "config" / ".env")

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
_disclosure_cache: dict[str, Any] = {"expires": 0.0, "data": None}
_CACHE_SECONDS = 60
_DISCLOSURE_CACHE_SECONDS = 600


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


@app.get("/latest-snapshot")
def latest_snapshot() -> dict[str, Any]:
    """Return the most recent persisted Snapshot in the same row shape as /scores.

    This is a read-only fast path for initial UI rendering. It does not
    trigger KIS calls and does not create or modify historical records.
    """
    url = os.getenv("NEON_DATABASE_URL")
    if not url:
        raise HTTPException(status_code=503, detail="snapshot database unavailable")

    try:
        with psycopg2.connect(url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    select snapshot_id, captured_at, market_data
                    from market_snapshots
                    order by captured_at desc
                    limit 1
                    """
                )
                row = cur.fetchone()

        if not row:
            return {"ok": True, "snapshot_id": None, "captured_at": None, "items": []}

        snapshot_id, captured_at, market_data = row
        stocks = (market_data or {}).get("stocks") or []
        items = []
        for stock in stocks:
            price = stock.get("price") or {}
            financial = stock.get("financial") or {}
            items.append({
                "symbol": stock.get("code"),
                "name": stock.get("name") or SYMBOLS.get(stock.get("code"), stock.get("code")),
                **price,
                **financial,
                "closes": stock.get("closes") or [],
                "volatility_annual": stock.get("volatility_annual"),
                "momentum_20d": stock.get("momentum_20d"),
                "drop_from_52w_high": stock.get("drop_from_52w"),
                "score": stock.get("score"),
            })

        return {
            "ok": True,
            "snapshot_id": str(snapshot_id) if snapshot_id else None,
            "captured_at": captured_at.isoformat() if captured_at else None,
            "items": items,
        }
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"latest snapshot unavailable: {exc}") from exc


@app.get("/scores")
def scores(force: bool = Query(False)) -> list[dict[str, Any]]:
    try:
        return _get_scores(force=force)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"market data unavailable: {exc}") from exc


@app.get("/prices")
def prices(force: bool = Query(False)) -> list[dict[str, Any]]:
    """Compatibility endpoint for the current React prototype."""
    try:
        return _get_scores(force=force)
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
        return data
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"market overview unavailable: {exc}") from exc



@app.get("/disclosures")
def disclosures(
    limit: int = Query(30, ge=1, le=100),
) -> dict[str, Any]:
    """Return recent DART disclosures for the configured watchlist."""
    now = time.time()
    cached = _disclosure_cache.get("data")
    if cached is not None and now < _disclosure_cache["expires"]:
        return {"ok": True, "items": cached[:limit]}

    api_key = os.getenv("DART_API_KEY", "")
    if not api_key:
        _disclosure_cache["data"] = []
        _disclosure_cache["expires"] = now + _DISCLOSURE_CACHE_SECONDS
        return {"ok": True, "items": [], "enabled": False}

    client = DartClient(api_key)
    items: list[dict[str, Any]] = []
    for symbol, name in SYMBOLS.items():
        try:
            events = client.get_recent_disclosures(symbol, name=name, days=45, max_count=10)
            items.extend(event.to_dict() for event in events)
        except Exception:
            continue

    items.sort(key=lambda x: str(x.get("ts") or ""), reverse=True)
    items = items[:100]
    _disclosure_cache["data"] = items
    _disclosure_cache["expires"] = now + _DISCLOSURE_CACHE_SECONDS
    return {"ok": True, "items": items[:limit], "enabled": True}


@app.get("/ai-judgments")
def ai_judgments(
    limit: int = Query(30, ge=1, le=200),
    symbol: Optional[str] = Query(None),
) -> dict[str, Any]:
    """Return persisted AI judgments from Snapshot history."""
    url = os.getenv("NEON_DATABASE_URL")
    if not url:
        raise HTTPException(status_code=503, detail="snapshot database unavailable")
    try:
        with psycopg2.connect(url) as conn:
            with conn.cursor() as cur:
                if symbol:
                    cur.execute(
                        """
                        select j.judgment_id, j.snapshot_id, j.symbol,
                               j.provider, j.model, j.input_data, j.output_data,
                               j.created_at, s.captured_at
                        from ai_judgments j
                        left join market_snapshots s on s.snapshot_id=j.snapshot_id
                        where j.symbol=%s
                        order by j.created_at desc
                        limit %s
                        """,
                        (symbol, limit),
                    )
                else:
                    cur.execute(
                        """
                        select j.judgment_id, j.snapshot_id, j.symbol,
                               j.provider, j.model, j.input_data, j.output_data,
                               j.created_at, s.captured_at
                        from ai_judgments j
                        left join market_snapshots s on s.snapshot_id=j.snapshot_id
                        order by j.created_at desc
                        limit %s
                        """,
                        (limit,),
                    )
                rows = cur.fetchall()

        items = []
        for judgment_id, snapshot_id, symbol_code, provider, model, input_data, output_data, created_at, captured_at in rows:
            inp = input_data or {}
            out = output_data or {}
            score = inp.get("score") or {}
            opinion = score.get("opinion") or out.get("opinion")
            total = score.get("total")
            items.append({
                "id": judgment_id,
                "snapshot_id": str(snapshot_id) if snapshot_id else None,
                "symbol": symbol_code,
                "name": SYMBOLS.get(symbol_code, symbol_code),
                "provider": provider,
                "model": model,
                "score": total,
                "opinion": opinion,
                "comment": out.get("comment"),
                "source": out.get("source"),
                "created_at": created_at.isoformat() if created_at else None,
                "captured_at": captured_at.isoformat() if captured_at else None,
            })
        return {"ok": True, "items": items}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"ai judgments unavailable: {exc}") from exc


@app.get("/panic-watch")
def panic_watch(
    limit: int = Query(30, ge=1, le=100),
) -> dict[str, Any]:
    """Return the latest persisted panic/snapshot history.

    This reads the production snapshot tables only; opening the app does not
    create or mutate historical records.
    """
    url = os.getenv("NEON_DATABASE_URL")
    if not url:
        raise HTTPException(status_code=503, detail="snapshot database unavailable")

    try:
        with psycopg2.connect(url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    select
                        p.detected_at,
                        p.snapshot_id,
                        p.panic_type,
                        p.market_regime,
                        p.details,
                        s.captured_at,
                        s.market_data
                    from panic_events p
                    join market_snapshots s on s.snapshot_id = p.snapshot_id
                    order by p.detected_at desc
                    limit %s
                    """,
                    (limit,),
                )
                rows = cur.fetchall()

        items = []
        for detected_at, snapshot_id, panic_type, market_regime, details, captured_at, market_data in rows:
            stocks = (market_data or {}).get("stocks") or []
            items.append({
                "snapshot_id": str(snapshot_id),
                "captured_at": captured_at.isoformat() if captured_at else None,
                "detected_at": detected_at.isoformat() if detected_at else None,
                "panic_type": panic_type,
                "market_regime": market_regime,
                "details": details or {},
                "stocks": [
                    {
                        "symbol": stock.get("code"),
                        "name": stock.get("name"),
                        "price": (stock.get("price") or {}).get("current_price"),
                        "change_rate": (stock.get("price") or {}).get("change_rate"),
                        "score": (stock.get("score") or {}).get("total"),
                        "opinion": (stock.get("score") or {}).get("opinion"),
                        "panic": stock.get("panic") or {},
                    }
                    for stock in stocks
                ],
            })

        return {"ok": True, "items": items}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"panic watch unavailable: {exc}") from exc


@app.get("/snapshot-outcomes")
def snapshot_outcomes(
    limit: int = Query(100, ge=1, le=500),
    symbol: Optional[str] = Query(None),
) -> dict[str, Any]:
    """Return persisted post-hoc outcomes without changing original judgments."""
    url = os.getenv("NEON_DATABASE_URL")
    if not url:
        raise HTTPException(status_code=503, detail="snapshot database unavailable")
    try:
        with psycopg2.connect(url) as conn:
            with conn.cursor() as cur:
                if symbol:
                    cur.execute(
                        """
                        select snapshot_id, symbol, horizon_days,
                               reference_price, future_price,
                               return_pct, benchmark_return_pct,
                               evaluated_at, result
                        from snapshot_outcomes
                        where symbol=%s
                        order by evaluated_at desc
                        limit %s
                        """,
                        (symbol, limit),
                    )
                else:
                    cur.execute(
                        """
                        select snapshot_id, symbol, horizon_days,
                               reference_price, future_price,
                               return_pct, benchmark_return_pct,
                               evaluated_at, result
                        from snapshot_outcomes
                        order by evaluated_at desc
                        limit %s
                        """,
                        (limit,),
                    )
                rows = cur.fetchall()

        return {
            "ok": True,
            "items": [
                {
                    "snapshot_id": str(row[0]),
                    "symbol": row[1],
                    "horizon_days": row[2],
                    "reference_price": float(row[3]) if row[3] is not None else None,
                    "future_price": float(row[4]) if row[4] is not None else None,
                    "return_pct": float(row[5]) if row[5] is not None else None,
                    "benchmark_return_pct": float(row[6]) if row[6] is not None else None,
                    "evaluated_at": row[7].isoformat() if row[7] else None,
                    "result": row[8] or {},
                }
                for row in rows
            ],
        }
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"snapshot outcomes unavailable: {exc}") from exc


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
