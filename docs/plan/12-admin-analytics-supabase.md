# Admin Analytics Platform — Supabase + Dashboard (plan)

> **Status:** Planning only (PR 027). Implementation in PR 028+.
> **Goal:** Capture every Sierra call (phone + web), store structured transcripts and orders in **Supabase (ca-central-1)**, and give the owner a **React admin dashboard** for metrics, review, and quality testing — single tenant (**Bizbull**) now, schema ready for multi-tenant later.
> **Context:** [`HANDOFF.md`](../HANDOFF.md) · voice quality backlog [`10-voice-quality-tier-b.md`](10-voice-quality-tier-b.md)

---

## 1. Problem statement

Today Sierra logs `USER:` / `SIERRA:` / `TURN_GUIDANCE` / `ORDER_PLACED` to **journalctl only**. That makes it hard to:

- Run 50–100 structured test calls and compare results
- See completion rate, drop-off phase, latency trends
- Verify STT heard the caller correctly vs what Sierra did
- Review placed orders after the fact
- Build a learning loop (failed menu search → alias fix)

**This plan adds a durable analytics layer without slowing the live voice path.**

---

## 2. Product shape

### Who uses it

| User | App | Auth |
|------|-----|------|
| Customer | `voice.bizbull.ai` (existing) | None — LiveKit token |
| Owner / QA (you) | `admin.bizbull.ai` (new) | Supabase Auth (email) |
| Agent worker | VPS `agent.py` | `SUPABASE_SERVICE_ROLE_KEY` (write only) |

### Admin dashboard (v1 pages)

```
┌─────────────────────────────────────────────────────────────┐
│  Sierra Admin — Bizbull Restaurant                          │
├──────────────┬──────────────────────────────────────────────┤
│  Overview    │  KPIs: calls today/7d, completion %, latency │
│  Calls       │  Searchable list, filters (channel, outcome) │
│  Call detail │  Transcript timeline, cart, tools, latency   │
│  Orders      │  Placed orders, export CSV                   │
│  Quality     │  Rubric scores, review queue (v1.1)          │
└──────────────┴──────────────────────────────────────────────┘
```

Recordings (Twilio / LiveKit egress) → **Phase D7** — transcripts first.

---

## 3. Architecture

```
CUSTOMER                    VPS AGENT                         SUPABASE (ca-central-1)
────────                    ─────────                         ─────────────────────
Phone / Web  ──LiveKit──►  agent.py
                           SessionRecorder (in-memory)
                           STT → LLM → TTS  (unchanged)
                                │
                           on session end (async, non-blocking)
                                │
                                └──────────────────────────────►  Postgres
                                                                  call_sessions
                                                                  call_turns
                                                                  orders
                                                                  call_events

YOU  ──browser──►  admin/ (React + Vite)
                   Supabase JS (anon + Auth)
                   read via RLS ◄────────────────────────────────  same DB
```

### Design rules (locked)

1. **Hot path unchanged** — no Supabase round-trip during STT/LLM/TTS turns.
2. **Agent writes** — service role on VPS only; never in customer web app.
3. **Admin reads** — authenticated user via RLS; anon key in admin SPA only.
4. **Single tenant now** — `tenant_id = 'bizbull'` on every row; no multi-tenant UI until needed.
5. **Fail open on voice** — if Supabase write fails, call completes; buffer to local JSON fallback.
6. **New Supabase project** — dedicated project in **`ca-central-1`** (Canada), separate from legacy `restaurant-platform` / Square POS projects.

---

## 4. Supabase project

| Setting | Value |
|---------|--------|
| Name | `sierra-bizbull` |
| Region | **`ca-central-1`** |
| Project ref | **`lzlwivsntqkpxfwjktid`** |
| URL | `https://lzlwivsntqkpxfwjktid.supabase.co` |
| Admin URL | **`https://admin.bizbull.ai`** |

**Not migrated in v1:** SQLite `data/tenants.db`, menu JSON cache — stay on VPS for speed.

### Environment variables

