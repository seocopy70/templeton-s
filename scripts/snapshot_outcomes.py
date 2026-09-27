#!/usr/bin/env python3
"""Evaluate persisted Templeton snapshots against later market prices."""
from __future__ import annotations

import os
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from dotenv import load_dotenv
load_dotenv(ROOT / "config" / ".env")

import psycopg2
from psycopg2.extras import Json
from config import SYMBOLS
from kis_client import KISClient

HORIZONS = (1, 5, 20)
BENCHMARK = "069500"


def db():
    url = os.getenv("NEON_DATABASE_URL")
    if not url:
        raise RuntimeError("NEON_DATABASE_URL not set")
    return psycopg2.connect(url)


def first_bar_on_or_after(bars: list[dict[str, Any]], target: date):
    candidates = []
    for bar in bars:
        try:
            d = date.fromisoformat(str(bar["date"]))
            if d >= target:
                candidates.append((d, bar))
        except Exception:
            pass
    return min(candidates, key=lambda x: x[0])[1] if candidates else None


def classify_return(value: float) -> str:
    if value > 1.0:
        return "positive"
    if value < -1.0:
        return "negative"
    return "flat"


def main() -> int:
    conn = db()
    client = KISClient()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                select snapshot_id, captured_at, market_data
                from market_snapshots
                order by captured_at asc
            """)
            snapshots = cur.fetchall()

        if not snapshots:
            print("[outcome] no snapshots")
            return 0

        symbols = {BENCHMARK}
        for _, _, market_data in snapshots:
            for stock in (market_data or {}).get("stocks", []):
                if stock.get("code") in SYMBOLS:
                    symbols.add(stock["code"])

        histories = {}
        for symbol in sorted(symbols):
            try:
                histories[symbol] = client.get_daily_bars(symbol, 120)
                print(f"[outcome] history {symbol} bars={len(histories[symbol])}")
            except Exception as exc:
                print(f"[outcome] history FAIL {symbol}: {exc}", file=sys.stderr)

        today = date.today()
        created = 0

        for snapshot_id, captured_at, market_data in snapshots:
            captured_date = captured_at.date()
            stocks = (market_data or {}).get("stocks", [])
            stock_map = {str(s.get("code")): s for s in stocks if s.get("code")}

            benchmark_stock = stock_map.get(BENCHMARK)
            benchmark_reference = ((benchmark_stock or {}).get("price") or {}).get("current_price")

            for symbol, stock in stock_map.items():
                reference_price = ((stock.get("price") or {}).get("current_price"))
                if reference_price is None:
                    continue

                for horizon in HORIZONS:
                    target_date = captured_date + timedelta(days=horizon)
                    if target_date > today:
                        continue

                    future = first_bar_on_or_after(histories.get(symbol, []), target_date)
                    if not future or future.get("close") is None:
                        continue

                    benchmark_future = first_bar_on_or_after(
                        histories.get(BENCHMARK, []), target_date
                    )
                    future_price = float(future["close"])
                    return_pct = (future_price / float(reference_price) - 1.0) * 100.0

                    benchmark_return = None
                    if benchmark_reference and benchmark_future and benchmark_future.get("close") is not None:
                        benchmark_return = (
                            float(benchmark_future["close"]) / float(benchmark_reference) - 1.0
                        ) * 100.0

                    with conn.cursor() as cur:
                        cur.execute("""
                            select output_data
                            from ai_judgments
                            where snapshot_id=%s and symbol=%s
                            order by created_at desc limit 1
                        """, (snapshot_id, symbol))
                        ai_row = cur.fetchone()
                        ai_output = (ai_row[0] if ai_row else {}) or {}

                        result = {
                            "symbol": symbol,
                            "name": SYMBOLS.get(symbol, stock.get("name", symbol)),
                            "captured_date": captured_date.isoformat(),
                            "target_date": target_date.isoformat(),
                            "evaluation_date": future.get("date"),
                            "ai_opinion": ai_output.get("opinion"),
                            "return_class": classify_return(return_pct),
                            "relative_to_benchmark": (
                                "outperform"
                                if benchmark_return is not None and return_pct > benchmark_return
                                else "underperform"
                                if benchmark_return is not None
                                else None
                            ),
                        }

                        cur.execute("""
                            insert into snapshot_outcomes(
                                snapshot_id, symbol, horizon_days,
                                reference_price, future_price,
                                return_pct, benchmark_return_pct, result
                            ) values(%s,%s,%s,%s,%s,%s,%s,%s)
                            on conflict(snapshot_id, symbol, horizon_days) do nothing
                        """, (
                            snapshot_id, symbol, horizon, reference_price,
                            future_price, return_pct, benchmark_return, Json(result)
                        ))
                        if cur.rowcount:
                            created += 1
                    conn.commit()
                    print(
                        f"[outcome] {snapshot_id} {symbol} "
                        f"h={horizon}d return={return_pct:.2f}%"
                    )

        print(f"[outcome] DONE created={created}")
        return 0
    except Exception as exc:
        conn.rollback()
        print(f"[outcome] FAILED: {exc}", file=sys.stderr)
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
