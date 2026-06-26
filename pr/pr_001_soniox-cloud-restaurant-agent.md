# PR 001 — Restaurant Voice Agent (Soniox + LiveKit Cloud)

## Branch
`pr_001_soniox-cloud-restaurant-agent`

## What This PR Does
Foundational PR for **Sierra**, the Punjabi restaurant voice agent for **Bizbull Restaurant**. The
agent answers phone (and web) calls, takes food orders and reservations, and answers menu questions in
natural Punjabi-English. It runs on **LiveKit Cloud** for transport (clean telephony echo
cancellation) with a fully **North-America-hosted voice stack** — **Soniox** STT + TTS and **OpenAI
GPT** LLM — so latency stays low for Canadian callers. This PR represents the current, consolidated
state of the project.

---

## Architecture (current)

```
Caller (Canada) ──PSTN──> Twilio (+15878175156) ──SIP──> LiveKit Cloud (US West)
                                                              │  (per-caller room, trunk Krisp NC)
Browser ──WebRTC──> LiveKit Cloud ───────────────────────────┤
                                                              ▼
                                       Agent Worker (Python, VPS) — agent.py
                                       Soniox STT (stt-rt-v5)
                                       OpenAI LLM (gpt-4o-mini)
                                       Soniox TTS (tts-rt-v1, voice Maya)
```

- **Transport:** LiveKit Cloud (`wss://bizbull-restaurant-cyeyyw0l.livekit.cloud`). No self-hosted
  media server in this project.
- **Echo:** handled by Cloud's telephony media path + trunk-level Krisp (`krisp_enabled` on the SIP trunk).
- **Latency:** STT/LLM/TTS all US-reachable; agent on a US-West VPS; `preemptive_generation=True`.

---

## Files Added

### `restaurant/voice_stack.py`
Factory functions `build_stt()` / `build_llm()` / `build_tts()` that construct the Soniox STT
(`stt-rt-v5`, `language_hints=["pa","en","hi"]`, language ID on), OpenAI `gpt-4o-mini`, and Soniox TTS
(`tts-rt-v1`, voice `Maya`, `language="pa"`). Kept as small factories so a future multi-tenant build
can vary voice/model per restaurant.

### `agent.py`
Main agent worker.
- `RestaurantAgent(Agent)` — `@function_tool` methods, per-session cart state.
- System prompt (English) with strict "respond in Punjabi-English code-mix" behaviour; menu injected at startup.
- `entrypoint()` builds the session from `voice_stack`, detects phone vs web via the SIP participant,
  uses `turn_detection="stt"`, `preemptive_generation=True`, and phone-specific endpointing/interruption tuning.
- Greeting via `session.say(..., allow_interruptions=False)` for the fastest first audio.
- `agent_name="restaurant-agent"`; HTTP port configurable via `AGENT_HTTP_PORT`.

### `token_server.py`
FastAPI token server for the web channel. `GET /token` mints a LiveKit JWT, dispatches
`restaurant-agent` to the room, and returns `{token, url, room, identity}` (url comes from
`LIVEKIT_URL`, so the web app follows whatever LiveKit project `.env` points at).

### `restaurant/menu.py`, `restaurant/orders.py`, `restaurant/reservations.py`
Menu data + lookup, in-memory order cart, and reservation logic (Phase 1; DB deferred).

### `scripts/setup_sip.py`
Creates/updates the LiveKit **Cloud** SIP inbound trunk (`krisp_enabled` via `KRISP_ENABLED=1`) and a
dispatch rule with `RoomAgentDispatch(agent_name="restaurant-agent")`.

### `scripts/test_call.py`
Places an outbound Twilio test call that bridges the callee to the Cloud SIP URI (`LIVEKIT_SIP_URI`).

### `web/`
React (Vite) front-end — one-button "Start Call" voice UI. Gets a token from the token server and
connects to the LiveKit URL returned by it.

### `deploy/restaurant-agent.service`, `deploy/restaurant-token.service`
systemd units for the agent worker and the web token server.

### `pyproject.toml`, `.env.example`, `.gitignore`
Dependencies (`livekit-agents`, `livekit-plugins-soniox`, `livekit-plugins-openai`, `fastapi`,
`uvicorn`, `python-dotenv`, `twilio`), env template (LiveKit Cloud + Soniox + OpenAI + Twilio), ignores.

### `docs/`
- `plan/01-overview.md`, `plan/02-architecture.md`, `plan/06-milestones.md`, `plan/07-twilio-sip.md`,
  `plan/08-web-app.md` — current overview, architecture, roadmap, phone path, web channel.
- `vps-config.md` — VPS ops: services, SIP IDs, env, shared-VPS "do not touch" inventory.
- `reference/` — captured Soniox + LiveKit knowledge (STT/TTS, turn detection, noise cancellation).

---

## What's NOT in This PR
- Database / order persistence and POS webhook (deferred).
- Multi-tenant per-restaurant config (the `voice_stack` factory is the seam for it later).
- Outbound calling (inbound only).
- Renaming the repo folder (`livekit-sarvam`) and the `sarvam.bizbull.ai` web domain — these are live
  infrastructure names left intentionally for a separate change.

---

## How to Test

```bash
# On the VPS
cd /opt/livekit-sarvam
git pull origin main
uv sync

# Imports
uv run python -c "import agent, token_server; print('OK')"

# Service
systemctl restart restaurant-agent
journalctl -u restaurant-agent -n 20 --no-pager   # expect: registered worker (wss://...livekit.cloud)

# Outbound test call (Twilio dials the number, bridges to the Cloud agent)
LIVEKIT_SIP_URI='sip:+15878175156@5qg9858y0ak.sip.livekit.cloud' \
  uv run python scripts/test_call.py +1XXXXXXXXXX
```

---

## Post-Merge: VPS Pull Command
```bash
cd /opt/livekit-sarvam && git pull origin main && uv sync && systemctl restart restaurant-agent restaurant-token
```
