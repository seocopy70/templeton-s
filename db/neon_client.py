import os
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv

load_dotenv("config/.env")  # local dev fallback

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
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(ddl)
        conn.commit()
    print("tables ok")

def upsert_prices(rows):
    # rows: list of (date, code, close, volume)
    sql = """
    insert into prices_daily (date, code, close, volume)
    values %s
    on conflict (date, code) do update set close=EXCLUDED.close, volume=EXCLUDED.volume
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            execute_values(cur, sql, rows)
        conn.commit()

def upsert_scores(rows):
    sql = """
    insert into templeton_scores (date, code, value, pessimism, risk, quality, growth, total)
    values %s
    on conflict (date, code) do update set
      value=EXCLUDED.value, pessimism=EXCLUDED.pessimism, risk=EXCLUDED.risk,
      quality=EXCLUDED.quality, growth=EXCLUDED.growth, total=EXCLUDED.total
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            execute_values(cur, sql, rows)
        conn.commit()

if __name__ == "__main__":
    init_tables()