# LiveKit Self-Hosting Plan

## Services to Deploy

| Service | Docker Image | Purpose |
|---|---|---|
| LiveKit Server | `livekit/livekit-server:latest` | WebRTC signaling + media relay |
| LiveKit SIP Service | `livekit/sip:latest` | Bridges Twilio ↔ LiveKit |
| Redis | `redis:7-alpine` | Shared state between services |

---

## VM Requirements

| Requirement | Detail |
|---|---|
| OS | Ubuntu 22.04 LTS |
| CPU | Compute-optimized, min 2 vCPU (4 recommended) |
| RAM | Min 4GB (8GB recommended) |
| Network | 10Gbps preferred; host networking in Docker |
| Domain | `livekit.yourdomain.com` (needs trusted SSL) |

---

## Ports to Open (Firewall)

| Port | Protocol | Service | Purpose |
|---|---|---|---|
| 7880 | TCP | LiveKit Server | HTTP + WebSocket signaling |
| 7881 | TCP | LiveKit Server | RTC over TCP (fallback) |
| 50000-60000 | UDP | LiveKit Server | WebRTC media streams |
| 443 | UDP + TCP | LiveKit Server | TURN server |
| 3478 | UDP + TCP | LiveKit Server | TURN (alternative) |
| 5060 | UDP + TCP | SIP Service | SIP signaling (from Twilio) |
| 5061 | TCP | SIP Service | SIP/TLS signaling |
| 10000-20000 | UDP | SIP Service | RTP media from Twilio |
| 6379 | TCP | Redis | Internal only (do not expose) |

---

## docker-compose.yml (Planned)

```yaml
version: "3.9"

services:
  redis:
    image: redis:7-alpine
    restart: unless-stopped
    # Internal only — no external port binding

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
      - SIP_CONFIG_BODY=${SIP_CONFIG_BODY}   # YAML config via env var
```

---

## livekit.yaml (Planned)

```yaml
port: 7880
rtc:
  tcp_port: 7881
  port_range_start: 50000
  port_range_end: 60000
  use_external_ip: true

keys:
  APIxxxxxxxx: <secret>        # generate with: livekit-server generate-keys

turn:
  enabled: true
  domain: livekit.yourdomain.com
  tls_port: 443
  udp_port: 443
  external_tls: true

redis:
  address: localhost:6379

logging:
  level: info
```

---

## SIP Service Config (Planned)

The SIP service reads its config from the `SIP_CONFIG_BODY` environment variable (YAML string):

```yaml
# sip-config.yaml (set as env var SIP_CONFIG_BODY)
api_key: APIxxxxxxxx
api_secret: <secret>
ws_url: wss://livekit.yourdomain.com

redis:
  address: localhost:6379

sip_port: 5060
rtp_port: 10000
rtp_port_range_end: 20000
```

---

## Key Generation

```bash
docker run --rm livekit/livekit-server generate-keys
# Outputs: API Key + Secret — save both in .env
```

---

## .env File

```env
# LiveKit
LIVEKIT_URL=wss://livekit.yourdomain.com
LIVEKIT_API_KEY=APIxxxxxxxx
LIVEKIT_API_SECRET=<secret>

# Sarvam
SARVAM_API_KEY=sk_xxxxxxxx

# Twilio (for SIP trunk setup only — not used in agent code)
TWILIO_ACCOUNT_SID=ACxxxxxxxx
TWILIO_AUTH_TOKEN=xxxxxxxx
TWILIO_PHONE_NUMBER=+91XXXXXXXXXX
```

---

## Twilio SIP Trunk Setup (Steps)

1. Log in to Twilio Console → Elastic SIP Trunking → Create Trunk
2. Set **Origination URI**: `sip:livekit.yourdomain.com:5060`
3. Add Twilio's IP ranges to SIP Service allowlist (Twilio publishes these)
4. Buy an Indian phone number (+91) and assign it to the trunk
5. In LiveKit, create an **Inbound Trunk** via API or LiveKit CLI pointing to Twilio's trunk
6. Create a **Dispatch Rule**: all inbound calls → create new room → trigger agent

```bash
# Create inbound trunk (LiveKit CLI)
lk sip inbound create \
  --name "twilio-trunk" \
  --numbers "+91XXXXXXXXXX"

# Create dispatch rule
lk sip dispatch create \
  --trunk-id <trunk-id> \
  --rule-type individual-room   # each caller gets own room
```

---

## Local Dev Setup

For development (no domain, no Twilio):

```bash
# LiveKit server in dev mode (auto API key, no auth)
docker run --rm \
  -p 7880:7880 -p 7881:7881/tcp \
  -p 50000-60000:50000-60000/udp \
  livekit/livekit-server:latest --dev

# Agent connects to ws://localhost:7880
```

Web channel works locally. Phone channel requires a public IP and real Twilio setup.

---

## Production Checklist

**LiveKit Server**
- [ ] VM provisioned, Ubuntu 22.04
- [ ] DNS A record → VM public IP
- [ ] SSL cert issued (Caddy or Certbot)
- [ ] All ports opened in firewall
- [ ] `livekit.yaml` configured with generated keys
- [ ] `docker-compose up -d` stable
- [ ] Healthcheck: `curl https://livekit.yourdomain.com:7880` → 200

**SIP / Twilio**
- [ ] `livekit-sip` container running alongside LiveKit
- [ ] SIP ports 5060, 10000-20000 open
- [ ] Twilio SIP trunk created with origination URI
- [ ] Indian phone number purchased and assigned
- [ ] LiveKit inbound trunk + dispatch rule created
- [ ] Test call: dial number → room created → agent joins

**Agent Worker**
- [ ] `.env` populated with all keys
- [ ] Agent connects to LiveKit server successfully
- [ ] Web user joins → agent responds in Punjabi
- [ ] Phone caller dials → agent responds in Punjabi
