# External Integrations

**Analysis Date:** 2026-07-14

## APIs & External Services

**Real-time Communication:**
- LiveKit - WebRTC infrastructure and agent orchestration
  - SDK: `livekit-agents`, `livekit-client` (web)
  - Auth: `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`, `LIVEKIT_URL`
  - Used in: Agent worker dispatch (`token_server.py`), room management (`restaurant/agent/worker.py`)

**Speech & Voice:**
- Soniox - Speech-to-text (STT) and text-to-speech (TTS)
  - SDK: `livekit-plugins-soniox`
  - Auth: Embedded in LiveKit plugins (configured via `LIVEKIT_API_KEY`)
  - Models: `stt-rt-v5` (STT), `tts-rt-v1` (TTS), voice "Maya", language "pa" (Punjabi)
  - Features: Automatic Punjabi/English/Hindi code-mixing (`restaurant/voice_stack.py`)
  - Tuning: `SONIOX_MAX_ENDPOINT_DELAY_MS`, `SONIOX_ENDPOINT_SENSITIVITY`, `SONIOX_ENDPOINT_LATENCY_ADJUSTMENT_LEVEL`

**Language Model:**
- OpenAI - Chat completions for restaurant agent
  - SDK: `livekit-plugins-openai`
  - Auth: `OPENAI_API_KEY`
  - Model: `gpt-4o-mini` (cost-optimized, supports prompt caching)
  - Used in: Agent LLM core (`restaurant/agent/core.py`)
  - Warmup: Pre-cached prompt on session start (`restaurant/llm_warmup.py`)

**POS & Order Management:**
- Clover - Point-of-sale system for menu and order submission
  - Client: Custom REST client via `urllib` (`restaurant/clover/client.py`)
  - Auth: `CLOVER_BASE_URL`, `CLOVER_MID` (merchant ID), `CLOVER_API_TOKEN`
  - Features:
    - Menu fetch and cache (`restaurant/clover/menu.py`)
    - Order submission (`restaurant/clover/order_submit.py`)
    - Item ID matching and spice aliases
    - Optional printing to Clover terminals
  - Toggle: `USE_CLOVER_MENU`, `CLOVER_SUBMIT_ORDERS`, `CLOVER_PRINT_ORDERS`
  - Fallback: Static menu in `restaurant/menu.py` if Clover unavailable

**Telephony:**
- Twilio - SIP trunk for phone calls
  - SDK: `twilio`
  - Auth: `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER`
  - Setup: `scripts/setup_twilio_sip.py` configures SIP trunk and webhook
  - Used in: Call routing from phone to LiveKit room

**Processing & Enhancement:**
- LiveKit Noise Cancellation Plugin - Audio filtering for phone calls
  - SDK: `livekit-plugins-noise-cancellation` >=0.2.5
  - Used in: Session audio config (`restaurant/session_config.py`)

## Data Storage

**Primary Database:**
- Supabase (PostgreSQL-hosted)
  - Connection: `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`
  - Tables:
    - `call_sessions` - Session metadata (room, channel, participant, timestamps)
    - `call_turns` - Individual conversation turns (STT, intent, phase, cart state)
    - `orders` - Submitted orders
    - `call_events` - Session events (metadata, errors, analytics)
  - Client: `supabase>=2.0` Python SDK in backend, `@supabase/supabase-js` in admin frontend
  - Auth (admin): `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY` (public, for admin dashboard login)

**Fallback Storage:**
- Local filesystem - JSON files in `data/sessions/` if Supabase unavailable
  - Path: Configured via `SESSION_FALLBACK_DIR` env var
  - Auto-created during analytics persist (`restaurant/analytics/analytics_store.py`)

**File Storage:**
- Local filesystem only - No cloud storage integration
  - Menu data: `data/` directory (Clover cache, static menu)
  - Session recordings: Optional local recording (configured in session)

**Caching:**
- In-memory Clover menu cache - Refreshed periodically (`restaurant/clover/menu.py`)
- No Redis or other external cache service

## Authentication & Identity

**Token Generation:**
- LiveKit access tokens - Issued by token server (`token_server.py`)
  - Endpoint: `/token` - Issues JWT for web clients
  - Grants: `room_join` (video), `room_name` from request or random UUID
  - Identity: `user-` or `sip_` prefixed participant ID

