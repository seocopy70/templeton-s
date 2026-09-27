-- Additive schema for the existing Neon snapshot design.
-- collection_runs, market_snapshots and ai_judgments already exist in Neon.
-- Do not recreate or alter those tables here.

create table if not exists panic_events (
  id bigserial primary key,
  snapshot_id uuid not null references market_snapshots(snapshot_id) on delete cascade,
  detected_at timestamptz not null default now(),
  panic_type text not null,
  market_regime text,
  details jsonb not null default '{}'::jsonb,
  unique(snapshot_id)
);

create index if not exists idx_panic_events_detected_at
  on panic_events(detected_at desc);

create table if not exists snapshot_outcomes (
  id bigserial primary key,
  snapshot_id uuid not null references market_snapshots(snapshot_id) on delete cascade,
  symbol text not null,
  horizon_days integer not null,
  evaluated_at timestamptz not null default now(),
  reference_price numeric,
  future_price numeric,
  return_pct numeric,
  benchmark_return_pct numeric,
  result jsonb not null default '{}'::jsonb,
  unique(snapshot_id, symbol, horizon_days)
);

create index if not exists idx_snapshot_outcomes_snapshot
  on snapshot_outcomes(snapshot_id);

-- Safe migration for the original draft table, if it was created before
-- per-symbol outcomes were introduced.
alter table snapshot_outcomes
  add column if not exists symbol text;

alter table snapshot_outcomes
  drop constraint if exists snapshot_outcomes_snapshot_id_horizon_days_key;

create unique index if not exists uq_snapshot_outcomes_snapshot_symbol_horizon
  on snapshot_outcomes(snapshot_id, symbol, horizon_days);
