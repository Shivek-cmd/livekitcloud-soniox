# Milestones & Build Phases

## Phase 1 — Agent Core (Local)

**Goal**: Working Punjabi voice conversation locally, via web browser.

| Task | Details |
|---|---|
| Set up Python project | `uv init`, `pyproject.toml`, `.env` |
| Install `livekit-agents[sarvam]` | Pin to `~=1.5` |
| Run LiveKit locally via Docker | `--dev` mode, no domain needed |
| Write `agent.py` | Sarvam STT → LLM → TTS pipeline |
| Write `token_server.py` | FastAPI token endpoint |
| Test via LiveKit Playground | Connect playground to local server |
| Validate Punjabi round-trip | Speak Punjabi → hear Punjabi reply |

**Done when**: Full Punjabi voice loop works in browser locally.

---

## Phase 2 — Self-Hosted Production (Web Channel Live)

**Goal**: Deploy to VPS, web users can call the agent from anywhere.

| Task | Details |
|---|---|
| Provision VM | Ubuntu 22.04, 4 vCPU / 8GB RAM |
| DNS + SSL | Domain A record + Caddy auto-TLS |
| LiveKit + Redis | `docker-compose up -d` with `livekit.yaml` |
| Deploy agent worker | Systemd service (auto-restart) |
| Deploy token server | FastAPI on port 8080 |
| Build minimal React web app | "Start Call" button + voice UI |
| Deploy web app | Nginx or Caddy static serve |
| Smoke test | External user opens URL → speaks Punjabi → hears reply |

**Done when**: Anyone with the URL can have a Punjabi voice conversation.

---

## Phase 3 — Phone Channel (Twilio SIP)

**Goal**: Same agent reachable by dialing a phone number.

| Task | Details |
|---|---|
| Deploy `livekit-sip` container | Add to `docker-compose.yml` |
| Open SIP ports | 5060, 10000-20000 UDP on firewall |
| Configure SIP service | `sip-config.yaml` with LiveKit API keys |
| Set up Twilio SIP trunk | Origination URI → LiveKit SIP |
| Buy Indian phone number | +91 DID via Twilio |
| Create LiveKit inbound trunk | Via LiveKit CLI |
| Create dispatch rule | `individual-room` per caller |
| Allowlist Twilio IPs | On VM firewall for port 5060 |
| Test call | Dial number → agent answers in Punjabi |

**Done when**: Dialing the phone number connects to the Punjabi voice agent.

---

## Phase 4 — Punjabi Quality Tuning

**Goal**: Conversation feels natural, not robotic.

| Task | Details |
|---|---|
| Tune system prompt | Short answers, natural Punjabi tone |
| STT accuracy testing | Multiple Punjabi accents and dialects |
| TTS voice selection | Pick best `speaker` in `bulbul:v3` for Punjabi |
| Code-mixed handling | `code-mixed` STT mode for Punjabi+English |
| Phone audio quality | Compare web vs phone STT accuracy (8kHz vs 16kHz) |
| Latency profiling | Measure TTFA on both channels, target < 1.1s |
| Channel detection | Adjust agent behavior for phone (shorter sentences) |

---

## Phase 5 — Features (Future)

| Feature | Notes |
|---|---|
| Outbound calls | Agent proactively calls users via Twilio |
| Conversation memory | Multi-turn context beyond single session |
| Tool calling | Weather, search, calendar in Punjabi |
| Domain-specific agent | Healthcare / agriculture / customer support |
| Hindi↔Punjabi switching | Bilingual conversation handling |
| Analytics | Transcript logging, latency dashboard |
| WhatsApp channel | LiveKit SIP connectors support WhatsApp |

---

## What NOT to Build Yet

- No custom STT/TTS wrappers — `livekit-plugins-sarvam` handles this
- No database — no persistence in Phase 1-2
- No auth/login — LiveKit token is enough for Phase 1-2
- No outbound calls — inbound only until Phase 5
- No custom frontend in Phase 1 — use LiveKit Playground
