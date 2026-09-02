"""
Backtest runner — 본 앱과 분리된 실행 경로
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, date
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from config import SYMBOLS, validate_config  # noqa: E402
from kis_client import KISClient  # noqa: E402
from market_data import compute_volatility, compute_momentum  # noqa: E402
from score_engine import calculate_templeton_score, MARKET_BENCHMARK_SYMBOL  # noqa: E402
from regime.market_regime import detect_market_regime  # noqa: E402
from regime.panic_classifier import classify_stock_panic  # noqa: E402
from regime.opportunity_rank import rank_opportunities  # noqa: E402

from .point_in_time import (  # noqa: E402
    load_bars,
    bars_as_of,
    bars_after,
    price_as_of,
    high_low_52w,
    change_rate_1d,
    closes_list,
)
from .snapshot import build_score_input, pack_record, dump_jsonl, ENGINE_VERSION  # noqa: E402
from .forward_return import forward_metrics  # noqa: E402
from .performance import summarize, print_summary  # noqa: E402

OUTPUT_DIR = ROOT / "data" / "backtest"

# 내장 시나리오 (샘플 — 데이터 가용 범위에 따라 결과 밀도 다름)
SCENARIOS: dict[str, dict[str, str]] = {
    "crash_sample": {
        "label": "최근 급락 샘플 구간",
        "start": "2024-07-01",
        "end": "2024-08-15",
        "step": "3",
    },
    "bear_sample": {
        "label": "약세 샘플",
        "start": "2024-01-02",
        "end": "2024-03-29",
        "step": "5",
    },
    "normal_sample": {
        "label": "일반 샘플",
        "start": "2024-09-02",
        "end": "2024-11-29",
        "step": "5",
    },
}

DISPLAY_ORDER = [
    "005930",
    "005380",
    "105560",
    "069500",
    "472150",
    "360750",
]


def _watchlist() -> list[tuple[str, str]]:
    items = [(SYMBOLS[c], c) for c in DISPLAY_ORDER if c in SYMBOLS]
    seen = set(DISPLAY_ORDER)
    for code, name in SYMBOLS.items():
        if code not in seen:
            items.append((name, code))
    return items


def _trading_dates_from_bars(bars: list[dict], start: str, end: str) -> list[str]:
    dates = sorted({b["date"] for b in bars if start <= b["date"] <= end})
    return dates


def _step_dates(dates: list[str], step: int) -> list[str]:
    if step <= 1:
        return dates
    return dates[::step]


def run_as_of(
    as_of: str,
    *,
    client: Optional[KISClient] = None,
    symbols: Optional[list[str]] = None,
    save: bool = True,
) -> list[dict[str, Any]]:
    """
    단일 판단일 재현.
    반환: 종목별 decision + forward 레코드
    """
    validate_config()
    client = client or KISClient()
    watch = _watchlist()
    if symbols:
        watch = [(n, c) for n, c in watch if c in symbols]

    # 데이터 윈도우: as_of 기준 과거 400일 ~ 이후 400일
    as_of_d = datetime.strptime(as_of[:10], "%Y-%m-%d").date()
    hist_start = (as_of_d - timedelta(days=400)).isoformat()
    hist_end = (as_of_d + timedelta(days=400)).isoformat()

    # 벤치 바
    bench_bars = load_bars(client, MARKET_BENCHMARK_SYMBOL, hist_start, hist_end)
    bench_upto = bars_as_of(bench_bars, as_of)
    bench_after = bars_after(bench_bars, as_of)
    bench_price = price_as_of(bench_upto)
    bench_chg = change_rate_1d(bench_upto)
    bench_closes = closes_list(bench_upto, 10)

    rows_for_rank: list[dict] = []
    interim: list[dict] = []

    for name, code in watch:
        try:
            bars = load_bars(client, code, hist_start, hist_end)
            upto = bars_as_of(bars, as_of)
            if len(upto) < 5:
                print(f"[backtest] skip {code}: insufficient bars as_of {as_of}")
                continue
            price = price_as_of(upto)
            chg = change_rate_1d(upto)
            hi, lo = high_low_52w(upto)
            closes = closes_list(upto, 60)
            vol = compute_volatility(closes)
            mom = compute_momentum(closes)
            score_input = build_score_input(
                symbol=code,
                name=name,
                as_of=as_of,
                price=price or 0.0,
                change_rate=chg,
                high_52w=hi,
                low_52w=lo,
                closes=closes,
                volatility_annual=vol,
                momentum_20d=mom,
            )
            market = {
                "current_price": bench_price,
                "change_rate": bench_chg,
            }
            score_data = calculate_templeton_score(score_input, market=market)
            interim.append({
                "name": name,
                "code": code,
                "score_input": score_input,
                "score_data": score_data,
                "price_data": {
                    "current_price": price,
                    "change_rate": chg,
                },
                "bars": bars,
                "upto": upto,
            })
        except Exception as e:
            print(f"[backtest] FAIL {code} @{as_of}: {e}")

    day_changes = [r["price_data"].get("change_rate") for r in interim]
    regime = detect_market_regime(
        bench_closes,
        day_changes,
        benchmark_day_change=bench_chg,
    )

    for r in interim:
        r["panic_class"] = classify_stock_panic(
            market_regime=regime.regime,
            change_rate=r["price_data"].get("change_rate"),
            market_change=bench_chg,
            events=[],  # v0.1: 공시 PIT 미연동
        )
        r["ok"] = True

    ranked = rank_opportunities(interim)
    rank_map = {x["code"]: x for x in ranked}

    records: list[dict] = []
    for r in interim:
        rr = rank_map.get(r["code"]) or {}
        rec = pack_record(
            symbol=r["code"],
            name=r["name"],
            as_of=as_of,
            score_input=r["score_input"],
            score_data=r["score_data"],
            market_regime=regime.regime,
            panic_class=r["panic_class"],
            opportunity_rank=rr.get("opportunity_rank"),
            opportunity_score=rr.get("opportunity_score"),
            bench_change=bench_chg,
        )
        fut = bars_after(r["bars"], as_of)
        rec["forward"] = forward_metrics(
            base_price=float(r["score_input"]["current_price"] or 0),
            future_bars_asc=fut,
            bench_base=bench_price,
            bench_future_asc=bench_after,
        )
        records.append(rec)
        print(
            f"  {as_of} {r['name']} ({r['code']}) "
            f"score={rec.get('total')} op={rec.get('opinion')} "
            f"regime={regime.regime} "
            f"+20d={((rec.get('forward') or {}).get('horizons') or {}).get('20', {}).get('ret')}"
        )

    if save and records:
        out = OUTPUT_DIR / f"results_{as_of}.jsonl"
        dump_jsonl(out, records)
        print(f"[backtest] saved {len(records)} → {out}")

    return records


def run_range(
    start: str,
    end: str,
    *,
    step: int = 5,
    client: Optional[KISClient] = None,
    save: bool = True,
) -> list[dict[str, Any]]:
    validate_config()
    client = client or KISClient()
    # 벤치 바로 거래일 목록
    s = datetime.strptime(start[:10], "%Y-%m-%d").date()
    e = datetime.strptime(end[:10], "%Y-%m-%d").date()
    pull_start = (s - timedelta(days=30)).isoformat()
    pull_end = (e + timedelta(days=5)).isoformat()
    bench = load_bars(client, MARKET_BENCHMARK_SYMBOL, pull_start, pull_end)
    dates = _step_dates(_trading_dates_from_bars(bench, start[:10], end[:10]), step)
    print(f"[backtest] range {start}→{end} step={step} days={len(dates)}")

    all_recs: list[dict] = []
    for d in dates:
        print(f"[backtest] as_of {d}")
        recs = run_as_of(d, client=client, save=False)
        all_recs.extend(recs)

    if save and all_recs:
        out = OUTPUT_DIR / f"results_{start}_{end}_step{step}.jsonl"
        dump_jsonl(out, all_recs)
        print(f"[backtest] saved {len(all_recs)} → {out}")

    summary = summarize(all_recs)
    print_summary(summary)
    if save:
        import json
        sum_path = OUTPUT_DIR / f"summary_{start}_{end}_step{step}.json"
        sum_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return all_recs


def run_scenario(name: str, **kwargs) -> list[dict[str, Any]]:
    sc = SCENARIOS.get(name)
    if not sc:
        raise ValueError(f"Unknown scenario: {name}. Available: {list(SCENARIOS)}")
    print(f"[backtest] scenario={name} ({sc['label']})")
    return run_range(
        sc["start"],
        sc["end"],
        step=int(sc.get("step") or 5),
        **kwargs,
    )