| Variable | Where | Purpose |
|----------|--------|---------|
| `SUPABASE_URL` | VPS `.env` | Project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | VPS `.env` | Agent insert (bypass RLS) |
| `VITE_SUPABASE_URL` | `admin/.env` | Admin SPA |
| `VITE_SUPABASE_ANON_KEY` | `admin/.env` | Admin SPA + RLS |
| `SESSION_RECORDING_ENABLED` | VPS `.env` | `1` to flush to Supabase (default `0` until PR 029) |
| `SESSION_FALLBACK_DIR` | VPS `.env` | `data/sessions/` local JSON if remote write fails |

---

## 5. Database schema

### 5.1 `tenants` (reference row, not full POS config)

Minimal row for future multi-tenant; v1 has one row `bizbull`.

| Column | Type | Notes |
|--------|------|-------|
| `id` | text PK | `'bizbull'` |
| `name` | text | Bizbull Restaurant |
| `phone_number` | text | `+15878175156` |
| `web_url` | text | `https://voice.bizbull.ai` |
| `created_at` | timestamptz | |

### 5.2 `call_sessions` (one row per call)

| Column | Type | Source / notes |
|--------|------|----------------|
| `id` | uuid PK | Generated at session start |
| `tenant_id` | text FK | `'bizbull'` |
| `room_name` | text | LiveKit room |
| `channel` | text | `phone` \| `web` |
| `participant_identity` | text | SIP / web identity |
| `caller_phone` | text | SIP attribute or cart |
| `started_at` | timestamptz | Session connect |
| `ended_at` | timestamptz | Shutdown callback |
| `duration_seconds` | int | Computed |
| `outcome` | text | See §6 |
| `turn_count` | int | |
| `preferred_language` | text | `en` \| `pa` \| `hi` from order flow |
| `customer_name` | text | Final cart |
| `customer_phone` | text | Final cart |
| `order_type` | text | pickup \| delivery |
| `delivery_address` | text | |
| `final_cart` | jsonb | Full cart snapshot |
| `order_total` | numeric | |
| `items_count` | int | |
| `clover_order_id` | text | Phase 8c |
| `transfer_reason` | text | If `transfer_to_human` |
| `echo_filter_count` | int | Turns dropped as echo |
| `background_filter_count` | int | Turns dropped as background |
| `avg_latency_ms` | int | Mean user_stop→speaking |
| `p95_latency_ms` | int | |
| `recording_url` | text | Phase D7 |
| `tags` | text[] | e.g. `{test,scenario_12}` |
| `metadata` | jsonb | git sha, sip call id, deploy version |
| `created_at` | timestamptz | |

**Indexes:** `(tenant_id, started_at DESC)`, `(outcome)`, `(channel)`, `(caller_phone)`.

### 5.3 `call_turns` (many per session)

| Column | Type | Notes |
|--------|------|-------|
| `id` | uuid PK | |
| `session_id` | uuid FK | → `call_sessions.id` |
| `turn_number` | int | 1-based |
| `user_stt` | text | Final Soniox transcript |
| `stt_language` | text | If available |
| `sierra_spoken` | text | Assistant text (post-sanitize log) |
| `intent` | text | `resolve_intent` value |
| `phase` | text | `OrderPhase` value |
| `was_filtered` | boolean | Echo / background drop |
| `filter_reason` | text | `echo` \| `background` |
| `auto_add` | boolean | PR 024 fast-path |
| `tools_called` | jsonb | `[{name, args, result}]` |
| `cart_snapshot` | jsonb | Cart after turn |
| `latency` | jsonb | `{eou_delay, llm_ttft, tts_ttfb, user_stop_to_speaking_ms}` |
| `created_at` | timestamptz | |

**Index:** `(session_id, turn_number)`.

### 5.4 `orders` (denormalized placed orders)

| Column | Type | Notes |
|--------|------|-------|
| `id` | uuid PK | |
| `session_id` | uuid FK | |
| `tenant_id` | text FK | |
| `channel` | text | |
| `placed_at` | timestamptz | |
| `status` | text | `logged` → `submitted_clover` → `printed` |
| `order_type` | text | |
| `items` | jsonb | Line items |
| `subtotal` | numeric | |
| `delivery_charge` | numeric | |
| `total` | numeric | |
| `customer_name` | text | |
| `customer_phone` | text | |
| `delivery_address` | text | |
| `clover_order_id` | text | Phase 8c |
| `created_at` | timestamptz | |

