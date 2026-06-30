-- Sierra admin analytics — initial schema (single tenant: bizbull)
-- Apply to Supabase project in ca-central-1

-- ── Tenants (reference; v1 has one row) ─────────────────────────────────────

create table if not exists public.tenants (
  id text primary key,
  name text not null,
  phone_number text,
  web_url text,
  created_at timestamptz not null default now()
);

insert into public.tenants (id, name, phone_number, web_url)
values (
  'bizbull',
  'Bizbull Restaurant',
  '+15878175156',
  'https://voice.bizbull.ai'
)
on conflict (id) do nothing;

-- ── Admin allowlist (RLS read access) ───────────────────────────────────────

create table if not exists public.admin_users (
  email text primary key,
  created_at timestamptz not null default now()
);

-- Add your login email after first Supabase Auth signup:
-- insert into public.admin_users (email) values ('you@example.com');

-- ── Call sessions ───────────────────────────────────────────────────────────

create table if not exists public.call_sessions (
  id uuid primary key,
  tenant_id text not null default 'bizbull' references public.tenants (id),
  room_name text not null,
  channel text not null check (channel in ('phone', 'web')),
  participant_identity text,
  caller_phone text,
  started_at timestamptz not null,
  ended_at timestamptz,
  duration_seconds integer,
  outcome text check (outcome in (
    'placed', 'reservation', 'transfer', 'abandoned', 'empty', 'error'
  )),
  turn_count integer not null default 0,
  preferred_language text,
  customer_name text,
  customer_phone text,
  order_type text,
  delivery_address text,
  final_cart jsonb,
  order_total numeric(10, 2),
  items_count integer not null default 0,
  clover_order_id text,
  transfer_reason text,
  echo_filter_count integer not null default 0,
  background_filter_count integer not null default 0,
  avg_latency_ms integer,
  p95_latency_ms integer,
  recording_url text,
  tags text[] not null default '{}',
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists call_sessions_tenant_started_idx
  on public.call_sessions (tenant_id, started_at desc);

create index if not exists call_sessions_outcome_idx
  on public.call_sessions (outcome);

create index if not exists call_sessions_channel_idx
  on public.call_sessions (channel);

-- ── Call turns ──────────────────────────────────────────────────────────────

create table if not exists public.call_turns (
  id uuid primary key default gen_random_uuid(),
  session_id uuid not null references public.call_sessions (id) on delete cascade,
  turn_number integer not null,
  user_stt text,
  stt_language text,
  sierra_spoken text,
  intent text,
  phase text,
  was_filtered boolean not null default false,
  filter_reason text,
  auto_add boolean not null default false,
  tools_called jsonb not null default '[]'::jsonb,
  cart_snapshot jsonb,
  latency jsonb,
  created_at timestamptz not null default now(),
  unique (session_id, turn_number)
);

create index if not exists call_turns_session_idx
  on public.call_turns (session_id, turn_number);

-- ── Orders ──────────────────────────────────────────────────────────────────

create table if not exists public.orders (
  id uuid primary key default gen_random_uuid(),
  session_id uuid references public.call_sessions (id) on delete set null,
  tenant_id text not null default 'bizbull' references public.tenants (id),
  channel text not null,
  placed_at timestamptz not null,
  status text not null default 'logged',
  order_type text,
  items jsonb not null default '[]'::jsonb,
  subtotal numeric(10, 2),
  delivery_charge numeric(10, 2),
  total numeric(10, 2),
  customer_name text,
  customer_phone text,
  delivery_address text,
  clover_order_id text,
  created_at timestamptz not null default now()
);

create index if not exists orders_placed_at_idx
  on public.orders (placed_at desc);

-- ── Call events ─────────────────────────────────────────────────────────────

create table if not exists public.call_events (
  id uuid primary key default gen_random_uuid(),
  session_id uuid not null references public.call_sessions (id) on delete cascade,
  event_type text not null,
  payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists call_events_session_idx
  on public.call_events (session_id, created_at);

-- ── Call reviews (quality rubric) ───────────────────────────────────────────

create table if not exists public.call_reviews (
  id uuid primary key default gen_random_uuid(),
  session_id uuid not null unique references public.call_sessions (id) on delete cascade,
  reviewer_id uuid references auth.users (id),
  rubric jsonb not null default '{}'::jsonb,
  overall_pass boolean,
  naturalness smallint check (naturalness between 1 and 5),
  notes text,
  reviewed_at timestamptz not null default now()
);

-- ── Metrics views ───────────────────────────────────────────────────────────

create or replace view public.daily_call_stats as
select
  date_trunc('day', started_at at time zone 'America/Edmonton')::date as day,
  channel,
  count(*) as call_count,
  count(*) filter (where outcome = 'placed') as placed_count,
  round(avg(duration_seconds)::numeric, 0) as avg_duration_sec,
  round(avg(avg_latency_ms)::numeric, 0) as avg_latency_ms
from public.call_sessions
group by 1, 2
order by 1 desc, 2;

-- ── Row Level Security ──────────────────────────────────────────────────────

alter table public.tenants enable row level security;
alter table public.admin_users enable row level security;
alter table public.call_sessions enable row level security;
alter table public.call_turns enable row level security;
alter table public.orders enable row level security;
alter table public.call_events enable row level security;
alter table public.call_reviews enable row level security;

-- Service role (agent) bypasses RLS. Authenticated admins read via allowlist.

create policy "admin read tenants"
  on public.tenants for select to authenticated
  using ((auth.jwt() ->> 'email') in (select email from public.admin_users));

create policy "admin read sessions"
  on public.call_sessions for select to authenticated
  using ((auth.jwt() ->> 'email') in (select email from public.admin_users));

create policy "admin read turns"
  on public.call_turns for select to authenticated
  using (
    session_id in (
      select id from public.call_sessions
      where (auth.jwt() ->> 'email') in (select email from public.admin_users)
    )
  );

create policy "admin read orders"
  on public.orders for select to authenticated
  using ((auth.jwt() ->> 'email') in (select email from public.admin_users));

create policy "admin read events"
  on public.call_events for select to authenticated
  using (
    session_id in (
      select id from public.call_sessions
      where (auth.jwt() ->> 'email') in (select email from public.admin_users)
    )
  );

create policy "admin read reviews"
  on public.call_reviews for select to authenticated
  using ((auth.jwt() ->> 'email') in (select email from public.admin_users));

create policy "admin insert reviews"
  on public.call_reviews for insert to authenticated
  with check ((auth.jwt() ->> 'email') in (select email from public.admin_users));

create policy "admin update reviews"
  on public.call_reviews for update to authenticated
  using ((auth.jwt() ->> 'email') in (select email from public.admin_users));

create policy "admin read admin_users self"
  on public.admin_users for select to authenticated
  using (email = auth.jwt() ->> 'email');