**Service Authentication:**
- LiveKit: API key + secret for server-side dispatch
- Clover: Bearer token in HTTP `Authorization` header
- Supabase: Service role key (backend) + anon key (frontend/admin)
- OpenAI: API key (via LiveKit plugin)
- Soniox: Embedded in LiveKit plugin auth
- Twilio: Account SID + auth token

**Admin Dashboard Auth:**
- Supabase Auth (built-in) - Login page in `admin/src/pages/Login.tsx`
- Uses anon key for public auth endpoints

## Monitoring & Observability

**Error Tracking:**
- None configured - Errors logged to stdout/stderr

**Logs:**
- Python logging to console - Configured in `restaurant/agent/worker.py`
  - Format: `%(asctime)s %(name)s %(levelname)s %(message)s`
  - Loggers: `restaurant-agent`, `analytics-store`, `clover-order-submit`, etc.

**Metrics & Analytics:**
- Turn latency tracking - `restaurant/analytics/turn_latency.py`
  - Captures: EOU (end-of-utterance), LLM, TTS times per turn
  - Persisted to Supabase `call_turns.latency` column
- Session recording - `restaurant/analytics/session_recorder.py`
  - Metadata: git SHA, room, channel (phone/web), timestamps
- Analytics storage - Async persist to Supabase or local JSON

**Tracing:**
- No distributed tracing configured

## CI/CD & Deployment

**Hosting:**
- Docker-based deployment
  - Image: `Dockerfile` in `deploy/` (not shown, inferred from systemd service)
  - Runtime: Systemd service `deploy/restaurant-agent.service`
  - Proxy: Caddy reverse proxy for web/token routing

**CI Pipeline:**
- Not configured in this repository - Assumed managed externally (GitHub Actions, GitLab CI, etc.)

**Deployment Artifacts:**
- GitHub repo pushes trigger (inferred from PR structure)
- Systemd manages agent process lifecycle

## Environment Configuration

**Required Environment Variables:**

Backend (agent):
- `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`, `LIVEKIT_URL` - LiveKit connectivity
- `CLOVER_BASE_URL`, `CLOVER_MID`, `CLOVER_API_TOKEN` - POS (if Clover menu/orders enabled)
- `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` - Analytics (optional, with fallback)
- `OPENAI_API_KEY` - GPT-4o-mini (not explicit but required by plugin)
- `AGENT_NAME` - Identifies agent for dispatch (default: `restaurant-agent`)

Token Server:
- `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`, `LIVEKIT_URL` - Same as agent
- CORS: Configured to allow all origins (`*`)

Web Frontend (Vite):
- None required - All config client-side (proxied via Caddy)

Admin Dashboard (Vite):
- `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY` - Supabase connection for auth and queries

**Optional Configuration:**
- `SESSION_ANALYTICS_ENABLED` - Toggle analytics (default: enabled)
- `SESSION_FALLBACK_DIR` - Local session JSON storage (default: `data/sessions`)
- `SONIOX_*` - STT tuning (max endpoint delay, sensitivity, latency adjustment)
- `USE_CLOVER_MENU`, `CLOVER_SUBMIT_ORDERS`, `CLOVER_PRINT_ORDERS` - Clover toggles
- `DEPLOY_GIT_SHA` - Git commit SHA recorded in session metadata

**Secrets Location:**
- `.env` file (development) - Not committed (in `.gitignore`)
- Docker environment or systemd override (production) - Managed externally
- `.env.example` provides template of required variables

## Webhooks & Callbacks

**Incoming:**
- Twilio SIP webhook - Inbound call routing to LiveKit (configured by `scripts/setup_twilio_sip.py`)

**Outgoing:**
- Order submission to Clover - HTTP POST to Clover create-order endpoint
- Analytics to Supabase - Async upsert to database tables via Supabase SDK
- No explicit webhooks to external services for events or notifications

## Data Flow

**Typical Call Session:**
1. Phone → Twilio SIP → LiveKit room (via SIP trunk)
2. Web browser → `/token` → LiveKit room
3. Agent connects, detects channel (phone vs web) → `restaurant/agent/worker.py`
4. Agent starts: Soniox STT + OpenAI LLM + Soniox TTS
5. Per turn: STT → LLM decision → TTS → cart state broadcast to web via data topic
6. Optional: Order submission → Clover API
7. Session end: Analytics upsert to Supabase, fallback to local JSON

---

*Integration audit: 2026-07-14*