### 5.5 `call_events` (optional audit log)

Lightweight events: `session_started`, `order_placed`, `transfer_requested`, `menu_search_empty`, `reservation_booked`.

| Column | Type |
|--------|------|
| `id` | uuid PK |
| `session_id` | uuid FK |
| `event_type` | text |
| `payload` | jsonb |
| `created_at` | timestamptz |

### 5.6 `call_reviews` (quality / 50–100 call program)

| Column | Type | Notes |
|--------|------|-------|
| `id` | uuid PK | |
| `session_id` | uuid FK unique | One review per call |
| `reviewer_id` | uuid | `auth.users.id` |
| `rubric` | jsonb | See §8 |
| `overall_pass` | boolean | |
| `naturalness_1_5` | smallint | Manual |
| `notes` | text | |
| `reviewed_at` | timestamptz | |

### 5.7 `learning_suggestions` (Phase D8)

Auto-created on repeated failures (empty menu search, availability without tool). Status: `pending` \| `approved` \| `rejected`.

### 5.8 SQL views (dashboard metrics)

- `daily_call_stats` — date, channel, count, placed_count, avg_duration, avg_latency
- `phase_dropoff` — last phase for non-placed calls

### 5.9 Row Level Security

| Role | Policy |
|------|--------|
| `service_role` (agent) | INSERT on sessions, turns, orders, events |
| `authenticated` admin | SELECT all; INSERT/UPDATE on `call_reviews` |
| `anon` | No access to call data |

Admin users: create in Supabase Auth; link via allowlist table `admin_users(email)` or hardcoded email check in RLS for v1.

---

## 6. Session outcome taxonomy

Derived at session end from cart + flow + tools:

| `outcome` | Condition |
|-----------|-----------|
| `placed` | `place_order` succeeded |
| `reservation` | `book_reservation` succeeded |
| `transfer` | `transfer_to_human` called |
| `abandoned` | Ended with items but no place |
| `empty` | No items, no reservation |
| `error` | Agent crash / write failure flagged |

---

## 7. What to capture from each call (agent hooks)

### Session start (`entrypoint`)

- Generate `session_id` (UUID)
- Record: `room_name`, `channel`, `participant_identity`, `started_at`
- Extract `caller_phone` from SIP participant attributes when present
- Event: `session_started`

### Each user turn (`on_user_turn_completed` + transcript handler)

- `user_stt` (final)
- `intent`, `phase` (after `resolve_intent` / flow)
- `was_filtered`, `filter_reason` if echo/background drop
- `auto_add` if fast-path fired
- Append to in-memory turn list

### Each assistant turn (`conversation_item_added`)

- `sierra_spoken`
- Attach to current turn or new assistant segment

### Tool calls (wrap or log in agent)

- `tools_called` with name, args, truncated result
- Event on `menu_search_empty`, `transfer_to_human`, `place_order`

### Cart mutations

- `cart_snapshot` json after each meaningful change

### Latency (`TurnLatencyTracker`)

- Merge `latency` json into current turn on `LATENCY` emit

### Session end (`ctx.add_shutdown_callback`)

- Compute: `duration`, `outcome`, aggregates, `final_cart`
- Async flush: insert session → batch insert turns → insert order if placed
- Fallback: write `data/sessions/{session_id}.json`

### Explicitly NOT captured on hot path

- Partial STT (optional debug flag later)
- Full LLM prompt / raw tool internals
- Audio bytes (use recording URL in D7)

---

## 8. Scoring rubric (admin Quality page)

Stored in `call_reviews.rubric` as JSON:

```json
{
  "stt_accurate": true,
  "intent_correct": true,
  "phase_advanced": true,
  "cart_correct": true,
  "menu_tool_used": true,
  "no_price_leak_phone": true,
  "confirm_flow_ok": true,
  "order_completed": false
}
```

Manual: `naturalness_1_5`, free-text `notes`.

Supports regression replay: export session → pytest golden file (see PR D6).

---

## 9. Admin React app

