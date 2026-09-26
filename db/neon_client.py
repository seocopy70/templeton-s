"""Neon persistence for the new snapshot pipeline.

Legacy tables/functions remain available for compatibility. New collection
code writes immutable run/snapshot/judgment records here.
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime
from typing import Any

import psycopg2
from psycopg2.extras import Json, execute_values
from dotenv import load_dotenv

load_dotenv("config/.env")


def get_conn():
    url = os.getenv("NEON_DATABASE_URL")
    if not url:
        raise RuntimeError("NEON_DATABASE_URL not set")
    return psycopg2.connect(url)


def init_tables():
    ddl = """
    create table if not exists prices_daily (
      date date, code text, close numeric, volume bigint,
      primary key (date, code)
    );
    create table if not exists templeton_scores (
      date date, code text,
      value numeric, pessimism numeric, risk numeric,
      quality numeric, growth numeric, total numeric,
      primary key (date, code)
    );
    create table if not exists macro_daily (
      date date primary key,
      dgs10 numeric, dff numeric, dtwexbgs numeric,
      dexkous numeric, sp500 numeric, nasdaqcom numeric
    );

    create table if not exists collection_runs (
      run_id uuid primary key,
      slot text,
      captured_at timestamptz not null,
      completed_at timestamptz,
      status text not null,
      error text,
      snapshot_id uuid
    );
    create table if not exists market_snapshots (
      snapshot_id uuid primary key,
      run_id uuid not null references collection_runs(run_id),
      captured_at timestamptz not null,
      market_data jsonb not null,
      macro_data jsonb not null,
      created_at timestamptz not null default now()
    );
    create table if not exists snapshot_scores (
      snapshot_id uuid not null references market_snapshots(snapshot_id),
      symbol text not null,
      name text not null,
      total numeric,
      components jsonb not null,
      inputs jsonb not null,
      opinion text,
      primary key (snapshot_id, symbol)
    );
    create table if not exists ai_judgments (
      judgment_id bigserial primary key,
      snapshot_id uuid not null references market_snapshots(snapshot_id),
      symbol text not null,
      provider text not null,
      model text not null,
      model_version text not null,
      prompt_version text not null,
      input_data jsonb not null,
      output_data jsonb not null,
      created_at timestamptz not null default now()
    );
    create table if not exists panic_watch_states (
      snapshot_id uuid not null references market_snapshots(snapshot_id),
      symbol text not null,
      status text not null,
      state_data jsonb not null,
      created_at timestamptz not null default now(),
      primary key (snapshot_id, symbol)
    );
    create index if not exists idx_snapshots_captured_at on market_snapshots(captured_at desc);
    create index if not exists idx_ai_judgments_snapshot on ai_judgments(snapshot_id);
    create index if not exists idx_panic_symbol_created on panic_watch_states(symbol, created_at desc);
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(ddl)
        conn.commit()


def begin_collection_run(slot: str | None, captured_at: datetime) -> str:
    run_id = uuid.uuid4()
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "insert into collection_runs(run_id,slot,captured_at,status) values(%s,%s,%s,%s)",
                (run_id, slot, captured_at, "running"),
            )
        conn.commit()
    return str(run_id)


def finish_collection_run(run_id: str, status: str, snapshot_id: str | None, error: str | None = None) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "update collection_runs set completed_at=now(),status=%s,snapshot_id=%s,error=%s where run_id=%s",
                (status, snapshot_id, error, run_id),
            )
        conn.commit()


def insert_snapshot(*, run_id: str, captured_at: datetime, market_data: dict[str, Any], macro_data: dict[str, Any]) -> str:
    snapshot_id = uuid.uuid4()
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "insert into market_snapshots(snapshot_id,run_id,captured_at,market_data,macro_data) values(%s,%s,%s,%s,%s)",
                (snapshot_id, run_id, captured_at, Json(market_data), Json(macro_data)),
            )
        conn.commit()
    return str(snapshot_id)


