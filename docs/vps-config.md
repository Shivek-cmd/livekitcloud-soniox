# VPS Configuration Reference

> **Session state / what's merged / next steps:** see [`HANDOFF.md`](HANDOFF.md) (updated 2026-06-29).
>
> This VPS is **shared** with several unrelated projects. Only the **livekit-sarvam** project below is
> ours. Everything under "Other projects (DO NOT TOUCH)" belongs to other apps — never stop, edit, or
> remove those containers/services.

## Server Info

| Property | Value |
|---|---|
| Public IP | 89.117.18.192 |
| OS | Ubuntu 22.04 LTS |
| SSH | key-based (`~/.ssh/livekit_vps`) |
| Python | 3.10 |
| uv | `/root/.local/bin/uv` |
| Note | OS clock is set to Europe/Berlin, but the host is physically in **Seattle, US West** (Contabo). |

---

## Our Project — livekit-sarvam

Location: `/opt/livekit-sarvam/`

**Transport is LiveKit Cloud** (no self-hosted LiveKit server for this project). The agent runs on the
VPS and connects out to the Cloud project.

### LiveKit Cloud project
| Property | Value |
|---|---|
| Project name | Bizbull Restaurant |
| Project ID | `p_5qg9858y0ak` |
| WebSocket URL | `wss://bizbull-restaurant-cyeyyw0l.livekit.cloud` |
| SIP URI | `sip:5qg9858y0ak.sip.livekit.cloud` |
| API key / secret | in `/opt/livekit-sarvam/.env` and the Cloud dashboard (not committed) |

### Environment — `/opt/livekit-sarvam/.env`
Keys required (values live only on the VPS, never committed):
```
LIVEKIT_URL=wss://bizbull-restaurant-cyeyyw0l.livekit.cloud
LIVEKIT_API_KEY=<cloud api key>
LIVEKIT_API_SECRET=<cloud api secret>
SONIOX_API_KEY=<soniox key>
OPENAI_API_KEY=<openai key>
TWILIO_ACCOUNT_SID=<twilio sid>
TWILIO_AUTH_TOKEN=<twilio token>
```

### Voice stack
Soniox `stt-rt-v5` (STT) + OpenAI `gpt-4o-mini` (LLM) + Soniox `tts-rt-v1` voice `Maya` (TTS).
Built in `restaurant/voice_stack.py`. **Shared** phone/web endpointing in `restaurant/session_config.py` — both channels default **0.2–0.5s** max wait after caller stops speaking.
All US/EU/JP-hosted (low latency for Canada callers).

**Production commit (2026-06-28):** `0666017` — web W2 + shared latency + Mango Kulfi TTS fix.

### Phone tuning env vars (optional — defaults in `session_config.py`)

Add to `/opt/livekit-sarvam/.env` to override without code deploy:

```
USE_CLOVER_MENU=1
PHONE_ENDPOINTING_MAX=0.5          # phone + web — lower = faster reply, may cut off pauses
PHONE_ENDPOINTING_MIN=0.2          # phone + web
SONIOX_MAX_ENDPOINT_DELAY_MS=1000  # PR 064 — Soniox finalize delay after speech stops (500-3000)
#SONIOX_ENDPOINT_SENSITIVITY=0.3   # PR 066 — -1.0..1.0, default 0.3 (Soniox voice-AI rec); "none" = server default
#SONIOX_ENDPOINT_LATENCY_ADJUSTMENT_LEVEL=2  # PR 066 — 0-3, default 2; "none" = don't send (server default)
#VAD_ACTIVATION_THRESHOLD=0.6      # PR 066 — Silero VAD speech threshold; raise toward 0.7 if noise trips it
#VAD_MIN_SILENCE_SEC=0.25          # PR 066 — silence before VAD end-of-speech
#EOU_WATCHDOG_SEC=2.0              # PR 067 — force turn commit if no final transcript this long after speech ends; 0 disables
PHONE_PREEMPTIVE_GENERATION=true
PHONE_PREEMPTIVE_TTS=true
PHONE_GREETING_SETTLE_SEC=2.0
PHONE_AEC_WARMUP_SEC=1.0
PHONE_INTERRUPTION_MIN_WORDS=2     # phone only
```

Restart after change: `systemctl restart restaurant-agent`.

### GHL / n8n order sync (PR 071)

After successful `place_order`, Sierra POSTs a normalized envelope to self-hosted n8n
→ GHL contact upsert + confirm SMS. **Fail-open** (n8n down does not block the call).
**Live on VPS** with `N8N_SYNC_ENABLED=1`. G2b verified (opps + Option B SMS). Next: G3 — plan §9.

