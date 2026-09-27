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
from kis_client import KISClient
from market_data import compute_volatility, compute_momentum
from score_engine import calculate_templeton_score, MARKET_BENCHMARK_SYMBOL
from events.trigger import should_refetch_events, trigger_reason
from events.dart_client import DartClient
from regime.market_regime import detect_market_regime
from regime.panic_classifier import classify_stock_panic
from regime.opportunity_rank import rank_opportunities
from ai_interpreter import get_coach, build_change_conditions

KST = ZoneInfo("Asia/Seoul")
DISPLAY_ORDER = ["005930", "005380", "105560", "069500", "472150", "360750"]
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
                "select id,status from collection_runs where slot_key=%s",
                (key,),
            )
            existing = cur.fetchone()
            if existing and existing[1] == "completed":
                print(f"[snapshot] skip completed slot={key} run_id={existing[0]}")
                return 0
            if existing:
                run_id = existing[0]
                cur.execute(
                    "update collection_runs set started_at=now(), status='running', error=null where id=%s",
                    (run_id,),
                )
            else:
                cur.execute(
                    """insert into collection_runs(slot_key,source,environment)
                       values(%s,'oracle_cron',%s) returning id""",
                    (key, KIS_ENV),
                )
                run_id = cur.fetchone()[0]
        conn.commit()

        client = KISClient()
        benchmark = client.get_current_price(MARKET_BENCHMARK_SYMBOL)
        benchmark_closes = client.get_daily_closes(MARKET_BENCHMARK_SYMBOL, 10)

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
                if need_events and DART_API_KEY:
                    try:
                        dart = DartClient(DART_API_KEY)
                        events = [e.to_dict() for e in dart.get_recent_disclosures(code, name=name, days=30, max_count=5)]
                    except Exception as e:
                        print(f"[snapshot] DART {code}: {e}")

                results.append({
                    "name": name, "code": code, "price": price, "closes": closes,
                    "financial": financial, "score": score, "events": events,
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
        )
        for r in results:
            r["panic"] = classify_stock_panic(
                market_regime=regime.regime,
                change_rate=r["price"].get("change_rate"),
                market_change=benchmark_chg,
                events=r["events"],
            )
        ranks = {x["code"]: x for x in rank_opportunities(results)}

        coach = get_coach()
        snapshot_rows = []
        for r in results:
            score = r["score"]
            comp = score.get("components") or {}
            panic = r["panic"] or {}
            rank = ranks.get(r["code"]) or {}
            payload = {
                "price_data": r["price"], "financial": r["financial"],
                "closes": r["closes"], "score_data": score,
                "events": r["events"], "event_trigger": r["event_trigger"],
                "volatility_annual": r["volatility_annual"],
                "momentum_20d": r["momentum_20d"],
                "drop_from_52w_high": r["drop_from_52w_high"],
                "benchmark": benchmark, "market_regime": regime.regime,
                "panic": panic,
            }
            with conn.cursor() as cur:
                cur.execute(
                    """insert into market_snapshots(
                       run_id,captured_at,captured_at_kst,code,name,price,change_rate,
                       score,opinion,value,price_score,pessimism,quality,growth,risk,
                       market_regime,panic_type,opportunity_rank,opportunity_score,payload)
                       values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                       on conflict(run_id,code) do update set
                       captured_at=excluded.captured_at,captured_at_kst=excluded.captured_at_kst,
                       price=excluded.price,change_rate=excluded.change_rate,score=excluded.score,
                       opinion=excluded.opinion,value=excluded.value,price_score=excluded.price_score,
                       pessimism=excluded.pessimism,quality=excluded.quality,growth=excluded.growth,
                       risk=excluded.risk,market_regime=excluded.market_regime,panic_type=excluded.panic_type,
                       opportunity_rank=excluded.opportunity_rank,opportunity_score=excluded.opportunity_score,
                       payload=excluded.payload
                       returning id""",
                    (run_id,captured_at,now_kst.isoformat(),r["code"],r["name"],
                     r["price"].get("current_price"),r["price"].get("change_rate"),
                     score.get("total"),score.get("opinion"),comp.get("value"),comp.get("price"),
                     comp.get("pessimism"),comp.get("quality"),comp.get("growth"),comp.get("risk"),
                     regime.regime,panic.get("type"),rank.get("opportunity_rank"),
                     rank.get("opportunity_score"),Json(payload)),
                )
                snapshot_id = cur.fetchone()[0]

            try:
                ai = coach.generate_comment(
                    r["name"], r["code"], score, score.get("opinion") or "",
                    market_ctx=f"시장모드: {regime.regime}, 벤치마크 변동률: {benchmark_chg}%",
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
            with conn.cursor() as cur:
                cur.execute(
                    """insert into ai_judgments(
                       snapshot_id,provider,model,status,comment,positives,negatives,
                       counter_argument,change_conditions,raw_response,error)
                       values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                       on conflict(snapshot_id,provider,model) do update set
                       status=excluded.status,generated_at=now(),comment=excluded.comment,
                       positives=excluded.positives,negatives=excluded.negatives,
                       counter_argument=excluded.counter_argument,
                       change_conditions=excluded.change_conditions,
                       raw_response=excluded.raw_response,error=excluded.error""",
                    (snapshot_id,PROVIDER,MODEL,status,ai.get("comment"),
                     Json(ai.get("positives") or []),Json(ai.get("negatives") or []),
                     ai.get("counter_argument"),Json(conditions),
                     ai.get("raw_response"),err),
                )
                cur.execute(
                    """insert into panic_events(snapshot_id,panic_type,market_regime,details)
                       values(%s,%s,%s,%s)
                       on conflict(snapshot_id) do update set
                       panic_type=excluded.panic_type,market_regime=excluded.market_regime,
                       details=excluded.details""",
                    (snapshot_id,panic.get("type") or "none",regime.regime,Json(panic)),
                )
            conn.commit()
            print(f"[snapshot] stored {r['code']} snapshot={snapshot_id} ai={status}")

        with conn.cursor() as cur:
            cur.execute(
                "update collection_runs set finished_at=now(),status='completed' where id=%s",
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
                    "update collection_runs set finished_at=now(),status='failed',error=%s where id=%s",
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
