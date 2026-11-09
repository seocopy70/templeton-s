#!/usr/bin/env python3
"""
Templeton S production snapshot collector.

KIS/Score/Panic -> Neon snapshot -> Groq/Llama judgment.
Existing daily_log.py remains untouched as the legacy JSONL collector.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from dotenv import load_dotenv
load_dotenv(ROOT / "config" / ".env")

import psycopg2
from psycopg2.extras import Json

from config import SYMBOLS, DART_API_KEY, KIS_ENV, validate_config
from fred_client import fetch_fred_context
from kis_client import KISClient
from market_data import compute_volatility, compute_momentum
from score_engine import calculate_templeton_score, MARKET_BENCHMARK_SYMBOL
from events.trigger import should_refetch_events, trigger_reason
from events.dart_client import DartClient
from regime.market_regime import detect_market_regime, calc_drawdown, DD_WATCH_PCT, DD_WINDOW
from regime.panic_classifier import classify_stock_panic
from regime.opportunity_rank import rank_opportunities, ETF_CODES
from regime.entry_stage import decide_entry
from ai_interpreter import get_coach, build_change_conditions

KST = ZoneInfo("Asia/Seoul")
DISPLAY_ORDER = [
    "005930", "000660", "005380", "105560",
    "373220", "012450", "034020", "207940", "005490",
    "069500", "472150", "360750",
]
MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
PROVIDER = "groq"


def db():
    url = os.getenv("NEON_DATABASE_URL")
    if not url:
        raise RuntimeError("NEON_DATABASE_URL not set")
    return psycopg2.connect(url)


def ensure_schema(conn):
    sql = (ROOT / "db" / "snapshot_schema.sql").read_text(encoding="utf-8")
    with conn.cursor() as cur:
        cur.execute(sql)
    conn.commit()


def slot_key(now_kst: datetime) -> str:
    return now_kst.strftime("%Y%m%d-%H%M")


def build_watchlist():
    return [(SYMBOLS[c], c) for c in DISPLAY_ORDER if c in SYMBOLS]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--slot", help="fixed slot key, e.g. 20260927-0930")
    args = parser.parse_args()

    now_kst = datetime.now(KST)
    captured_at = datetime.now(timezone.utc)
    key = args.slot or slot_key(now_kst)
    print(f"[snapshot] start KST={now_kst.isoformat()} slot={key} env={KIS_ENV} model={MODEL}")

    validate_config()
    conn = db()
    try:
        ensure_schema(conn)

        with conn.cursor() as cur:
            cur.execute(
                "select run_id,status,snapshot_id from collection_runs where slot=%s",
                (key,),
            )
            existing = cur.fetchone()
            if existing and existing[1] == "completed":
                print(f"[snapshot] skip completed slot={key} run_id={existing[0]}")
                return 0
            if existing:
                run_id = existing[0]
                snapshot_id = existing[2]
                cur.execute(
                    """update collection_runs
                       set captured_at=%s, completed_at=null, status='running', error=null
                       where run_id=%s""",
                    (captured_at, run_id),
                )
            else:
                run_id = str(uuid.uuid4())
                snapshot_id = str(uuid.uuid4())
                cur.execute(
                    """insert into collection_runs(
                         run_id,slot,captured_at,status,snapshot_id
                       ) values(%s,%s,%s,'running',%s)""",
                    (run_id, key, captured_at, snapshot_id),
                )
        conn.commit()

        client = KISClient()
        benchmark = client.get_current_price(MARKET_BENCHMARK_SYMBOL)
        benchmark_closes = client.get_daily_closes(MARKET_BENCHMARK_SYMBOL, DD_WINDOW)
        bench_dd = calc_drawdown(benchmark_closes, benchmark.get("current_price"))
        # 시장이 고점 대비 충분히 눌린 구간이면 소폭 변동이어도 공시를 조회한다
        # (그렇지 않으면 '악재 공시 미확인'이 실제로는 '미조회'인 채로 남는다)
        force_events = bench_dd is not None and bench_dd <= DD_WATCH_PCT
        print(f"[snapshot] benchmark drawdown={bench_dd} force_events={force_events}")

        results = []
        for name, code in build_watchlist():
            try:
                price = client.get_current_price(code)
                closes = client.get_daily_closes(code, 60)
                try:
                    financial = client.get_financial_ratios(code)
                except Exception:
                    financial = {}

                vol = compute_volatility(closes)
                mom = compute_momentum(closes)
                drop_52 = None
                if price.get("high_52w") and price.get("current_price") and price["high_52w"] > 0:
                    drop_52 = round((price["high_52w"] - price["current_price"]) / price["high_52w"] * 100, 2)

                score_input = {
                    **price, "closes": closes, "volatility_annual": vol,
                    "momentum_20d": mom, "candle_days": len(closes),
                    "drop_from_52w_high": drop_52, **financial,
                }
                score = calculate_templeton_score(score_input, market=benchmark)

                events = []
                change = price.get("change_rate")
                mkt_chg = benchmark.get("change_rate")
                need_events = should_refetch_events(change, mkt_chg)
                trigger = trigger_reason(change, mkt_chg)
                if force_events and code not in ETF_CODES and not need_events:
                    need_events = True
                    trigger = f"market_drawdown:{bench_dd:+.1f}%"
                events_checked = False
                if need_events and DART_API_KEY:
                    try:
                        dart = DartClient(DART_API_KEY)
                        events = [e.to_dict() for e in dart.get_recent_disclosures(code, name=name, days=30, max_count=5)]
                        events_checked = True
                    except Exception as e:
                        print(f"[snapshot] DART {code}: {e}")

                results.append({
                    "name": name, "code": code, "price": price, "closes": closes,
                    "financial": financial, "score": score, "events": events,
                    "events_checked": events_checked,
                    "event_trigger": trigger if need_events else "none",
                    "volatility_annual": vol, "momentum_20d": mom,
                    "drop_from_52w_high": drop_52, "ok": True,
                })
                print(f"[snapshot] ok {name} ({code}) price={price.get('current_price')} score={score.get('total')}")
            except Exception as e:
                print(f"[snapshot] FAIL {name} ({code}): {e}", file=sys.stderr)

        if not results:
            raise RuntimeError("no stock results")

        benchmark_chg = benchmark.get("change_rate", 0.0)
        regime = detect_market_regime(
            benchmark_closes,
            [r["price"].get("change_rate") for r in results],
            benchmark_day_change=benchmark_chg,
            benchmark_drawdown=bench_dd,
        )
        for r in results:
            r["panic"] = classify_stock_panic(
                market_regime=regime.regime,
                change_rate=r["price"].get("change_rate"),
                market_change=benchmark_chg,
                events=r["events"],
                events_checked=r["events_checked"],
            )
        ranks = {x["code"]: x for x in rank_opportunities(results)}

        # 분할매수 단계: 총점(75↑ 필요)과 별도로 '시장 낙폭 × 종목 낙폭 + 안전 게이트'로 판정.
        # score["opinion"]을 덮어쓰면 API/사후검증(snapshot_outcomes)이 그대로 새 의견을 읽는다.
        for r in results:
            sc = r["score"]
            ent = decide_entry(
                code=r["code"],
                base_opinion=sc.get("opinion") or "",
                total_score=float(sc.get("total") or 0),
                components=sc.get("components") or {},
                market_dd=regime.drawdown_pct,
                drop_from_52w_high=r.get("drop_from_52w_high"),
                opportunity_score=(ranks.get(r["code"]) or {}).get("opportunity_score"),
                panic_type=(r.get("panic") or {}).get("type") or "none",
                events=r["events"],
                events_checked=r["events_checked"],
            )
            sc["opinion_base"] = ent["opinion_base"]
            sc["opinion"] = ent["opinion"]
            sc["entry"] = ent

        coach = get_coach()
        market_data = {
            "stocks": results,
            "benchmark": benchmark,
            "market_regime": regime.regime,
            "benchmark_change_rate": benchmark_chg,
            "market_drawdown": regime.drawdown_pct,
            "dd_stage": regime.dd_stage,
        }
        macro_data = fetch_fred_context()
        macro_data["captured_at_kst"] = now_kst.isoformat()
        macro_data["source"] = "fred"

        with conn.cursor() as cur:
            cur.execute(
                """insert into market_snapshots(
                     snapshot_id,run_id,captured_at,market_data,macro_data
                   ) values(%s,%s,%s,%s,%s)
                   on conflict(snapshot_id) do update set
                     captured_at=excluded.captured_at,
                     market_data=excluded.market_data,
                     macro_data=excluded.macro_data""",
                (snapshot_id, run_id, captured_at,
                 Json(market_data), Json(macro_data)),
            )
        conn.commit()
        print(
            f"[snapshot] stored market snapshot={snapshot_id} "
            f"fred_status={macro_data.get('status')}"
        )

        macro_series = macro_data.get("series") or {}
        macro_ctx = ", ".join(
            f"{sid}={item.get('value')}"
            for sid, item in macro_series.items()
            if item.get("value") is not None
        )
        if not macro_ctx:
            macro_ctx = "FRED macro data unavailable"

        coach = get_coach()
        for r in results:
            score = r["score"]
            rank = ranks.get(r["code"]) or {}
            panic = r["panic"] or {}
            try:
                ai = coach.generate_comment(
                    r["name"], r["code"], score, score.get("opinion") or "",
                    market_ctx=(
                        f"시장모드: {regime.regime}, "
                        f"벤치마크 변동률: {benchmark_chg}%, "
                        f"FRED: {macro_ctx}"
                    ),
                    events=r["events"],
                )
                status = "completed"
                err = None
            except Exception as e:
                ai = {}
                status = "error"
                err = str(e)

            conditions = build_change_conditions(
                r["name"], score, r["price"].get("current_price")
            )
            output_data = {
                "status": status,
                "comment": ai.get("comment"),
                "positives": ai.get("positives") or [],
                "negatives": ai.get("negatives") or [],
                "counter_argument": ai.get("counter_argument"),
                "change_conditions": conditions,
                "source": ai.get("source"),   # groq | rule_based (폴백 여부를 기록)
                "error": err,
            }
            input_data = {
                "name": r["name"], "code": r["code"], "score": score,
                "price": r["price"], "market_regime": regime.regime,
                "benchmark_change_rate": benchmark_chg, "events": r["events"],
                "panic": panic,
                "opportunity_rank": rank.get("opportunity_rank"),
                "opportunity_score": rank.get("opportunity_score"),
                "macro_data": macro_data,
            }
            with conn.cursor() as cur:
                cur.execute(
                    """insert into ai_judgments(
                         snapshot_id,symbol,provider,model,model_version,
                         prompt_version,input_data,output_data
                       ) values(%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (snapshot_id, r["code"], PROVIDER, MODEL, MODEL,
                     "templeton-snapshot-v1", Json(input_data), Json(output_data)),
                )
            conn.commit()
            print(f"[snapshot] stored {r['code']} ai={status}")

        panic_types = [((r.get("panic") or {}).get("type") or "none") for r in results]
        active_panics = [p for p in panic_types if p != "none"]
        with conn.cursor() as cur:
            cur.execute(
                """insert into panic_events(
                     snapshot_id,panic_type,market_regime,details
                   ) values(%s,%s,%s,%s)
                   on conflict(snapshot_id) do update set
                     panic_type=excluded.panic_type,
                     market_regime=excluded.market_regime,
                     details=excluded.details""",
                (snapshot_id, active_panics[0] if active_panics else "none",
                 regime.regime,
                 Json({
                     "types": panic_types,
                     "stocks": [
                         {"code": r["code"], "name": r["name"],
                          "panic": r.get("panic") or {}}
                         for r in results
                     ],
                 })),
            )
        conn.commit()

        with conn.cursor() as cur:
            cur.execute(
                """update collection_runs
                   set completed_at=now(),status='completed',error=null
                   where run_id=%s""",
                (run_id,),
            )
        conn.commit()
        print(f"[snapshot] DONE run_id={run_id} stocks={len(results)}")
        return 0

    except Exception as e:
        conn.rollback()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """update collection_runs
                       set completed_at=now(),status='failed',error=%s
                       where run_id=%s""",
                    (str(e)[:2000], run_id),
                )
            conn.commit()
        except Exception:
            pass
        print(f"[snapshot] FAILED: {e}", file=sys.stderr)
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
