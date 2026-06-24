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
| uv | NOT INSTALLED | Must install before running agent |

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

### 3. Soniox Voice Project (lk.bizbull.ai was built for this)
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

lk.bizbull.ai          → localhost:7880     (LiveKit server)
order.bizbull.ai       → localhost:3000/8000 (restaurant order app)
integration.bizbull.ai → localhost:3001     (POS integration)
voice.bizbull.ai       → localhost:8090     (Apache)
getsetvisa.com         → localhost:8090     (Apache)
```

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
| 8080 | TCP | Soniox Caddy |
| 8090 | TCP | Apache2 |
| 8443 | TCP | Soniox Caddy HTTPS |
| 10000-10100 | UDP | LiveKit RTC media |
| 20000-30000 | UDP | LiveKit SIP RTP |
| 27017 | TCP (127.0.0.1) | MongoDB |
| 33060 | TCP (127.0.0.1) | MySQL X protocol |

## Ports Free for Our Project

| Port | Planned Use |
|---|---|
| 8001 | Our token server (FastAPI) |
| Static files | Web app served by Caddy (no separate port) |

---

## Our Project — livekit-sarvam

### Location
```
/opt/livekit-sarvam/
```

### Credentials (reusing existing LiveKit)
```
LIVEKIT_URL=wss://lk.bizbull.ai
LIVEKIT_API_KEY=devkey
LIVEKIT_API_SECRET=7fb987483e9c463c7777ea7e9a97e4bde86bcaa5
SARVAM_API_KEY=sk_70uoawf4_UVla2uvKlDWjuo8PG3fVKm5g
```

### What We Reuse (no new containers needed)
- LiveKit server → `lk.bizbull.ai` (already running)
- LiveKit SIP → `livekit-sip-1` (already running)
- Redis → `redis-lk` on `localhost:6379` (already running)

### What We Add
- Agent worker → Python systemd service
- Token server → FastAPI on port 8001, systemd service
- Web app → React static files, served by Caddy

### Planned Subdomains (add to Caddyfile)
- TBD — confirm subdomain names with user before adding

---

## Installation Checklist (Run Once on Fresh Session)

- [ ] Install uv: `curl -LsSf https://astral.sh/uv/install.sh | sh && source $HOME/.local/bin/env`
- [ ] Clone repo: `git clone https://github.com/Shivek-cmd/livekit-sarvam.git /opt/livekit-sarvam`
- [ ] Create `.env` at `/opt/livekit-sarvam/.env` with credentials above
- [ ] Run `cd /opt/livekit-sarvam && uv sync`
- [ ] Verify: `uv run python -c "import livekit.agents; print(livekit.agents.__version__)"`
- [ ] Add subdomains to `/etc/caddy/Caddyfile` and reload Caddy
- [ ] Set up systemd services for agent + token server
