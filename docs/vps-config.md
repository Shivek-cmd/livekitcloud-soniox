# VPS Configuration Reference

## Server Info

| Property | Value |
|---|---|
| Hostname | vmi3273803 |
| OS | Ubuntu 22.04.5 LTS |
| Kernel | 5.15.0-181-generic |
| Public IP | 89.117.18.192 |
| CPU | 4 vCPU |
| RAM | 7.8 GB |
| Disk | 146 GB total, ~81 GB free |
| Swap | None |

---

## Pre-installed Software

| Software | Version | Notes |
|---|---|---|
| Python | 3.10.12 | System python3 |
| Docker | 29.6.0 | Running |
| Docker Compose | v5.1.4 | Plugin (use `docker compose`, not `docker-compose`) |
| Git | 2.34.1 | |
| Caddy | v2.11.4 | Running as systemd service |
| Node.js | v20.20.2 | |
| Redis | 7-alpine | Running as `redis-lk` Docker container, port 6379 |
| Apache2 | - | Running on port 8090 |
| MongoDB | - | Running on 127.0.0.1:27017 |
| MySQL | - | Running on 127.0.0.1:3306 |
| uv | 0.11.24 | Installed at `/root/.local/bin/uv` |

---

## Existing Projects on This VPS (DO NOT TOUCH)

### 1. LiveKit Server — `lk.bizbull.ai`
- **Folder**: `/opt/livekit/`
- **Container**: `livekit-livekit-1` (image: `livekit/livekit-server:latest`)
- **Config**: `/opt/livekit/infra/livekit.yaml`
- **Port**: 7880 (host network)
- **API Key**: `devkey`
- **API Secret**: `7fb987483e9c463c7777ea7e9a97e4bde86bcaa5`
- **Redis**: `localhost:6379`
- **RTC ports**: 10000–10100 UDP
- **Node IP**: 89.117.18.192

### 2. LiveKit SIP Service
- **Container**: `livekit-sip-1` (image: `livekit/sip:latest`)
- **Config**: `/opt/livekit/infra/sip.yaml`
- **SIP Port**: 5060 (UDP + TCP, host network)
- **RTP Ports**: 20000–30000
- **Connects to**: `ws://localhost:7880`
- **API Key/Secret**: same as LiveKit above

### 3. Soniox Voice Project
- **Containers**: `livekit-soniox-agent-1`, `livekit-soniox-web-1`, `livekit-soniox-api-1`, `livekit-soniox-livekit-1`
- **Note**: `livekit-soniox-livekit-1` is in Restarting state (unhealthy) — separate from main livekit

### 4. Soniox App
- **Containers**: `soniox-frontend-1`, `soniox-twilio-bridge-1`, `soniox-voice-server-1`, `soniox-store-api-1`, `soniox-caddy-1`
- **Ports**: 8080→80, 8443→443 (via soniox-caddy)

### 5. POS Integration App
- **Folder**: `/opt/POS_INTEGRATION_APP/`
- **Container**: `pos_integration_app-app-1`
- **Port**: 127.0.0.1:3001 (internal only)
- **Domain**: `integration.bizbull.ai`

### 6. Order App
- **Domain**: `order.bizbull.ai`
- **API**: port 8000
- **Web**: port 3000

---

## Caddy Config — `/etc/caddy/Caddyfile`

```
{ email admin@bizbull.ai }

lk.bizbull.ai          → localhost:7880          (LiveKit server)
sarvam.bizbull.ai      → localhost:8001 (/token) + /opt/livekit-sarvam/web/dist (static)
order.bizbull.ai       → localhost:3000/8000      (restaurant order app)
integration.bizbull.ai → localhost:3001           (POS integration)
voice.bizbull.ai       → localhost:8090           (Apache)
getsetvisa.com         → localhost:8090           (Apache)
```

The `sarvam.bizbull.ai` block routes `/token` and `/token/*` to port 8001 (token server),
everything else is served as static files from `/opt/livekit-sarvam/web/dist`.

---

## Ports In Use

| Port | Protocol | Used By |
|---|---|---|
| 22 | TCP | SSH |
| 80 | TCP | Caddy (HTTP redirect) |
| 443 | TCP/UDP | Caddy (HTTPS + TURN) |
| 3000 | TCP | Order web app (Docker) |
| 3001 | TCP (127.0.0.1) | POS integration (Docker) |
| 3306 | TCP (127.0.0.1) | MySQL |
| 4001 | TCP | Unknown |
| 5060 | TCP/UDP | LiveKit SIP service |
| 6379 | TCP | Redis (redis-lk container) |
| 7880 | TCP | LiveKit server |
| 7881 | TCP | LiveKit RTC TCP |
| 8000 | TCP | Order API (Docker) |
| 8001 | TCP (127.0.0.1) | **Our token server (FastAPI)** |
| 8080 | TCP | Soniox Caddy |
| 8090 | TCP | Apache2 |
| 8443 | TCP | Soniox Caddy HTTPS |
| 10000-10100 | UDP | LiveKit RTC media |
| 20000-30000 | UDP | LiveKit SIP RTP |
| 27017 | TCP (127.0.0.1) | MongoDB |
| 33060 | TCP (127.0.0.1) | MySQL X protocol |