| Item | Choice |
|------|--------|
| Location | `admin/` (new Vite + React + TypeScript) |
| URL | `admin.bizbull.ai` (Caddy on VPS) or subdomain TBD |
| UI | Tailwind; charts via Recharts |
| Auth | Supabase Auth — magic link or email/password |
| Data | `@supabase/supabase-js` — realtime optional on `call_sessions` |

**v1 screens:** Login → Overview → Calls list → Call detail → Orders.

Customer `web/` app **does not** import Supabase analytics client.

---

## 10. Phased delivery

**Single PR 027** ships everything: Supabase schema, agent capture, admin dashboard.

| Component | PR 027 |
|-----------|--------|
| Supabase `sierra-bizbull` (ca-central-1) | ✅ |
| Agent session recorder + writer | ✅ |
| Admin `admin.bizbull.ai` | ✅ |
| Call recordings | deferred |
| Quality rubric UI | deferred |

---

## 11. Metrics (automatic from schema)

| Metric | Definition |
|--------|------------|
| Calls / day | `count(call_sessions)` |
| Completion rate | `placed / total` |
| Phone vs web | Group by `channel` |
| Avg duration | `avg(duration_seconds)` |
| Avg latency | `avg(avg_latency_ms)` |
| Drop-off by phase | Last `call_turns.phase` where outcome ≠ placed |
| Transfer rate | `outcome = transfer` |
| Echo/background rate | `sum(echo_filter_count + background_filter_count)` |
| Test call volume | `tags @> '{test}'` |
| Revenue (logged) | `sum(order_total)` where placed |

---

## 12. Security & privacy

- PII: phone, name, address — admin-only; never expose via public API
- Service role key: VPS only; rotate if leaked
- RLS enabled on all public tables
- Optional: mask phone in admin list UI (`+1••••5156`)
- Retention policy (TBD): e.g. delete transcripts > 90 days — not v1

---

## 13. Relationship to other workstreams

| Workstream | Interaction |
|------------|-------------|
| Voice quality Tier B | Dashboard surfaces B-2/B-11 failures; fixes still code PRs |
| Web W3–W5 | Web calls appear in same `call_sessions` with `channel=web` |
| Clover 8c | `clover_order_id` + `orders.status` updated on POS submit |
| Multi-tenant | Add tenants + RLS by `tenant_id`; map phone → tenant later |
| Legacy `restaurant-platform` Supabase | **Do not use** — fresh project for this repo |

---

## 14. Out of scope (v1)

- Customer-facing order history portal
- Auto-learning / prompt rewrites from transcripts
- Moving menu cache or live cart to Supabase
- Multi-restaurant admin UI
- Public API for third parties
- Real-time supervisor listen-in

---

## 15. Verification checklist

After D3 (Supabase writer live):

- [ ] Phone test call → row in `call_sessions`, turns in `call_turns`
- [ ] Web test call → `channel=web`
- [ ] Placed order → row in `orders` linked to session
- [ ] Supabase down → call still works; JSON in `data/sessions/`
- [ ] Admin login → see call in list within 30s of hangup
- [ ] RLS: unauthenticated client cannot read `call_sessions`

---

## 16. Files anticipated (implementation PRs)

| Area | Path |
|------|------|
| Plan | `docs/plan/12-admin-analytics-supabase.md` (this file) |
| SQL migration | `supabase/migrations/001_initial_analytics.sql` |
| Session recorder | `restaurant/session_recorder.py` |
| Supabase writer | `restaurant/analytics_store.py` |
| Agent hooks | `agent.py` |
| Admin SPA | `admin/src/` |
| Env template | `.env.example`, `admin/.env.example` |
| Caddy | `docs/vps-config.md` — `admin.bizbull.ai` block |

---

## 17. Decisions (locked for planning)

1. **New Supabase project** in **ca-central-1** — not legacy projects.
2. **Transcripts before recordings** — D7 deferred.
3. **Agent-side write, admin-side read** — no customer Supabase client.
4. **Single tenant `bizbull`** — schema uses `tenant_id` anyway.
5. **Async flush on hangup** — never block TTS for DB.

**Open (decide before deploy):** none — **admin.bizbull.ai** and **sierra-bizbull** confirmed.
