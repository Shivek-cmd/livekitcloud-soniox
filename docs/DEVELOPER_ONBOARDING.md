# Sierra — Bizbull Restaurant Voice Agent
## Developer Onboarding & Architecture Reference

> **Repository:** `https://github.com/Shivek-cmd/livekitcloud-soniox`  
> **VPS path:** `/opt/livekit-sarvam` @ `89.117.18.192`  
> **Production `main`:** includes Engine Rebuild (PR #95) — **not live yet**; production still runs `agent.py`  
> **See also:** [`HANDOFF.md`](HANDOFF.md) (session state), [`vps-config.md`](vps-config.md) (ops), [`plan/02-architecture.md`](plan/02-architecture.md) (diagrams)

---

## 1. Executive Summary

**Sierra** is a multilingual (Punjabi / Hindi / English) voice ordering agent for **Bizbull Restaurant** (Canadian market). Callers can order by **phone** or **web**. Orders are matched against a **Clover POS menu cache** and can be submitted to Clover when enabled.

| Channel | Entry point | Agent dispatch |
|---------|-------------|----------------|
| **Phone** | `+1 587-817-5156` → Twilio → LiveKit Cloud SIP | `restaurant-agent` |
| **Web** | `https://voice.bizbull.ai` | `restaurant-agent` |
| **Admin** | `https://admin.bizbull.ai` | React dashboard (call analytics) |

**Stack:** LiveKit Cloud (media + SIP) · Soniox STT/TTS · OpenAI GPT-4o-mini · Clover API · Supabase analytics

---

## 1.1 Live products (production URLs)

Both apps are **live on the VPS** today, served by Caddy on `89.117.18.192`.

### Web ordering — `https://voice.bizbull.ai`

Customer-facing app for **voice ordering with Sierra in the browser** (same agent worker as phone).

| Item | Detail |
|------|--------|
| **URL** | `https://voice.bizbull.ai` |
| **Status** | Live (W1 shell + W2 live cart — PR 011–012) |
| **Auth** | None — browser gets a LiveKit token from the token server |
| **Agent** | Dispatches `restaurant-agent` (same pipeline as phone) |

**What the user sees:**

- **Order with Sierra** tab — WebRTC voice session; talk to Sierra; live captions + hybrid cart panel
- **Store** tab — browse menu catalog (from `GET /menu` on token server)

**How it works behind the scenes:**

```
Browser → GET /token (Caddy → token_server :8001)
       → LiveKit room + restaurant-agent joins
       → Soniox STT → GPT-4o-mini → Soniox TTS
       → Cart state pushed to UI via web_sync.py
```

**Caddy routing** (`docs/vps-config.md`):

- `/token`, `/menu`, `/health` → `localhost:8001` (`restaurant-token.service`)
- Everything else → static `web/dist`

**Quick health check:**

```bash
curl -s https://voice.bizbull.ai/health
# {"status":"ok"}
```

**Developer test:** Open `https://voice.bizbull.ai` → **Order with Sierra** → allow mic → place a test order (sandbox Clover if `CLOVER_SUBMIT_ORDERS=1`).

---

### Admin analytics — `https://admin.bizbull.ai`

Internal dashboard for **call analytics, transcripts, and order review** (PR 027).

| Item | Detail |
|------|--------|
| **URL** | `https://admin.bizbull.ai` |
| **Status** | Live |
| **Auth** | Supabase email + password (see below) |
| **Data source** | Supabase project `sierra-bizbull` (ca-central-1) |
| **Agent write path** | `SessionRecorder` in `agent.py` → flush on session end |

**Login (team access):**

| Field | Value |
|-------|-------|
| **URL** | `https://admin.bizbull.ai/login` |
| **Email** | `sandeeptaur@gmail.com` |
| **Password** | Provided by project owner out-of-band (not stored in this repo) |

> **Security:** Do not commit admin passwords to git or Notion public pages. Share credentials via 1Password / secure channel when onboarding a developer.

**What you can do in the admin app:**

| Page | Route | Purpose |
|------|-------|---------|
| **Dashboard** | `/` | KPIs — calls today/7d, completion rate, latency overview |
| **Calls** | `/calls` | Searchable call list (phone + web), filter by channel/outcome |
| **Call detail** | `/calls/:id` | **Full transcript timeline** — what caller said (STT) vs what Sierra spoke, cart state, tools, phase, latency per turn |
| **Orders** | `/orders` | Placed orders, export/review |

**Use admin to:**

- Review STT accuracy vs Sierra responses after live or test calls
- Debug order-flow issues (fish disambiguation, name/phone capture, etc.)
- Confirm `ORDER_PLACED` / Clover submit outcomes
- Compare phone vs web channel behavior

**Requires on VPS** (`/opt/livekit-sarvam/.env`):

```
SESSION_ANALYTICS_ENABLED=1
SUPABASE_URL=https://lzlwivsntqkpxfwjktid.supabase.co
SUPABASE_SERVICE_ROLE_KEY=<secret>
SESSION_FALLBACK_DIR=data/sessions
```

If Supabase write fails, sessions may still land in `data/sessions/*.jsonl` on the VPS as fallback.

**Admin frontend env** (`admin/.env` on build machine / VPS):

```
VITE_SUPABASE_URL=https://lzlwivsntqkpxfwjktid.supabase.co
VITE_SUPABASE_ANON_KEY=<anon key from Supabase dashboard>
```

Rebuild after admin code changes: `cd admin && npm run build` (also run by `scripts/vps_deploy.sh`).

**Caddy** serves `admin/dist` at `admin.bizbull.ai` (see `docs/vps-config.md`).

---

## 2. System Architecture

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                         CUSTOMER ENTRY (live voice)                             │
├───────────────────────────────┬──────────────────────────────────────────────┤
│  WEB — voice.bizbull.ai       │  PHONE — +15878175156                         │
│  Caddy → web/dist + /token    │  Twilio → LiveKit Cloud SIP                  │
│  Browser (WebRTC)             │  PSTN caller                                  │
│       │                       │       │                                       │
│       └───────────┬───────────┴───────┘                                       │
│                   ▼                                                           │
│         LiveKit Cloud (US West)                                               │
│         wss://bizbull-restaurant-cyeyyw0l.livekit.cloud                       │
│         - Per-caller rooms · Krisp NC on SIP trunk                            │
└───────────────────────────┬──────────────────────────────────────────────────┘
                            │ wss
                            ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│  VPS — /opt/livekit-sarvam (Seattle / US West)                                │
│                                                                               │
│  restaurant-agent.service   →  agent.py start        (port 8081)           │
│  restaurant-token.service   →  token_server.py         (port 8001)           │
│  caddy.service              →  TLS + static sites                             │
│                                                                               │
│  Voice loop:  Soniox STT → GPT-4o-mini → Soniox TTS (Maya, pa)              │
│  Menu:        Clover cache JSON + voice labels                                │
│  Orders:      OrderCart → Clover submit (optional)                            │
│                                                                               │
│  On session end (async):  SessionRecorder → analytics_store → Supabase      │
│                            └─ fallback: data/sessions/*.jsonl on VPS          │
└───────────────────────────┬──────────────────────────────────────────────────┘
                            │ write (service role)
                            ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│  Supabase — sierra-bizbull (ca-central-1)                                     │
│  call_sessions · call_turns · orders · call_events                            │
└───────────────────────────┬──────────────────────────────────────────────────┘
                            │ read (anon + Auth RLS)
                            ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│  ADMIN — admin.bizbull.ai  (internal QA / owner dashboard)                    │
│  Caddy → admin/dist (React) · Supabase Auth login                             │
│  Dashboard · Calls list · Call detail (transcripts) · Orders                  │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Caddy on VPS (public URLs)

| Hostname | Serves | Backend |
|----------|--------|---------|
| `voice.bizbull.ai` | Customer web app | `web/dist` + proxy `/token`, `/menu`, `/health` → `:8001` |
| `admin.bizbull.ai` | Admin analytics SPA | `admin/dist` (reads Supabase in browser) |

Both hostnames terminate TLS on the same VPS Caddy instance. Neither runs the voice agent directly — they are **frontends**; voice processing stays in `restaurant-agent` + LiveKit Cloud.

### Call flow — Phone

1. Caller dials `+15878175156`
2. Twilio routes via SIP to LiveKit Cloud (`sip:5qg9858y0ak.sip.livekit.cloud`)
3. Dispatch rule creates room + dispatches `restaurant-agent`
4. Agent greets → STT → LLM (+ tools) → TTS loop
5. On `place_order()` → optional Clover submit → goodbye → auto hang-up

### Call flow — Web

1. User opens `voice.bizbull.ai`
2. Frontend calls `GET /token` on token server
3. Token server issues LiveKit JWT + dispatches `restaurant-agent`
4. Browser joins room via WebRTC; same agent pipeline as phone
5. Hybrid cart synced to UI via `web_sync.py`

### Analytics flow — Admin (`admin.bizbull.ai`)

Admin is **not** on the live voice path. It is a **read-only dashboard** over data the agent writes after each call.

```
Phone or Web call
  → agent.py (SessionRecorder captures turns, cart, tools, latency in memory)
  → session end / shutdown
  → analytics_store.py flushes to Supabase (async, fail-open)
  → owner opens admin.bizbull.ai
  → React app (admin/) queries Supabase with logged-in user
  → Call detail page shows full transcript timeline
```

- **Write:** VPS agent only (`SUPABASE_SERVICE_ROLE_KEY`)
- **Read:** Browser admin app (`VITE_SUPABASE_ANON_KEY` + email login)
- **No customer access** to admin — separate hostname and Supabase Auth

---

## 3. Technology Stack

| Layer | Technology | Notes |
|-------|------------|-------|
| Runtime | Python 3.10+ | Managed with `uv` |
| Agent framework | `livekit-agents` 1.x | `agent.py` entrypoint |
| STT | Soniox `stt-rt-v5` | Hints: `pa`, `en`, `hi` |
| LLM | OpenAI `gpt-4o-mini` | Streaming, function tools |
| TTS | Soniox `tts-rt-v1` | Voice `Maya`, language `pa` |
| Telephony | Twilio + LiveKit Cloud SIP | Inbound primary |
| POS | Clover REST API | Sandbox or production |
| Analytics DB | Supabase (ca-central-1) | Session + transcript storage |
| Web UI | React + Vite + TypeScript | `web/` |
| Admin UI | React + Vite + TypeScript | `admin/` |
| Reverse proxy | Caddy | Serves static builds + TLS |
| Tests | pytest | `tests/` |

---

## 4. Repository Structure

```
livekitcloud-soniox/
├── agent.py                    # ★ PRODUCTION entrypoint — voice agent worker
├── token_server.py             # Web token + menu API + agent dispatch
├── pyproject.toml              # Python deps (uv)
├── .env.example                # Env template (never commit real .env)
│
├── deploy/
│   ├── restaurant-agent.service   # systemd: agent.py start
│   └── restaurant-token.service   # systemd: token server :8001
│
├── restaurant/                 # ★ Core Python package
│   ├── conversation.py         # Intents, templates, opening greeting
│   ├── order_flow.py           # Phase machine + per-turn LLM guidance
│   ├── order_parse.py          # Multi-item utterance parsing
│   ├── orders.py               # OrderCart — cart state + pricing
│   ├── menu_provider.py        # Menu facade (Clover cache vs static)
│   ├── menu_browse.py          # Category/family browse (mithai, fish, etc.)
│   ├── customer_info.py        # Name/phone parsing from STT
│   ├── prompts.py              # System prompts (phone + web)
│   ├── voice_stack.py          # Soniox STT/TTS factory
│   ├── session_config.py       # Turn detection, endpointing, BVC
│   ├── session_recorder.py     # Call analytics capture
│   ├── analytics_store.py      # Supabase flush
│   ├── web_sync.py             # Push cart state to web UI
│   ├── call_control.py         # Auto hang-up after order
│   ├── ambient_audio.py        # Background restaurant ambience
│   ├── fillers.py              # Intent-based voice fillers
│   ├── phone_echo.py           # Echo / re-greeting guards
│   ├── phone_background.py     # Background speech filter
│   ├── stt_noise.py            # STT noise rejection
│   ├── llm_warmup.py           # LLM cache warmup on session start
│   ├── turn_latency.py         # Per-turn latency logging
│   ├── text_match.py           # Indic-safe regex helpers
│   ├── menu.py                 # Static fallback menu
│   ├── reservations.py         # Table booking tools
│   │
│   ├── clover/                 # Clover POS integration
│   │   ├── client.py           # HTTP client
│   │   ├── menu.py             # MenuCache sync/load/save
│   │   ├── match.py            # Cross-script phonetic matcher
│   │   ├── order_submit.py     # Submit OrderCart → Clover
│   │   ├── speech_policy.py    # voice_line / speak_as rules
│   │   ├── voice_labels.py     # Voice label helpers
│   │   ├── models.py           # CachedMenuItem dataclasses
│   │   └── seed_menu.py        # Category seed data
│   │
│   ├── tenants/                # Multi-tenant config (single tenant today)
│   │   ├── config.py           # get_default_tenant()
│   │   └── store.py            # SQLite tenant DB
│   │
│   └── engine/                 # ★ NEW — deterministic order engine (NOT live)
│       ├── README.md           # Architecture + rollout status
│       ├── core.py             # OrderEngine state machine (pure)
│       ├── extractor.py        # LLM → Proposal JSON
│       ├── renderer.py         # Action → spoken templates (en/pa)
│       ├── resolver.py         # CloverResolver adapter
│       └── live.py             # Alternate entrypoint (engine-restaurant-agent)
│
├── data/
│   ├── menu_cache_bizbull.json # Clover menu cache (~61 items)
│   ├── clover_voice_labels.json# TTS voice lines + aliases per item
│   ├── tenants.db              # Tenant Clover credentials
│   ├── sessions/               # Analytics fallback JSONL
│   └── audio/restaurant_ambience.mp3
│
├── web/                        # Customer web app (voice.bizbull.ai)
│   └── src/
│       ├── App.tsx
│       ├── components/         # SierraPanel, OrderPanel, StoreTab
│       └── hooks/useCart.tsx
│
├── admin/                      # Admin dashboard (admin.bizbull.ai)
│   └── src/pages/              # Dashboard, CallsList, CallDetail
│
├── scripts/
│   ├── vps_deploy.sh           # ★ Production deploy script
│   ├── setup_sip.py            # LiveKit Cloud SIP trunk + dispatch
│   ├── setup_twilio_sip.py     # Twilio → LiveKit origination
│   ├── clover_sync_menu.py     # Sync menu from Clover → cache JSON
│   ├── rebuild_voice_labels.py # Rebuild voice label index
│   ├── clover_init_tenant.py   # Initialize tenant in SQLite
│   ├── test_call.py            # Outbound test call via Twilio
│   └── clover_sandbox_*.py     # Sandbox setup/probe/cleanup
│
├── tests/                      # pytest suite
├── docs/                       # Architecture, VPS, handoff docs
├── pr/                         # PR docs (doc-first workflow)
└── supabase/migrations/        # Analytics schema
```

---

## 5. Production vs Engine (Important)

### What runs in production today

| Component | File | systemd service |
|-----------|------|-----------------|
| Voice agent | `agent.py` | `restaurant-agent` |
| Web tokens | `token_server.py` | `restaurant-token` |

Dispatch name everywhere: **`restaurant-agent`**

### Engine rebuild (PR #95) — merged but not switched on

The `restaurant/engine/` package is a **future architecture**:

```
transcript → [Extractor LLM] → Proposal → [OrderEngine code] → Actions → [Renderer] → TTS
```

- **Goal:** Code owns 100% of cart state; LLM only understands language
- **Fixes:** Fish ambiguity, invented quantities, additive cart bugs
- **Status:** Stages 1–4 done; Stage 5 (shadow mode → pilot) pending
- **Entry:** `restaurant/engine/live.py` registers as `engine-restaurant-agent` (port 8082)
- **Not wired** to Twilio SIP or web dispatch — safe to deploy `main` without switching

See [`restaurant/engine/README.md`](../restaurant/engine/README.md) for full engine design.

---

## 6. Core Modules — How They Work Together

### `agent.py` — orchestrator

Central LiveKit agent. On each user turn:

1. **Fast paths (code-owned, before LLM):**
   - `_try_auto_add` — high-confidence menu match → add without LLM
   - `_try_menu_browse` — category queries ("mithai kya hai?")
   - `_try_answer_item_availability` — "do you have kheer?"
   - `_try_capture_customer_info` — name/phone during checkout
   - `_try_run_checkout_ladder` — allergies, pickup, readback
   - STT noise / echo / background filters

2. **LLM turn:** injects `[TURN GUIDANCE]` from `order_flow.py`, then LLM may call tools

3. **Function tools:**
   - `add_to_order`, `remove_from_order`, `update_item_quantity`
   - `set_order_type`, `set_customer_info`, `set_delivery_address`
   - `get_order_summary`, `place_order`
   - `check_menu_item`, `search_menu_items`
   - `transfer_to_human`, `check_table_availability`, `book_reservation`

### `restaurant/order_flow.py` — phase machine

Tracks checkout phase and builds per-turn guidance for the LLM:

```
BROWSING → AWAITING_MORE → SPECIAL_INSTRUCTIONS → ORDER_TYPE → READBACK
  → CUSTOMER_NAME → CUSTOMER_PHONE → READY_TO_PLACE
```

`outstanding_requirements()` lists what's still missing (soft guide for LLM).

### `restaurant/menu_provider.py` — menu facade

When `USE_CLOVER_MENU=1`:

- Loads `data/menu_cache_bizbull.json`
- Merges `data/clover_voice_labels.json` for `voice_line` / `speech_mode`
- Routes lookups through `restaurant/clover/match.py` (confidence scoring)

### `restaurant/orders.py` — OrderCart

In-memory cart per call. `ready_to_place()` is the hard gate before `place_order()`.

### `restaurant/clover/order_submit.py` — POS submit

When `CLOVER_SUBMIT_ORDERS=1`, builds Clover atomic order from cart lines.

---

## 7. Phone Order Flow (Production)

```
Greet (OPENING_GREETING)
  → Browse / add items ("Anything else?")
  → Allergies / special instructions
  → Pickup or delivery
  → Read order back + confirm ("All good?")
  → Customer name
  → Phone number (spoken back in English digits)
  → place_order() → Clover submit (if enabled) → goodbye → hang up
```

**Rules enforced in code + guidance:**

- No price on phone unless customer asks
- Auto-add only above confidence thresholds
- Ambiguous dishes should disambiguate (fish curry vs fish pakora)
- Quantity corrections use `update_item_quantity`, not `add_to_order`

---

## 8. Environment Variables

> **Security:** Store all secrets in `/opt/livekit-sarvam/.env` on the VPS only.  
> **Never commit `.env` to git or paste secrets in Notion/Slack.**  
> Use a password manager or secure channel for onboarding new developers.  
> Template: [`.env.example`](../.env.example)

### 8.1 Required — core services

| Variable | Purpose | Example / format |
|----------|---------|------------------|
| `LIVEKIT_URL` | LiveKit Cloud WebSocket URL | `wss://bizbull-restaurant-cyeyyw0l.livekit.cloud` |
| `LIVEKIT_API_KEY` | LiveKit API key | from LiveKit dashboard |
| `LIVEKIT_API_SECRET` | LiveKit API secret | from LiveKit dashboard |
| `SONIOX_API_KEY` | Soniox STT + TTS | from Soniox console |
| `OPENAI_API_KEY` | GPT-4o-mini | from OpenAI dashboard |
| `TWILIO_ACCOUNT_SID` | Twilio account | `AC…` |
| `TWILIO_AUTH_TOKEN` | Twilio auth | from Twilio dashboard |

### 8.2 Clover POS

| Variable | Purpose | Notes |
|----------|---------|-------|
| `CLOVER_BASE_URL` | API base | `https://apisandbox.dev.clover.com` (sandbox) |
| `CLOVER_MID` | Merchant ID | e.g. `D7Q5A5QWRF9R1` |
| `CLOVER_API_TOKEN` | API token | secret — Clover dashboard |
| `CLOVER_ORDER_TYPE_PICKUP_ID` | Clover order type ID | from `clover_sandbox_probe.py` |
| `CLOVER_ORDER_TYPE_DELIVERY_ID` | Clover order type ID | from `clover_sandbox_probe.py` |
| `USE_CLOVER_MENU` | Load Clover menu cache | `1` on VPS |
| `MENU_CACHE_PATH` | Menu JSON path | `data/menu_cache_bizbull.json` |
| `VOICE_LABELS_PATH` | Voice labels JSON | `data/clover_voice_labels.json` |
| `TENANT_DB_PATH` | Tenant SQLite DB | `data/tenants.db` |
| `CLOVER_SUBMIT_ORDERS` | Submit orders to Clover on place | `0` or `1` |
| `CLOVER_PRINT_ORDERS` | Print order on Clover device | `0` or `1` |

### 8.3 Analytics (Supabase)

| Variable | Purpose | Notes |
|----------|---------|-------|
| `SUPABASE_URL` | Supabase project URL | `https://lzlwivsntqkpxfwjktid.supabase.co` |
| `SUPABASE_SERVICE_ROLE_KEY` | Server-side write key | secret — Supabase dashboard |
| `SESSION_ANALYTICS_ENABLED` | Enable call recording | `1` |
| `SESSION_FALLBACK_DIR` | Local JSONL fallback | `data/sessions` |

**Admin dashboard** (`admin/.env`, separate file):

```
VITE_SUPABASE_URL=https://lzlwivsntqkpxfwjktid.supabase.co
VITE_SUPABASE_ANON_KEY=<anon key from Supabase dashboard>
```

### 8.4 Voice / UX tuning

| Variable | Purpose | Typical prod |
|----------|---------|--------------|
| `FILLERS_ENABLED` | Short filler phrases before LLM | `1` |
| `PHONE_AMBIENT_VOLUME` | Phone background ambience volume | `0.5` |
| `AUTO_HANGUP_AFTER_ORDER` | Hang up after successful order | `1` |
| `AUTO_HANGUP_GRACE_SEC` | Delay before hang-up | `1.0` |

### 8.5 Optional — latency / phone hardening

| Variable | Default | Purpose |
|----------|---------|---------|
| `PHONE_ENDPOINTING_MAX` | `0.5` | Max silence before end-of-utterance |
| `PHONE_ENDPOINTING_MIN` | `0.2` | Min silence threshold |
| `PHONE_PREEMPTIVE_GENERATION` | `true` | Start LLM before utterance fully ends |
| `PHONE_PREEMPTIVE_TTS` | `true` | Start TTS early |
| `PHONE_BVC_ENABLED` | `1` | Krisp background voice cancellation |
| `PHONE_BACKGROUND_FILTER_ENABLED` | `1` | Filter background chatter from STT |
| `PHONE_INTERRUPTION_MIN_WORDS` | `2` | Words required to interrupt Sierra |
| `WEB_AMBIENT_ENABLED` | `1` | Web background audio |
| `WEB_AMBIENT_VOLUME` | `0.2` | Web ambience volume |
| `PHONE_AMBIENT_ENABLED` | `1` | Phone background audio |

### 8.6 Optional — menu matching

| Variable | Default | Purpose |
|----------|---------|---------|
| `MENU_MATCH_LEGACY` | `0` | `1` = old substring matcher (rollback) |
| `MENU_MATCH_MIN_CONF` | `0.55` | Minimum match confidence |
| `AUTO_ADD_MIN_CONFIDENCE` | `0.8` | Auto-add single item threshold |
| `AUTO_ADD_MULTI_MIN_CONFIDENCE` | `0.72` | Auto-add multi-item threshold |

### 8.7 View env on VPS

```bash
ssh root@89.117.18.192
cat /opt/livekit-sarvam/.env                    # full file (secrets!)
grep -E '^[A-Z_]+=' /opt/livekit-sarvam/.env | cut -d= -f1 | sort   # keys only
systemctl show restaurant-agent -p Environment  # what systemd loaded
```

---

## 9. VPS Deployment

### Server

| Property | Value |
|----------|-------|
| IP | `89.117.18.192` |
| OS | Ubuntu 22.04 |
| Repo path | `/opt/livekit-sarvam` |
| Python manager | `uv` at `/root/.local/bin/uv` |
| Region | US West (Seattle) — low latency for Canada callers |

### Deploy (standard)

```bash
ssh root@89.117.18.192
cd /opt/livekit-sarvam
bash scripts/vps_deploy.sh
```

What `vps_deploy.sh` does:

1. `git fetch` + `git reset --hard origin/main`
2. `uv sync` (install Python deps)
3. `rebuild_voice_labels.py` + `clover_sync_menu.py`
4. `npm run build` for `web/` and `admin/`
5. `systemctl restart restaurant-agent restaurant-token`

### Manual deploy

```bash
cd /opt/livekit-sarvam
git fetch origin main
git checkout main
git reset --hard origin/main
uv sync
systemctl restart restaurant-agent restaurant-token
systemctl is-active restaurant-agent restaurant-token
```

### Rollback

```bash
cd /opt/livekit-sarvam
git log --oneline -10                    # find good commit
git reset --hard <commit-sha>            # e.g. 698a3ca = pre-engine
uv sync
systemctl restart restaurant-agent restaurant-token
```

### Service management

```bash
systemctl status restaurant-agent restaurant-token
systemctl restart restaurant-agent
journalctl -u restaurant-agent -f
journalctl -u restaurant-agent -f | grep -E 'USER:|SIERRA:|ORDER_PLACED|AUTO_ADD|LATENCY'
```

---

## 10. Local Development

> **Full local runbook (3 terminals, Windows notes, VPS env capture):** [`LOCAL_DEV.md`](LOCAL_DEV.md)

### Prerequisites

- Python 3.10+
- [uv](https://github.com/astral-sh/uv)
- Node.js 18+ (for web/admin)
- API keys in `.env` (from VPS or `.env.example`)

### Setup

```bash
git clone https://github.com/Shivek-cmd/livekitcloud-soniox.git
cd livekitcloud-soniox
cp .env.example .env          # or copy secrets from VPS — see LOCAL_DEV.md
uv sync
```

### Three processes (typical local stack)

| Process | Command |
|---------|---------|
| Token server `:8001` | `uv run python -m uvicorn token_server:app --host 0.0.0.0 --port 8001 --reload` |
| Web UI | `cd web && npm run dev` → http://localhost:5173 |
| Agent | `uv run python agent.py dev` |

On Windows, prefer `python -m uvicorn` (not `uv run uvicorn`) — see [`LOCAL_DEV.md`](LOCAL_DEV.md).

### Run tests

```bash
PYTHONPATH=. uv run pytest tests/ -q
```

### Sync menu from Clover

```bash
USE_CLOVER_MENU=1 uv run python scripts/clover_sync_menu.py
uv run python scripts/rebuild_voice_labels.py
```

---

## 11. SIP & Telephony Setup

Configured via scripts (run with LiveKit credentials in `.env`):

```bash
uv run python scripts/setup_twilio_sip.py --apply   # Twilio → LiveKit Cloud
KRISP_ENABLED=1 uv run python scripts/setup_sip.py  # Cloud trunk + dispatch rule
```

| Item | Value |
|------|-------|
| Phone number | `+15878175156` |
| LiveKit SIP URI | `sip:5qg9858y0ak.sip.livekit.cloud` |
| Dispatch agent | `restaurant-agent` |
| Room prefix | `phone-` (per caller) |

---

## 12. Data Files

| File | Purpose | Regenerated by |
|------|---------|----------------|
| `data/menu_cache_bizbull.json` | Clover menu items, prices, modifiers | `scripts/clover_sync_menu.py` |
| `data/clover_voice_labels.json` | TTS voice lines, aliases, speech_mode | `scripts/rebuild_voice_labels.py` |
| `data/tenants.db` | Clover credentials per tenant | `scripts/clover_init_tenant.py` |
| `data/sessions/*.jsonl` | Analytics fallback when Supabase unavailable | Agent at runtime |

---

## 13. Testing Strategy

| Area | Test files |
|------|------------|
| Order engine (new) | `test_engine.py`, `test_engine_resolver.py`, `test_engine_renderer.py` |
| Menu matching | `test_menu_match.py` |
| Order flow | `test_order_flow.py` |
| Conversation / intents | `test_conversation.py` |
| Customer info | `test_customer_info.py` |
| Clover submit | `test_clover_order_submit.py` |
| Voice labels / speech | `test_voice_labels.py`, `test_speech_policy.py` |

```bash
PYTHONPATH=. uv run pytest tests/test_engine.py tests/test_order_flow.py -v
```

---

## 14. PR Workflow (Mandatory)

All changes follow **doc-first** workflow ([`pr/pr_rules.md`](../pr/pr_rules.md)):

1. Create `pr/pr_NNN_description.md` **before** coding
2. Branch name = doc filename (without `.md`)
3. Code on branch only — never commit directly to `main`
4. Open GitHub PR → merge to `main`
5. Deploy from `main` on VPS

Index: [`pr/README.md`](../pr/README.md)

---

## 15. Observability

### Live call logs

```bash
journalctl -u restaurant-agent -f | grep -E 'USER:|SIERRA:|TURN_GUIDANCE|AUTO_ADD|ORDER_PLACED|CAPTURE|MENU_MATCH'
```

### Latency

```bash
journalctl -u restaurant-agent -f | grep LATENCY
# Example: eou_delay=0.56s | user_stop→speaking=3909ms | llm_ttft=1.62s
```

### Admin dashboard

- URL: `https://admin.bizbull.ai`
- Login: `sandeeptaur@gmail.com` (password from project owner)
- Shows call list, **full transcripts**, order outcome, latency metrics
- **Call detail** page is the primary QA tool — compare caller STT vs Sierra replies turn-by-turn
- Backed by Supabase project `sierra-bizbull` (ca-central-1)

---

## 16. Key URLs & Credentials Map

| Service | Dashboard / URL | Env vars |
|---------|-----------------|----------|
| LiveKit Cloud | cloud.livekit.io → Bizbull Restaurant | `LIVEKIT_*` |
| Soniox | console.soniox.com | `SONIOX_API_KEY` |
| OpenAI | platform.openai.com | `OPENAI_API_KEY` |
| Twilio | console.twilio.com | `TWILIO_*` |
| Clover | sandbox/dev dashboard | `CLOVER_*` |
| Supabase | supabase.com → sierra-bizbull | `SUPABASE_*` |

---

## 17. Developer Onboarding Checklist

- [ ] Get `.env` from team lead via secure channel (1Password / vault — not Notion)
- [ ] Read [`HANDOFF.md`](HANDOFF.md) and [`plan/02-architecture.md`](plan/02-architecture.md)
- [ ] Clone repo, `uv sync`, run tests
- [ ] Read `agent.py` `on_user_turn_completed` and `order_flow.py`
- [ ] Understand `USE_CLOVER_MENU=1` + menu cache + voice labels
- [ ] SSH access to VPS (`89.117.18.192`)
- [ ] Test web order at **`https://voice.bizbull.ai`** (Order with Sierra tab)
- [ ] Log in to **`https://admin.bizbull.ai`** and open a recent call transcript
- [ ] Read [`pr/pr_rules.md`](../pr/pr_rules.md) before any code change
- [ ] Know rollback: `git reset --hard <sha>` + restart services

---

## 18. Known Architecture Notes

1. **Three authorities problem (old flow):** `order_flow.py`, `agent.py` ladder, and `conversation.py` intents can disagree — source of many live bugs. Engine rebuild (`restaurant/engine/`) is the long-term fix.

2. **`add_to_order` is additive:** repeating the same dish doubles quantity. Corrections must use `update_item_quantity`.

3. **Engine is on `main` but not live:** deploying `main` does **not** switch to the engine. Production still uses `agent.py`.

4. **HANDOFF.md may be stale:** verify with `git log -1 --oneline` on VPS vs repo.

5. **Never deploy feature branches on VPS** — only `main` (or explicit rollback SHA).

---

## 19. Production `.env` Template

Copy to `/opt/livekit-sarvam/.env` and fill secrets from each service dashboard:

```bash
# LiveKit Cloud
LIVEKIT_URL=wss://bizbull-restaurant-cyeyyw0l.livekit.cloud
LIVEKIT_API_KEY=<from LiveKit dashboard>
LIVEKIT_API_SECRET=<from LiveKit dashboard>

# Soniox STT + TTS
SONIOX_API_KEY=<from Soniox console>

# OpenAI LLM
OPENAI_API_KEY=<from OpenAI dashboard>

# Twilio telephony
TWILIO_ACCOUNT_SID=<from Twilio>
TWILIO_AUTH_TOKEN=<from Twilio>

# Clover POS (sandbox)
CLOVER_BASE_URL=https://apisandbox.dev.clover.com
CLOVER_MID=D7Q5A5QWRF9R1
CLOVER_API_TOKEN=<from Clover dashboard>
CLOVER_ORDER_TYPE_PICKUP_ID=J90MCHQDCHTN8
CLOVER_ORDER_TYPE_DELIVERY_ID=Y5XYT9VM3DJB4

# Menu
USE_CLOVER_MENU=1
MENU_CACHE_PATH=data/menu_cache_bizbull.json
VOICE_LABELS_PATH=data/clover_voice_labels.json
TENANT_DB_PATH=data/tenants.db

# Order submit
CLOVER_SUBMIT_ORDERS=1
CLOVER_PRINT_ORDERS=0

# Analytics
SUPABASE_URL=https://lzlwivsntqkpxfwjktid.supabase.co
SUPABASE_SERVICE_ROLE_KEY=<from Supabase dashboard>
SESSION_ANALYTICS_ENABLED=1
SESSION_FALLBACK_DIR=data/sessions

# UX
FILLERS_ENABLED=1
PHONE_AMBIENT_VOLUME=0.5
AUTO_HANGUP_AFTER_ORDER=1
```
