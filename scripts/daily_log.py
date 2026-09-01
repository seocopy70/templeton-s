#!/usr/bin/env python3
"""
템플턴S 일일 판단 기록 (헤드리스)

GitHub Actions / 로컬 스케줄용.
UI 없이 시세·Score·시장모드를 계산해 data/decisions.jsonl 에 적재한다.

원칙:
- 프로그램 계산만 (AI 해석 호출 없음 — 일일 스냅샷 비용·안정성)
- 당일(KST) 이미 기록된 종목은 스킵 (재실행 안전)
- 자동매수 없음
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Optional
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from config import (  # noqa: E402
    KIS_APP_KEY,
    KIS_APP_SECRET,
    KIS_ENV,
    SYMBOLS,
    DART_API_KEY,
    validate_config,
)
from kis_client import KISClient  # noqa: E402
from market_data import compute_volatility, compute_momentum  # noqa: E402
from score_engine import calculate_templeton_score, MARKET_BENCHMARK_SYMBOL  # noqa: E402
from decision_log import log_decision, LOG_PATH, recent_decisions  # noqa: E402
from events.trigger import should_refetch_events, trigger_reason  # noqa: E402
from events.dart_client import DartClient  # noqa: E402
from regime.market_regime import detect_market_regime  # noqa: E402
from regime.panic_classifier import classify_stock_panic  # noqa: E402
from regime.opportunity_rank import rank_opportunities  # noqa: E402

KST = ZoneInfo("Asia/Seoul")
DISPLAY_ORDER = [
    "005930",
    "005380",
    "105560",
    "069500",
    "472150",
    "360750",
]


def _today_kst() -> str:
    return datetime.now(KST).strftime("%Y-%m-%d")


def _already_logged_today(symbol: str, today: str) -> bool:
    """오늘(KST) 날짜로 이미 기록이 있으면 True."""
    for row in recent_decisions(limit=200, symbol=symbol):
        ts = row.get("ts") or ""
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            if dt.astimezone(KST).strftime("%Y-%m-%d") == today:
                return True
        except Exception:
            continue
    return False


def _build_watchlist() -> list[tuple[str, str]]:
    items = [(SYMBOLS[c], c) for c in DISPLAY_ORDER if c in SYMBOLS]
    seen = set(DISPLAY_ORDER)
    for code, name in SYMBOLS.items():
        if code not in seen:
            items.append((name, code))
    return items


def run() -> int:
    print(f"[daily_log] start KST={datetime.now(KST).isoformat()} env={KIS_ENV}")
    try:
        validate_config()
    except ValueError as e:
        print(f"[daily_log] config error: {e}", file=sys.stderr)
        return 2

    today = _today_kst()
    client = KISClient()
    watchlist = _build_watchlist()

    # 벤치마크
    try:
        benchmark = client.get_current_price(MARKET_BENCHMARK_SYMBOL)
    except Exception as e:
        print(f"[daily_log] benchmark price failed: {e}")
        benchmark = {"current_price": 0, "change_rate": 0.0}
    try:
        benchmark_closes = client.get_daily_closes(MARKET_BENCHMARK_SYMBOL, 10)
    except Exception as e:
        print(f"[daily_log] benchmark closes failed: {e}")
        benchmark_closes = []

    results: list[dict[str, Any]] = []
    for name, code in watchlist:
        if _already_logged_today(code, today):
            print(f"[daily_log] skip {name} ({code}) — already logged {today}")
            continue
        try:
            price = client.get_current_price(code)
            closes = client.get_daily_closes(code, 60)
            try:
                financial = client.get_financial_ratios(code)
            except Exception:
                financial = {}

            volatility_annual = compute_volatility(closes)
            momentum_20d = compute_momentum(closes)
            drop_52 = None
            if (
                price.get("high_52w")
                and price.get("current_price")
                and price["high_52w"] > 0
            ):
                drop_52 = round(
                    (price["high_52w"] - price["current_price"])
                    / price["high_52w"]
                    * 100,
                    2,
                )

            score_input = {
                **price,
                "closes": closes,
                "volatility_annual": volatility_annual,
                "momentum_20d": momentum_20d,
                "candle_days": len(closes),
                "drop_from_52w_high": drop_52,
                **financial,
            }
            score_data = calculate_templeton_score(score_input, market=benchmark)

            change = price.get("change_rate")
            mkt_chg = benchmark.get("change_rate")
            need_events = should_refetch_events(change, mkt_chg)
            reason = trigger_reason(change, mkt_chg)
            events_for_stock: list = []
            if need_events and DART_API_KEY:
                try:
                    dart = DartClient(DART_API_KEY)
                    events_for_stock = [
                        e.to_dict()
                        for e in dart.get_recent_disclosures(
                            code, name=name, days=30, max_count=5
                        )
                    ]
                except Exception as e:
                    print(f"[daily_log] DART {code}: {e}")

            results.append({
                "name": name,
                "code": code,
                "price_data": price,
                "score_data": score_data,
                "events": events_for_stock,
                "event_trigger": reason if need_events else "none",
                "ok": True,
            })
            print(
                f"[daily_log] ok {name} ({code}) "
                f"price={price.get('current_price')} "
                f"score={score_data.get('total')} "
                f"op={score_data.get('opinion')}"
            )
        except Exception as e:
            print(f"[daily_log] FAIL {name} ({code}): {e}", file=sys.stderr)
            results.append({
                "name": name,
                "code": code,
                "ok": False,
                "error": str(e),
            })

    ok_results = [r for r in results if r.get("ok")]
    if not ok_results:
        print("[daily_log] no new rows to log (all skipped or failed)")
        return 0 if not results else 1

    benchmark_chg = benchmark.get("change_rate", 0.0)
    day_changes = [r["price_data"].get("change_rate") for r in ok_results]
    regime = detect_market_regime(
        benchmark_closes,
        day_changes,
        benchmark_day_change=benchmark_chg,
    )
    for r in ok_results:
        r["panic_class"] = classify_stock_panic(
            market_regime=regime.regime,
            change_rate=r["price_data"].get("change_rate"),
            market_change=benchmark_chg,
            events=r.get("events") or [],
        )
    ranked = rank_opportunities(ok_results)
    rank_map = {x["code"]: x for x in ranked}

    logged = 0
    for r in ok_results:
        rr = rank_map.get(r["code"]) or {}
        wrote = log_decision(
            symbol=r["code"],
            name=r["name"],
            score_data=r["score_data"],
            price=r["price_data"].get("current_price"),
            event_ids=[
                str(ev.get("event_id"))
                for ev in (r.get("events") or [])
                if isinstance(ev, dict) and ev.get("event_id")
            ],
            event_trigger=r.get("event_trigger") or "none",
            force=True,  # 일일 스냅샷: 당일 미기록 종목만 여기까지 옴
            market_regime=regime.regime,
            panic_type=(r.get("panic_class") or {}).get("type"),
            opportunity_rank=rr.get("opportunity_rank"),
            opportunity_score=rr.get("opportunity_score"),
            extra={"source": "daily_log", "date_kst": today},
        )
        if wrote:
            logged += 1

    print(
        f"[daily_log] done regime={regime.regime} "
        f"logged={logged}/{len(ok_results)} path={LOG_PATH}"
    )
    if LOG_PATH.exists():
        lines = LOG_PATH.read_text(encoding="utf-8").strip().splitlines()
        print(f"[daily_log] total lines in jsonl: {len(lines)}")
    return 0 if logged or not ok_results else 1


if __name__ == "__main__":
    raise SystemExit(run())