```
N8N_SYNC_ENABLED=1
N8N_WEBHOOK_ORDERS_URL=https://n8n.bizbull.ai/webhook/sierra-ghl-sync
#N8N_WEBHOOK_SECRET=optional-shared-secret
#N8N_WEBHOOK_TIMEOUT_SEC=3.0
```

Plan: `docs/plan/13-ghl-n8n-order-sync.md`. Workflow export: `n8n/`.

### Ambient audio (optional — PR 020 web, PR 022 phone)

Quiet background loop via LiveKit `BackgroundAudioPlayer`. Same `restaurant_ambience.mp3` on web and phone.

```
WEB_AMBIENT_ENABLED=1
WEB_AMBIENT_VOLUME=0.2
WEB_AMBIENT_FADE_IN=1.0

PHONE_AMBIENT_ENABLED=1
PHONE_AMBIENT_VOLUME=0.2
PHONE_AMBIENT_FADE_IN=1.0

# AMBIENT_AUDIO_PATH=/opt/livekit-sarvam/data/audio/restaurant_ambience.mp3
# WEB_AMBIENT_AUDIO_PATH=       # legacy alias for AMBIENT_AUDIO_PATH
# WEB_AMBIENT_THINKING=0        # web only
```

Drop `restaurant_ambience.mp3` in `/opt/livekit-sarvam/data/audio/` or set `AMBIENT_AUDIO_PATH`.
If no custom file exists, builtin office ambience is used for testing.
If phone echo worsens: `PHONE_AMBIENT_ENABLED=0` (web unchanged).

Logs: `journalctl -u restaurant-agent -f | grep -i ambient`

### Phone background speech (PR 023)

Krisp BVC voice isolation + stricter phone interruptions + transcript filter for background chatter.

```
PHONE_BVC_ENABLED=1                    # 0 = disable agent BVC (full revert of audio layer)
PHONE_BACKGROUND_FILTER_ENABLED=1      # 0 = disable transcript background filter
PHONE_INTERRUPTION_MIN_WORDS=2         # require 2+ words to barge-in (was 1)
PHONE_INTERRUPTION_MIN_DURATION=0.55
```

SIP trunk Krisp NC: `KRISP_ENABLED=1` when running `scripts/setup_sip.py` (default on).

Logs: `journalctl -u restaurant-agent -f | grep -iE 'background|BVC|Ignoring phone'`

### Sierra analytics — Supabase (PR 027)

Project **`sierra-bizbull`** · region **ca-central-1** · ref **`lzlwivsntqkpxfwjktid`**

```
SUPABASE_URL=https://lzlwivsntqkpxfwjktid.supabase.co
SUPABASE_SERVICE_ROLE_KEY=<from Supabase dashboard — never commit>
SESSION_ANALYTICS_ENABLED=1
SESSION_FALLBACK_DIR=data/sessions
```

After first deploy: create Auth user in Supabase, then `insert into admin_users (email) values ('you@example.com');`

Logs: `journalctl -u restaurant-agent -f | grep -iE 'analytics|Session analytics'`

### Admin dashboard — `admin.bizbull.ai` (PR 027)

Build: `cd /opt/livekit-sarvam/admin && npm ci && npm run build`

Env file **`admin/.env`** (not committed):
```
VITE_SUPABASE_URL=https://lzlwivsntqkpxfwjktid.supabase.co
VITE_SUPABASE_ANON_KEY=<anon key from Supabase dashboard>
```

Caddy block (add alongside voice.bizbull.ai):
```
admin.bizbull.ai {
  root * /opt/livekit-sarvam/admin/dist
  file_server
  try_files {path} /index.html
}
```

**Quick revert if analytics breaks calls:** set `SESSION_ANALYTICS_ENABLED=0`, restart agent (voice unchanged).

**Quick revert if phone tuning breaks calls:** set `PHONE_BVC_ENABLED=0` and `PHONE_BACKGROUND_FILTER_ENABLED=0`, restart agent.

### Latency / conversation logs

```bash
journalctl -u restaurant-agent -f | grep -E 'USER:|SIERRA:|LATENCY|Ignoring|EOU metrics'
```

Example `LATENCY` line: `eou_delay=0.56s | user_stop→speaking=3909ms | llm_ttft=1.62s`

---

## Systemd Services (ours)

### `restaurant-agent.service`
The agent worker, connected to LiveKit Cloud.
```
File:    /etc/systemd/system/restaurant-agent.service
Source:  /opt/livekit-sarvam/deploy/restaurant-agent.service
Exec:    /root/.local/bin/uv run python agent.py start
Dir:     /opt/livekit-sarvam
Env:     EnvironmentFile=/opt/livekit-sarvam/.env
Restart: always
```

