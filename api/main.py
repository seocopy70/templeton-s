"""New read-only FastAPI layer for Templeton S.

Current endpoints read live market data only; they never create snapshots.
Historical judgments are read from Neon and remain separate from current data.
"""
from __future__ import annotations
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path: sys.path.insert(0, str(SRC))

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from config import SYMBOLS
from kis_client import KISClient
from market_data import fetch_all_prices
from market_overview import fetch_market_overview
from score_engine import calculate_templeton_score, MARKET_BENCHMARK_SYMBOL
from db.neon_client import latest_snapshot, latest_judgments, latest_panic_states, init_tables

app = FastAPI(title="Templeton S API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=False, allow_methods=["GET"], allow_headers=["*"])
_client = KISClient()


def _current() -> dict[str, Any]:
    prices = fetch_all_prices(_client)
    by_symbol = {str(x.get("symbol")): x for x in prices}
    for symbol, row in by_symbol.items():
        if row.get("error"): continue
        try: row.update(_client.get_financial_ratios(symbol))
        except Exception as exc: row["financial_error"] = str(exc)
    market = by_symbol.get(MARKET_BENCHMARK_SYMBOL)
    items=[]
    for symbol in SYMBOLS:
        row=by_symbol.get(symbol,{"symbol":symbol,"name":SYMBOLS[symbol]})
        if row.get("error"):
            items.append({**row,"score":None}); continue
        items.append({**row,"score":calculate_templeton_score(row,market)})
    return {"as_of": max((x.get("timestamp") for x in items if x.get("timestamp")), default=None), "items":items}

@app.get("/")
def root(): return {"ok":True,"service":"Templeton S API","version":"1.0.0"}

@app.get("/health")
def health(): return {"status":"ok"}

@app.get("/current")
def current():
    try: return _current()
    except Exception as exc: raise HTTPException(502, f"current market data unavailable: {exc}") from exc

@app.get("/scores")
def scores(): return current()

@app.get("/market-overview")
def market_overview():
    try: return {"ok":True,"items":fetch_market_overview(_client)}
    except Exception as exc: raise HTTPException(502, f"market overview unavailable: {exc}") from exc

@app.get("/snapshots/latest")
def snapshot_latest():
    try: return {"ok":True,"snapshot":latest_snapshot()}
    except Exception as exc: raise HTTPException(503, f"snapshot store unavailable: {exc}") from exc

@app.get("/judgments/latest")
def judgments_latest():
    try: return {"ok":True,"items":latest_judgments()}
    except Exception as exc: raise HTTPException(503, f"judgment store unavailable: {exc}") from exc

@app.get("/panic/latest")
def panic_latest():
    try: return {"ok":True,"items":latest_panic_states()}
    except Exception as exc: raise HTTPException(503, f"panic store unavailable: {exc}") from exc

@app.get("/prices/{symbol}/history")
def price_history(symbol: str, count: int = Query(60, ge=1, le=120)):
    symbol=symbol.strip()
    if symbol not in SYMBOLS: raise HTTPException(404, f"unknown symbol: {symbol}")
    try:
        bars=_client.get_daily_bars(symbol,count)
        return {"ok":True,"symbol":symbol,"name":SYMBOLS[symbol],"bars":bars,"closes":list(reversed([b["close"] for b in bars]))}
    except Exception as exc: raise HTTPException(502, f"history unavailable: {exc}") from exc

@app.on_event("startup")
def startup():
    # Creates only missing tables; does not write a market snapshot.
    try: init_tables()
    except Exception as exc: print(f"[startup] Neon schema check skipped: {exc}")
