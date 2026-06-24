# VPS Deployment Guide

## VPS Folder Structure

```
/opt/livekit-sarvam/                  ← root of everything
├── .env                              ← all secrets (never commit)
├── agent.py
├── token_server.py
├── pyproject.toml
├── restaurant/
│   ├── menu.py
│   ├── orders.py
│   └── reservations.py
├── prompts/
│   └── system_pa.txt
├── web/                              ← built React app (static files)
│   └── dist/
├── docker/
│   ├── docker-compose.yml
│   ├── livekit.yaml
│   └── sip-config.yaml
└── logs/
    ├── agent.log
    └── token-server.log
```

---

## Step 0 — Connect to VPS

```bash
ssh root@YOUR_VPS_IP
```

---

## Step 1 — Initial Server Setup

```bash
# Update system
apt update && apt upgrade -y

# Install essentials
apt install -y curl git ufw fail2ban

# Create app user (don't run everything as root)
useradd -m -s /bin/bash appuser
usermod -aG sudo appuser
```

---

## Step 2 — Install Docker + Docker Compose

```bash
# Install Docker
curl -fsSL https://get.docker.com | sh

# Add appuser to docker group
usermod -aG docker appuser

# Install Docker Compose plugin
apt install -y docker-compose-plugin

# Verify
docker --version
docker compose version
```

---

## Step 3 — Install Python (uv)

```bash
# Install uv (Python package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.cargo/env

# Verify
uv --version
```

---

## Step 4 — Firewall Rules

```bash
# Default deny
ufw default deny incoming
ufw default allow outgoing

# SSH
ufw allow 22/tcp

# LiveKit WebRTC
ufw allow 7880/tcp
ufw allow 7881/tcp
ufw allow 50000:60000/udp

# TURN server
ufw allow 443/tcp
ufw allow 443/udp
ufw allow 3478/tcp
ufw allow 3478/udp

# SIP (Twilio)
ufw allow 5060/tcp
ufw allow 5060/udp
ufw allow 5061/tcp
ufw allow 10000:20000/udp

# Web app + token server
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow 8080/tcp

# Enable
ufw enable

# Verify
ufw status numbered
```

---

## Step 5 — Install Caddy (SSL + Reverse Proxy)

```bash
apt install -y debian-keyring debian-archive-keyring apt-transport-https curl
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | tee /etc/apt/sources.list.d/caddy-stable.list
apt update && apt install -y caddy
```

**Caddyfile** (`/etc/caddy/Caddyfile`):

```
# LiveKit signaling (WebSocket proxy)
livekit.yourdomain.com {
    reverse_proxy localhost:7880
}

# Token server API
api.yourdomain.com {
    reverse_proxy localhost:8080
}

# Web app
app.yourdomain.com {
    root * /opt/livekit-sarvam/web/dist
    file_server
}
```

```bash
# Reload Caddy
systemctl reload caddy
systemctl enable caddy
```

---

## Step 6 — Clone Repo and Set Up App

```bash
# Create app directory
mkdir -p /opt/livekit-sarvam
cd /opt/livekit-sarvam

# Clone
git clone https://github.com/Shivek-cmd/livekit-sarvam.git .

# Create Python virtual env and install deps
uv sync
```

---

## Step 7 — Generate LiveKit Keys

```bash
cd /opt/livekit-sarvam

docker run --rm livekit/livekit-server generate-keys
# Output:
# API Key:    APIxxxxxxxxxxxxxxxxx
# API Secret: xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
# SAVE THESE — you only see them once
```

---

## Step 8 — Create .env File

```bash
cat > /opt/livekit-sarvam/.env << 'EOF'
# LiveKit
LIVEKIT_URL=wss://livekit.yourdomain.com
LIVEKIT_API_KEY=APIxxxxxxxxxxxxxxxxx
LIVEKIT_API_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Sarvam
SARVAM_API_KEY=sk_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Twilio (for SIP setup reference — not used in agent runtime)
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_PHONE_NUMBER=+91XXXXXXXXXX
EOF

chmod 600 /opt/livekit-sarvam/.env
```

---

## Step 9 — Create LiveKit Config Files

**`docker/livekit.yaml`**:

```bash
cat > /opt/livekit-sarvam/docker/livekit.yaml << 'EOF'
port: 7880
rtc:
  tcp_port: 7881
  port_range_start: 50000
  port_range_end: 60000
  use_external_ip: true

keys:
  APIxxxxxxxxxxxxxxxxx: xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

turn:
  enabled: true
  domain: livekit.yourdomain.com
  tls_port: 443
  udp_port: 443
  external_tls: true

redis:
  address: redis:6379

logging:
  level: info
EOF
```

**`docker/sip-config.yaml`**:

```bash
cat > /opt/livekit-sarvam/docker/sip-config.yaml << 'EOF'
api_key: APIxxxxxxxxxxxxxxxxx
api_secret: xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
ws_url: wss://livekit.yourdomain.com

redis:
  address: redis:6379

sip_port: 5060
rtp_port: 10000
rtp_port_range_end: 20000
EOF
```

---

## Step 10 — Create docker-compose.yml

```bash
cat > /opt/livekit-sarvam/docker/docker-compose.yml << 'EOF'
version: "3.9"

services:
  redis:
    image: redis:7-alpine
    restart: unless-stopped
    networks:
      - livekit-net

  livekit:
    image: livekit/livekit-server:latest
    network_mode: host
    restart: unless-stopped
    depends_on:
      - redis
    volumes:
      - ./livekit.yaml:/livekit.yaml
    command: --config /livekit.yaml

  livekit-sip:
    image: livekit/sip:latest
    network_mode: host
    restart: unless-stopped
    depends_on:
      - livekit
      - redis
    environment:
      - SIP_CONFIG_BODY=${SIP_CONFIG_BODY}

networks:
  livekit-net:
    driver: bridge
EOF
```

