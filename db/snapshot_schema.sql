-- Templeton S snapshot pipeline
-- Safe additive schema: does not alter existing prices_daily / templeton_scores / macro_daily.

create table if not exists collection_runs (
  id bigserial primary key,
  slot_key text not null unique,
  started_at timestamptz not null default now(),
  finished_at timestamptz,
  status text not null default 'running',
  source text not null default 'oracle_cron',
  environment text,
  error text
);

create table if not exists market_snapshots (
  id bigserial primary key,
  run_id bigint not null references collection_runs(id) on delete cascade,
  captured_at timestamptz not null,
  captured_at_kst text not null,
  code text not null,
  name text not null,
  price numeric,
  change_rate numeric,
  score numeric,
  opinion text,
  value numeric,
  price_score numeric,
  pessimism numeric,
  quality numeric,
  growth numeric,
  risk numeric,
  market_regime text,
  panic_type text,
  opportunity_rank integer,
  opportunity_score numeric,
  payload jsonb not null default '{}'::jsonb,
  unique(run_id, code)
);

create index if not exists idx_market_snapshots_captured_at
  on market_snapshots(captured_at desc);
create index if not exists idx_market_snapshots_code_captured_at
  on market_snapshots(code, captured_at desc);

create table if not exists ai_judgments (
  id bigserial primary key,
  snapshot_id bigint not null references market_snapshots(id) on delete cascade,
  provider text not null,
  model text not null,
  status text not null,
  generated_at timestamptz not null default now(),
  comment text,
  positives jsonb not null default '[]'::jsonb,
  negatives jsonb not null default '[]'::jsonb,
  counter_argument text,
  change_conditions jsonb not null default '[]'::jsonb,
  raw_response text,
  error text,
  unique(snapshot_id, provider, model)
);

create index if not exists idx_ai_judgments_generated_at
  on ai_judgments(generated_at desc);

create table if not exists panic_events (
  id bigserial primary key,
  snapshot_id bigint not null references market_snapshots(id) on delete cascade,
  detected_at timestamptz not null default now(),
  panic_type text not null,
  market_regime text,
  details jsonb not null default '{}'::jsonb,
  unique(snapshot_id)
);

create table if not exists snapshot_outcomes (
  id bigserial primary key,
  snapshot_id bigint not null references market_snapshots(id) on delete cascade,
  horizon_days integer not null,
  evaluated_at timestamptz not null default now(),
  reference_price numeric,
  future_price numeric,
  return_pct numeric,
  benchmark_return_pct numeric,
  result jsonb not null default '{}'::jsonb,
  unique(snapshot_id, horizon_days)
);
