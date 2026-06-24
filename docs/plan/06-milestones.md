# Milestones & Build Phases

## Phase 1 — Foundation (Do First)

**Goal**: Get a working Punjabi voice conversation end-to-end, even locally.

| Task | Details |
|---|---|
| Set up Python project | `uv init`, `pyproject.toml`, `.env` |
| Install `livekit-agents[sarvam]` | Pin to `~=1.5` |
| Run LiveKit locally via Docker | `--dev` mode, no domain needed |
| Write `agent.py` | Basic STT→LLM→TTS pipeline |
| Test with LiveKit Playground | Connect playground to local server |
| Validate Punjabi round-trip | Speak Punjabi → get Punjabi response |

**Done when**: You can speak Punjabi and hear a Punjabi reply.

---

## Phase 2 — Self-Hosted Production Server

**Goal**: Run on a real VPS with a domain, accessible from anywhere.

| Task | Details |
|---|---|
| Provision VM | Ubuntu 22.04, 2+ vCPU |
| Point domain DNS | A record → VM IP |
| Set up SSL | Caddy or Certbot |
| Configure `livekit.yaml` | Real keys, TURN enabled |
| `docker-compose up -d` | LiveKit + Redis |
| Deploy agent worker | Systemd service or Docker container |
| Smoke test from external network | Phone/remote browser |

**Done when**: Agent is reachable from outside the VPS.

---

## Phase 3 — Quality & Punjabi Tuning

**Goal**: Make the Punjabi conversation actually feel good.

| Task | Details |
|---|---|
| Tune system prompt | Punjabi-only, short answers, natural tone |
| Test STT accuracy | Various Punjabi accents and dialects |
| Test TTS voices | Pick the best `speaker` for Punjabi |
| Handle code-mixed input | `code-mixed` STT mode |
| Handle Romanized Punjabi | Transliterate mode |
| Latency profiling | Measure TTFA, optimize if > 1.5s |

---

## Phase 4 — Features (Future)

Ideas to implement after Phase 1-3 are solid:

- [ ] Custom frontend (React + LiveKit SDK)
- [ ] Telephony integration (phone calls via SIP)
- [ ] Conversation memory / multi-turn context
- [ ] Tool calling (weather, calendar, search in Punjabi)
- [ ] Domain-specific agent (e.g., healthcare, agriculture assistant)
- [ ] Support Hindi + Punjabi bilingual switching
- [ ] Analytics dashboard (transcripts, latency, error rates)

---

## What NOT to Build Yet

- No custom STT/TTS wrappers — the `livekit-plugins-sarvam` package handles this
- No custom frontend — use LiveKit Playground for Phase 1-2
- No database — no persistence needed in Phase 1
- No auth system — LiveKit token generation is enough for testing