---

## Step 11 — Start Docker Services

```bash
cd /opt/livekit-sarvam/docker

# Export SIP config as env var
export SIP_CONFIG_BODY=$(cat sip-config.yaml)

# Start all services
docker compose up -d

# Verify all running
docker compose ps

# Check LiveKit logs
docker compose logs livekit --tail=50

# Check SIP service logs
docker compose logs livekit-sip --tail=50
```

**Health check**:
```bash
curl http://localhost:7880
# Should return: {"status": "ok"} or similar
```

---

## Step 12 — Run Agent Worker as Systemd Service

```bash
cat > /etc/systemd/system/livekit-agent.service << 'EOF'
[Unit]
Description=LiveKit Sarvam Restaurant Agent
After=network.target docker.service
Requires=docker.service

[Service]
Type=simple
User=appuser
WorkingDirectory=/opt/livekit-sarvam
EnvironmentFile=/opt/livekit-sarvam/.env
ExecStart=/root/.cargo/bin/uv run python agent.py start
Restart=always
RestartSec=5
StandardOutput=append:/opt/livekit-sarvam/logs/agent.log
StandardError=append:/opt/livekit-sarvam/logs/agent.log

[Install]
WantedBy=multi-user.target
EOF

# Create logs dir
mkdir -p /opt/livekit-sarvam/logs

# Enable and start
systemctl daemon-reload
systemctl enable livekit-agent
systemctl start livekit-agent

# Check status
systemctl status livekit-agent

# Tail logs
tail -f /opt/livekit-sarvam/logs/agent.log
```

---

## Step 13 — Run Token Server as Systemd Service

```bash
cat > /etc/systemd/system/livekit-token-server.service << 'EOF'
[Unit]
Description=LiveKit Token Server
After=network.target

[Service]
Type=simple
User=appuser
WorkingDirectory=/opt/livekit-sarvam
EnvironmentFile=/opt/livekit-sarvam/.env
ExecStart=/root/.cargo/bin/uv run uvicorn token_server:app --host 0.0.0.0 --port 8080
Restart=always
RestartSec=5
StandardOutput=append:/opt/livekit-sarvam/logs/token-server.log
StandardError=append:/opt/livekit-sarvam/logs/token-server.log

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable livekit-token-server
systemctl start livekit-token-server
systemctl status livekit-token-server
```

---

## Step 14 — Deploy Web App (React Build)

Run this on your **local machine**, then push the build to VPS:

```bash
# Local: build the React app
cd web
pnpm install
pnpm build          # outputs to web/dist/

# Push built files to VPS
rsync -avz dist/ root@YOUR_VPS_IP:/opt/livekit-sarvam/web/dist/
```

Or build directly on VPS:

```bash
# On VPS: install Node
curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
apt install -y nodejs
npm install -g pnpm

# Build
cd /opt/livekit-sarvam/web
pnpm install
pnpm build
```

Caddy serves the `dist/` folder automatically at `https://app.yourdomain.com`.

---

## Step 15 — Set Up Twilio SIP Trunk (After Docker is Running)

```bash
# Install LiveKit CLI
curl -sSL https://github.com/livekit/livekit-cli/releases/latest/download/lk_linux_amd64.tar.gz | tar -xz
mv lk /usr/local/bin/

# Set credentials
export LIVEKIT_URL=wss://livekit.yourdomain.com
export LIVEKIT_API_KEY=APIxxxxxxxxxxxxxxxxx
export LIVEKIT_API_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Create inbound SIP trunk (after configuring Twilio console)
lk sip inbound create \
  --name "twilio-punjabi-restaurant" \
  --numbers "+91XXXXXXXXXX"

# List trunks to get trunk ID
lk sip inbound list

# Create dispatch rule
lk sip dispatch create \
  --trunk-id <TRUNK_ID_FROM_ABOVE> \
  --rule-type individual-room \
  --room-prefix "restaurant-call-"
```

---

## Updating the App (Deploy New Code)

```bash
# On VPS
cd /opt/livekit-sarvam

# Pull latest code
git pull origin main

# Restart agent (picks up new agent.py)
systemctl restart livekit-agent

# Restart token server (picks up new token_server.py)
systemctl restart livekit-token-server

# If Docker configs changed
cd docker && docker compose pull && docker compose up -d

# Rebuild + redeploy web app if frontend changed
cd ../web && pnpm build
# (Caddy serves static files live — no restart needed)
```

---

## Useful Monitoring Commands

```bash
# All service statuses at a glance
systemctl status livekit-agent livekit-token-server

# Live agent logs
journalctl -u livekit-agent -f

# Docker service logs
cd /opt/livekit-sarvam/docker
docker compose logs -f

# Check ports are listening
ss -tulnp | grep -E '7880|7881|5060|8080'

# Check disk space (logs can grow)
df -h /opt/livekit-sarvam

# Rotate logs if needed
truncate -s 0 /opt/livekit-sarvam/logs/agent.log
```

---

## Full Service Map (What's Running on VPS)

| Process | How It Runs | Port | Managed By |
|---|---|---|---|
| LiveKit Server | Docker | 7880, 7881, 443 | docker compose |
| LiveKit SIP Service | Docker | 5060, 10000-20000 | docker compose |
| Redis | Docker | 6379 (internal) | docker compose |
| Agent Worker | Systemd | — (outbound only) | systemctl |
| Token Server | Systemd | 8080 | systemctl |
| Caddy (SSL proxy) | Systemd | 80, 443 | systemctl |
| Web App | Static files | via Caddy | N/A |
