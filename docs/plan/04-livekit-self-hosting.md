# LiveKit Self-Hosting Plan

## Requirements

| Requirement | Detail |
|---|---|
| Domain | e.g., `livekit.yourdomain.com` |
| SSL Certificate | From a trusted CA (Let's Encrypt works) |
| VM | Compute-optimized, min 2 vCPU / 4GB RAM |
| Network | 10Gbps preferred, host networking in Docker |
| OS | Ubuntu 22.04 LTS recommended |

---

## Ports to Open (Firewall)

| Port | Protocol | Purpose |
|---|---|---|
| 7880 | TCP | HTTP + WebSocket signaling |
| 7881 | TCP | RTC over TCP (fallback) |
| 50000-60000 | UDP | RTC media streams |
| 443 | UDP + TCP | TURN server |
| 3478 | UDP + TCP | TURN (alternative) |
| 6379 | TCP | Redis (internal only) |

---

## docker-compose.yml (Planned)

```yaml
version: "3.9"

services:
  livekit:
    image: livekit/livekit-server:latest
    network_mode: host           # required for WebRTC
    restart: unless-stopped
    volumes:
      - ./livekit.yaml:/livekit.yaml
    command: --config /livekit.yaml

  redis:
    image: redis:7-alpine
    restart: unless-stopped
    ports:
      - "6379:6379"
```

---

## livekit.yaml (Planned)

```yaml
port: 7880
rtc:
  tcp_port: 7881
  port_range_start: 50000
  port_range_end: 60000
  use_external_ip: true      # required for cloud VMs

keys:
  APIxxxxxxxx: <secret>       # generate with: livekit-server generate-keys

turn:
  enabled: true
  domain: livekit.yourdomain.com
  tls_port: 443
  udp_port: 443
  external_tls: true         # if behind nginx/caddy with TLS termination

redis:
  address: localhost:6379

logging:
  level: info
```

---

## Key Generation

```bash
docker run --rm livekit/livekit-server generate-keys
# Outputs: API Key + Secret — save these in .env
```

---

## Agent Worker .env

```env
LIVEKIT_URL=wss://livekit.yourdomain.com
LIVEKIT_API_KEY=APIxxxxxxxx
LIVEKIT_API_SECRET=<secret>
SARVAM_API_KEY=sk_xxxxxxxx
```

---

## Local Dev Setup (Without Domain)

For development only, use LiveKit Cloud free tier or run locally:

```bash
# Start LiveKit locally (no TURN needed for local)
docker run --rm \
  -p 7880:7880 \
  -p 7881:7881/tcp \
  -p 50000-60000:50000-60000/udp \
  livekit/livekit-server:latest \
  --dev   # generates temp API key, disables auth
```

Agent connects via `ws://localhost:7880` in dev mode.

---

## Production Checklist

- [ ] VM provisioned with correct instance type
- [ ] DNS A record pointing to VM public IP
- [ ] SSL cert issued (Caddy auto-TLS or Certbot)
- [ ] Firewall rules opened for all required ports
- [ ] `livekit.yaml` configured with real keys
- [ ] `docker-compose up -d` running stable
- [ ] Healthcheck: `curl http://livekit.yourdomain.com:7880` returns 200
- [ ] Agent worker connects and appears in LiveKit dashboard