---

## Our Project — livekit-sarvam

### Location
```
/opt/livekit-sarvam/
```

### Environment — `/opt/livekit-sarvam/.env`
```
LIVEKIT_URL=wss://lk.bizbull.ai
LIVEKIT_API_KEY=devkey
LIVEKIT_API_SECRET=7fb987483e9c463c7777ea7e9a97e4bde86bcaa5
SARVAM_API_KEY=sk_70uoawf4_UVla2uvKlDWjuo8PG3fVKm5g
TWILIO_ACCOUNT_SID=AC02b35d544672eb20c553c7c0b7d2291e
TWILIO_AUTH_TOKEN=ef3bf837081b393a37d24654ff6eecbf
```

### What We Reuse (no new containers needed)
- LiveKit server → `lk.bizbull.ai` (already running on port 7880)
- LiveKit SIP → `livekit-sip-1` (already running on port 5060)
- Redis → `redis-lk` on `localhost:6379` (already running)

### What We Added
- **Agent worker** → Python systemd service (`restaurant-agent.service`)
- **Token server** → FastAPI on port 8001, systemd service (`restaurant-token.service`)
- **Web app** → React static files, built to `web/dist/`, served by Caddy

---

## Systemd Services

### `restaurant-agent.service`
```
File:    /etc/systemd/system/restaurant-agent.service
Source:  /opt/livekit-sarvam/deploy/restaurant-agent.service
Exec:    /opt/livekit-sarvam/.venv/bin/python agent.py start
Dir:     /opt/livekit-sarvam
Restart: always, 5s delay
```

### `restaurant-token.service`
```
File:    /etc/systemd/system/restaurant-token.service
Source:  /opt/livekit-sarvam/deploy/restaurant-token.service
Exec:    uvicorn token_server:app --host 0.0.0.0 --port 8001
Dir:     /opt/livekit-sarvam
Restart: always, 5s delay
```

### Common Commands
```bash
# Check status
systemctl status restaurant-agent restaurant-token

# Restart after git pull
systemctl restart restaurant-agent restaurant-token

# View logs
journalctl -u restaurant-agent -f
journalctl -u restaurant-token -f
```

---

## SIP Configuration

### LiveKit SIP Trunk
- **Trunk ID**: `ST_ULoCL8A6UHRs`
- **Name**: Twilio Restaurant Line
- **Phone number**: `+15878175156`

### LiveKit SIP Dispatch Rule
- **Rule ID**: `SDR_VJLPyAuaAwEv`
- **Name**: Restaurant Agent Dispatch
- **Room prefix**: `phone-`
- **Agent dispatch**: `RoomAgentDispatch(agent_name="")` — agent auto-joins every incoming call

### Twilio
- **Account SID**: `AC02b35d544672eb20c553c7c0b7d2291e`
- **SIP Trunk**: `parkash-liveket`
- **Phone number**: `+15878175156`
- **Origination URI**: `sip:lk.bizbull.ai:5060;transport=udp`

To reconfigure SIP (e.g. after server wipe):
```bash
uv run python scripts/setup_sip.py
```

To test an outbound call:
```bash
uv run python scripts/test_call.py +919413752688
```

---

## Web App

- **Source**: `web/src/`
- **Build output**: `web/dist/`
- **Public URL**: `https://sarvam.bizbull.ai`
- **Build command**: `cd web && npm install && npm run build`

Caddy serves `web/dist/` as static files. After a frontend change, rebuild and restart nothing — Caddy picks up the new files automatically.

---

## Installation (Completed)

- [x] Install uv 0.11.24 — `/root/.local/bin/uv`
- [x] Clone repo → `/opt/livekit-sarvam/`
- [x] Create `.env` at `/opt/livekit-sarvam/.env`
- [x] Run `uv sync` — 83+ packages installed, no conflicts
- [x] Copy systemd unit files → `/etc/systemd/system/`
- [x] `systemctl enable --now restaurant-agent restaurant-token`
- [x] Add `sarvam.bizbull.ai` to `/etc/caddy/Caddyfile` and reloaded Caddy
- [x] Build React web app → `web/dist/`
- [x] Run `scripts/setup_sip.py` to create SIP trunk + dispatch rule

## Deploy After Code Changes

```bash
cd /opt/livekit-sarvam
git pull origin main
systemctl restart restaurant-agent restaurant-token
```

For frontend changes, also rebuild:
```bash
cd /opt/livekit-sarvam/web && npm run build
```

---

## Installed Package Versions (Locked)

| Package | Version |
|---|---|
| livekit-agents | 1.6.3 |
| livekit-plugins-sarvam | 1.6.3 |
| livekit | 1.1.9 |
| livekit-api | 1.1.1 |
| fastapi | 0.138.0 |
| uvicorn | 0.49.0 |
| python-dotenv | 1.2.2 |
| pydantic | 2.13.4 |
| twilio | 9.x |