### `restaurant-token.service`
FastAPI token server for the web channel (port 8001).
```
Exec:    uvicorn token_server:app --host 0.0.0.0 --port 8001
```

### Common commands
```bash
systemctl status restaurant-agent restaurant-token
systemctl restart restaurant-agent restaurant-token
journalctl -u restaurant-agent -f
```

---

## SIP Configuration (LiveKit Cloud)

Created/updated by `scripts/setup_sip.py` against the **Cloud** credentials:
- **Inbound trunk** bound to `+15878175156`, `krisp_enabled=True` (trunk-level noise cancellation).
- **Dispatch rule**: per-caller room (`phone-` prefix) + `RoomAgentDispatch(agent_name="restaurant-agent")`.

Twilio origination must point at Cloud (`sip:5qg9858y0ak.sip.livekit.cloud`), not the old self-hosted `lk.bizbull.ai:5060`. Use `scripts/setup_twilio_sip.py --apply` to fix.

```bash
uv run python scripts/setup_twilio_sip.py --apply   # Twilio → LiveKit Cloud
KRISP_ENABLED=1 uv run python scripts/setup_sip.py  # Cloud trunk + dispatch

# Outbound test call
LIVEKIT_SIP_URI='sip:+15878175156@5qg9858y0ak.sip.livekit.cloud' \
  uv run python scripts/test_call.py +91XXXXXXXXXX
```

---

## Deploy after code changes

Git remote on VPS uses **SSH** (`git@github.com:Shivek-cmd/livekitcloud-soniox.git`). First-time setup:

```bash
bash scripts/setup_vps_git.sh   # prints deploy key if needed; tests fetch
```

Deploy latest `main`:

```bash
bash scripts/vps_deploy.sh
```

`vps_deploy.sh` also runs `npm install && npm run build` in `web/` (serves `web/dist` via Caddy).

### Caddy — `voice.bizbull.ai`

Our web block (shared Caddy on VPS):

```
voice.bizbull.ai {
  handle /token* { reverse_proxy localhost:8001 }
  handle /menu*  { reverse_proxy localhost:8001 }
  handle /health { reverse_proxy localhost:8001 }
  handle {
    root * /opt/livekit-sarvam/web/dist
    file_server
    try_files {path} /index.html
  }
}
```

> **`sarvam.bizbull.ai` retired** (PR 009). Use **`voice.bizbull.ai`** only.

Manual equivalent:

```bash
cd /opt/livekit-sarvam
git fetch origin main && git reset --hard origin/main
/root/.local/bin/uv sync
PYTHONPATH=/opt/livekit-sarvam /root/.local/bin/uv run python scripts/rebuild_voice_labels.py
PYTHONPATH=/opt/livekit-sarvam /root/.local/bin/uv run python scripts/clover_sync_menu.py
(cd /opt/livekit-sarvam/web && npm install && npm run build)
systemctl restart restaurant-agent restaurant-token
```

> **VPS tip:** Do not run two `npm` builds at once (e.g. deploy + worktree validation) — small box OOMs and SSH hangs.

---

## Key packages

| Package | Notes |
|---|---|
| livekit-agents | 1.6.x |
| livekit-plugins-soniox | STT + TTS |
| livekit-plugins-openai | GPT LLM |
| livekit-api / livekit | Cloud API + rtc |
| fastapi / uvicorn | token server |
| twilio | test-call script |

> **Removed:** `livekit-plugins-sarvam` and `SARVAM_API_KEY` — Sarvam is no longer used.

---

## Other projects on this VPS (DO NOT TOUCH)

These belong to other apps. Never modify them.

| Project | Containers / services |
|---|---|
| Self-hosted LiveKit (legacy/other) | `livekit-livekit-1`, `livekit-sip-1`, `redis-lk` |
| Soniox voice project | `livekit-soniox-agent-1`, `livekit-soniox-web-1`, `livekit-soniox-api-1`, `livekit-soniox-livekit-1` |
| Soniox app | `soniox-frontend-1`, `soniox-twilio-bridge-1`, `soniox-voice-server-1`, `soniox-store-api-1`, `soniox-caddy-1` |
| POS integration | `pos_integration_app-app-1` (`integration.bizbull.ai`) |
| Order app | `order.bizbull.ai` |
| Caddy (shared reverse proxy) | `caddy.service` — serves **`voice.bizbull.ai`** (static `web/dist` + `/token`, `/menu` → port 8001) |

> Our web app is at **`https://voice.bizbull.ai`**. Backend is Soniox + LiveKit Cloud (not Sarvam).
