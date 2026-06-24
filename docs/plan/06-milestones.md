# Milestones & Build Phases

## Phase 1 — Agent Core ✅ DONE

**Goal**: Working Punjabi voice conversation, agent pipeline validated.

| Task | Status |
|---|---|
| Set up Python project — `uv init`, `pyproject.toml`, `.env` | ✅ |
| Install `livekit-agents[sarvam]` pinned to `~=1.6` | ✅ |
| Write `agent.py` — Sarvam STT → LLM → TTS pipeline | ✅ |
| Write `token_server.py` — FastAPI token + agent dispatch | ✅ |
| Test via LiveKit agents-playground | ✅ |
| Validate Punjabi voice round-trip | ✅ |

**Notes**: Went straight to VPS rather than running locally. Tested via agents-playground with VPS credentials.

---

## Phase 2 — Self-Hosted Production (Web Channel) ✅ DONE

**Goal**: Deploy to VPS, web users can call from `https://sarvam.bizbull.ai`.

| Task | Status |
|---|---|
| Reuse existing LiveKit server (`lk.bizbull.ai`) | ✅ |
| Add `sarvam.bizbull.ai` to Caddyfile | ✅ |
| Deploy agent worker — `restaurant-agent.service` systemd | ✅ |
| Deploy token server — `restaurant-token.service` systemd on port 8001 | ✅ |
| Build React web app — "Start Call" button + voice UI | ✅ |
| Serve web app as static files via Caddy | ✅ |
| Echo cancellation on mic | ✅ PR 006 |
| Smoke test — open URL, speak Punjabi, hear reply | ✅ |

**Notes**: Token server dispatches agent via `lk.agent_dispatch.create_dispatch()` on each web call. Echo cancellation constraints added to mic `getUserMedia`.

---

## Phase 3 — Phone Channel (Twilio SIP) ✅ DONE

**Goal**: Same agent reachable by dialing `+15878175156`.

| Task | Status |
|---|---|
| Reuse existing `livekit-sip-1` container | ✅ |
| Create LiveKit SIP inbound trunk — `ST_ULoCL8A6UHRs` | ✅ |
| Create dispatch rule with agent auto-dispatch — `SDR_VJLPyAuaAwEv` | ✅ PR 008 |
| Reuse existing Twilio trunk `parkash-liveket` | ✅ |
| Link Twilio number `+15878175156` to trunk | ✅ |
| Write reproducible `scripts/setup_sip.py` | ✅ PR 008 |
| Write `scripts/test_call.py` — outbound call tester | ✅ |
| Test call — dial number → Sierra answers | ✅ |

**Key fix**: SIP dispatch rule must include `room_config=RoomConfiguration(agents=[RoomAgentDispatch(agent_name="")])`. Without it the room is created but the agent never joins.

---

## Phase 4 — Quality Tuning (In Progress)

**Goal**: Conversation feels natural, not robotic.

| Task | Status | Notes |
|---|---|---|
| Fix deprecated LLM model (`sarvam-30b-16k` → `sarvam-30b`) | ✅ PR 002 | |
| Rewrite system prompt — Sierra persona, humanized | ✅ PR 009 | |
| Natural Punjabi-English code-switching language | ✅ PR 009 | |
| Spice level per item (starters + mains only) | ✅ PR 009 | |
| Phone digit-by-digit confirmation | ✅ PR 009 | |
| STT accuracy testing across Punjabi accents | ⬜ | |
| Latency profiling — measure TTFA on both channels | ⬜ | |
| TTS voice comparison across speakers | ⬜ | |

---

## Phase 5 — Features (Deferred)

| Feature | Notes |
|---|---|
| Order persistence | Save orders to database (deferred) |
| Order webhook | Notify POS/kitchen on new order (deferred) |
| Multi-tenant | Multiple restaurants, each with own config (deferred — future SaaS) |
| Outbound calls | Agent proactively calls users via Twilio |
| Analytics | Transcript logging, latency dashboard |
| Hindi↔Punjabi switching | Bilingual conversation handling |
| WhatsApp channel | LiveKit SIP connectors support WhatsApp |

---

## What NOT to Build Yet

- No database — persistence deferred
- No order webhook — deferred
- No multi-tenant architecture — deferred (user will sell service later)
- No outbound calling — inbound only
- No custom STT/TTS wrappers — `livekit-plugins-sarvam` handles this
