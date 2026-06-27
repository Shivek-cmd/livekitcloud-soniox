# VPS Configuration Reference

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
Built in `restaurant/voice_stack.py`. All US/EU/JP-hosted (low latency for Canada callers).

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

Manual equivalent:

```bash
cd /opt/livekit-sarvam
git fetch origin main && git reset --hard origin/main
/root/.local/bin/uv sync
PYTHONPATH=/opt/livekit-sarvam /root/.local/bin/uv run python scripts/rebuild_voice_labels.py
PYTHONPATH=/opt/livekit-sarvam /root/.local/bin/uv run python scripts/clover_sync_menu.py
systemctl restart restaurant-agent restaurant-token
```

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
| Caddy (shared reverse proxy) | `caddy.service` — also serves `sarvam.bizbull.ai` (our web app) |

> Our web app is served by the shared Caddy at `sarvam.bizbull.ai` (static `web/dist` + `/token` →
> port 8001). The domain name still says "sarvam" for historical reasons; the backend is now Soniox.