def insert_score(snapshot_id: str, row: dict[str, Any], score: dict[str, Any]) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """insert into snapshot_scores(snapshot_id,symbol,name,total,components,inputs,opinion)
                   values(%s,%s,%s,%s,%s,%s,%s)
                   on conflict (snapshot_id,symbol) do nothing""",
                (snapshot_id, row["symbol"], row["name"], score.get("total"),
                 Json(score.get("components", {})), Json({k:v for k,v in score.items() if k != "components"}), score.get("opinion")),
            )
        conn.commit()


def insert_ai_judgment(*, snapshot_id: str, symbol: str, provider: str, model: str, model_version: str,
                       prompt_version: str, input_data: dict[str, Any], output_data: dict[str, Any]) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """insert into ai_judgments(snapshot_id,symbol,provider,model,model_version,prompt_version,input_data,output_data)
                   values(%s,%s,%s,%s,%s,%s,%s,%s)""",
                (snapshot_id, symbol, provider, model, model_version, prompt_version,
                 Json(input_data), Json(output_data)),
            )
        conn.commit()


def latest_panic_state(symbol: str) -> dict[str, Any] | None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "select status,state_data from panic_watch_states where symbol=%s order by created_at desc limit 1",
                (symbol,),
            )
            row = cur.fetchone()
    if not row:
        return None
    return {"status": row[0], **(row[1] or {})}


def insert_panic_state(snapshot_id: str, symbol: str, state: dict[str, Any]) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "insert into panic_watch_states(snapshot_id,symbol,status,state_data) values(%s,%s,%s,%s)",
                (snapshot_id, symbol, state.get("status", "NORMAL"), Json(state)),
            )
        conn.commit()


def latest_snapshot() -> dict[str, Any] | None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("select snapshot_id,run_id,captured_at,market_data,macro_data from market_snapshots order by captured_at desc limit 1")
            row = cur.fetchone()
    if not row:
        return None
    return {"snapshot_id": str(row[0]), "run_id": str(row[1]), "captured_at": row[2].isoformat(), "market_data": row[3], "macro_data": row[4]}


def latest_judgments() -> list[dict[str, Any]]:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""select j.symbol,j.provider,j.model,j.model_version,j.prompt_version,j.input_data,j.output_data,j.created_at
                          from ai_judgments j join market_snapshots s on s.snapshot_id=j.snapshot_id
                          where s.snapshot_id=(select snapshot_id from market_snapshots order by captured_at desc limit 1)
                          order by j.symbol""")
            rows = cur.fetchall()
    return [{"symbol": r[0], "provider": r[1], "model": r[2], "model_version": r[3], "prompt_version": r[4], "input": r[5], "output": r[6], "created_at": r[7].isoformat()} for r in rows]


def latest_panic_states() -> list[dict[str, Any]]:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""select p.symbol,p.status,p.state_data,p.created_at
                          from panic_watch_states p join market_snapshots s on s.snapshot_id=p.snapshot_id
                          where s.snapshot_id=(select snapshot_id from market_snapshots order by captured_at desc limit 1)
                          order by p.symbol""")
            rows = cur.fetchall()
    return [{"symbol": r[0], "status": r[1], "state": r[2], "created_at": r[3].isoformat()} for r in rows]


# Legacy compatibility -----------------------------------------------------
def upsert_prices(rows):
    sql = """insert into prices_daily (date, code, close, volume) values %s
    on conflict (date, code) do update set close=EXCLUDED.close, volume=EXCLUDED.volume"""
    with get_conn() as conn:
        with conn.cursor() as cur: execute_values(cur, sql, rows)
        conn.commit()


def upsert_scores(rows):
    sql = """insert into templeton_scores (date, code, value, pessimism, risk, quality, growth, total)
    values %s on conflict (date, code) do update set value=EXCLUDED.value,pessimism=EXCLUDED.pessimism,
    risk=EXCLUDED.risk,quality=EXCLUDED.quality,growth=EXCLUDED.growth,total=EXCLUDED.total"""
    with get_conn() as conn:
        with conn.cursor() as cur: execute_values(cur, sql, rows)
        conn.commit()


if __name__ == "__main__":
    init_tables()
    print("tables ok")
