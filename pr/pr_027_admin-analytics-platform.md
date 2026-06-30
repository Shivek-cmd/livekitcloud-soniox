# PR 027 — Admin analytics platform (Supabase + dashboard)

## Branch
`pr_027_admin-analytics-platform`

## What This PR Does

Full **Sierra Admin Analytics Platform** in one PR:

1. **Supabase project `sierra-bizbull`** (ca-central-1, Canada) — schema for call sessions, turns, orders, events, reviews
2. **Agent session capture** — `SessionRecorder` buffers every call; async flush to Supabase on hangup (local JSON fallback)
3. **Admin dashboard** at **`https://admin.bizbull.ai`** — React app: login, overview KPIs, calls list, transcript detail, orders

Single tenant **`bizbull`** now; schema ready for multi-tenant later.

### Locked decisions
- Admin URL: **`admin.bizbull.ai`**
- Supabase project name: **`sierra-bizbull`**
- Project ref: **`lzlwivsntqkpxfwjktid`**
- Agent writes (service role); admin reads (Auth + RLS allowlist)
- Transcripts first — recordings deferred

## Files Added

### `docs/plan/12-admin-analytics-supabase.md`
Master plan document.

### `supabase/migrations/001_initial_analytics.sql`
Postgres schema: `tenants`, `admin_users`, `call_sessions`, `call_turns`, `orders`, `call_events`, `call_reviews`, RLS policies, `daily_call_stats` view.

### `restaurant/session_recorder.py`
In-memory per-call buffer: turns, tools, latency, cart snapshots, events.

### `restaurant/analytics_store.py`
Async Supabase persist + `data/sessions/` JSON fallback.

### `admin/` (Vite + React + TypeScript)
- Supabase Auth login
- Overview (7-day KPIs)
- Calls list + call detail (transcript timeline)
- Orders list

### `admin/.env.example`
`VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`

### `admin/src/vite-env.d.ts`
Vite `import.meta.env` TypeScript types (fixes `npm run build` on VPS).

### `tests/test_session_recorder.py`
Unit tests for recorder finalize and echo filter.

## Files Modified

### `agent.py`
- `SessionRecorder` wired in `entrypoint`
- Turn capture: STT, Sierra speech, intent/phase, echo/background filters, tools, latency
- Shutdown callback → `persist_session()`

### `restaurant/turn_latency.py`
Optional `on_turn_latency` callback for analytics.

### `pyproject.toml`
Add `supabase>=2.0`.

### `.env.example`
Supabase env vars for VPS agent.

### `.gitignore`
`admin/dist/`, `data/sessions/`

### `docs/README.md`, `pr/README.md`
Index updates.

## Files Deleted
None.

## What's NOT in This PR
- Call audio recordings (Twilio / LiveKit egress)
- Quality rubric UI (`call_reviews` table exists; UI later)
- `learning_suggestions` auto-queue
- Multi-tenant admin UI
- Customer web app changes

## Supabase setup (one-time)

Migration applied via Supabase MCP to project **`lzlwivsntqkpxfwjktid`**.

**After merge, owner must:**

1. Supabase Dashboard → **Authentication → Users** → create admin user (email + password)
2. SQL Editor:
   ```sql
   insert into public.admin_users (email) values ('your@email.com');
   ```
3. Settings → API → copy **service_role** key → VPS `.env` as `SUPABASE_SERVICE_ROLE_KEY`
4. Copy **anon** key → `admin/.env` as `VITE_SUPABASE_ANON_KEY`

## VPS deploy

```bash
# Agent env (/opt/livekit-sarvam/.env)
SUPABASE_URL=https://lzlwivsntqkpxfwjktid.supabase.co
SUPABASE_SERVICE_ROLE_KEY=...
SESSION_ANALYTICS_ENABLED=1

# Sync deps + restart agent
cd /opt/livekit-sarvam && git pull origin main && uv sync
systemctl restart restaurant-agent

# Build admin app
cd admin && npm ci && npm run build
# Serve admin/dist via Caddy → admin.bizbull.ai (see docs/vps-config.md)
```

## How to Test

```bash
uv run python -m pytest tests/test_session_recorder.py -v
cd admin && npm install && npm run dev
```

## Post-Merge: VPS Pull Command

```bash
cd /opt/livekit-sarvam && git pull origin main && uv sync && systemctl restart restaurant-agent
```
