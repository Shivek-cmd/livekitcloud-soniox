# System Architecture

## Overview

Phone (primary) and web both converge on the same **LiveKit Cloud** room and the same agent worker.
The agent runs on our VPS but connects **out** to LiveKit Cloud — there is no self-hosted LiveKit
server in this project anymore.

```
┌──────────────────────────────────────────────────────────────────┐
│                          ENTRY CHANNELS                            │
│                                                                    │
│  WEB CHANNEL                       PHONE CHANNEL                    │
│  ──────────────                    ──────────────                  │
│  User (Browser)                    User (Phone, Canada)            │
│       │ WebRTC                          │ PSTN                      │
│       │                                 ▼                           │
│       │                          Twilio (+15878175156)             │
│       │                                 │ SIP trunk                 │
│       ▼                                 ▼                           │
│                    LiveKit Cloud  (US West region)                 │
│                    - WebRTC media + SIP service                    │
│                    - trunk-level Krisp noise cancellation         │
│                    - [Room created per caller]                     │
└──────────────────────────────────────────────────────────────────┘
                                │  (agent subscribes over wss)
                                ▼
                    LiveKit Agent Worker (Python, on VPS)
                                │
                    ┌───────────┼───────────┐
                    ▼           ▼           ▼
                Soniox STT   OpenAI LLM   Soniox TTS
                stt-rt-v5    gpt-4o-mini  tts-rt-v1 (Maya)
                (US/EU/JP)   (US)         (US/EU/JP)
                    │           │           │
                    └───────────┼───────────┘
                                ▼
                    LiveKit Cloud routes audio back
                          │              │
                    WebRTC back       SIP back → Twilio → Phone
```

---

## Components

### 1. LiveKit Cloud
- Managed media server (WebRTC) + managed SIP service.
- Project: **Bizbull Restaurant** (`bizbull-restaurant-cyeyyw0l.livekit.cloud`).
- Handles echo cancellation on the telephony path; **trunk-level Krisp** NC cleans caller audio.
- Auto-routes media to the edge nearest the caller.

### 2. Twilio (phone)
- Provides the number `+15878175156`, relays inbound calls via SIP to the LiveKit Cloud SIP URI.
- Pure SIP relay — unaware of the agent or providers.

### 3. LiveKit Agent Worker (`agent.py`)
- Python `livekit-agents` process running on the VPS as a systemd service.
- Registers with LiveKit Cloud as `agent_name="restaurant-agent"` and waits for dispatch.
- One worker handles both phone and web (transport abstracted by LiveKit).
- Voice providers: `restaurant/voice_stack.py`.
- Session tuning (turn detection, endpointing, latency): `restaurant/session_config.py`.
- Per-turn latency logs: `restaurant/turn_latency.py`.

### 4. Soniox STT — `stt-rt-v5`
- Realtime streaming, `language_hints=["pa","en","hi"]`, automatic code-mix + language ID.

### 5. OpenAI LLM — `gpt-4o-mini`
- Streaming chat completions; system prompt drives Sierra's persona + order flow.

### 6. Soniox TTS — `tts-rt-v1`, voice `Maya`
- Punjabi (`pa`) primary; streams audio before sentence end for low latency.

---

## Call Flow — Phone

```
1. Caller dials +15878175156
2. Twilio routes the call via SIP to the LiveKit Cloud SIP URI
3. Cloud SIP applies the dispatch rule → creates a room + SIP participant
4. The "restaurant-agent" worker is dispatched → joins the room
5. Sierra greets (TTS) → audio back via Cloud → Twilio → PSTN
6. Caller speaks → Soniox STT → GPT → Soniox TTS loop
```

## Call Flow — Web

```
1. User opens the web app → requests a token from token_server.py
2. Browser connects to the LiveKit Cloud room via WebRTC
3. Agent worker joins the room → Sierra greets
4. Same STT → LLM → TTS loop
```

---

## Latency model (why this stack)

The dominant latency factor is **geography**: the agent talks to STT, LLM, and TTS on every turn.
With Soniox (US/EU/JP) + GPT (US) + the agent on a US VPS + LiveKit Cloud US West, a Canada caller's
pipeline stays in North America. `preemptive_generation=True` overlaps LLM work with listening.

> The earlier India-hosted stack put STT/LLM/TTS in India, forcing ~3 US↔India round-trips per turn —
> the root cause of the old latency. That stack has been removed.

---

## Deployment topology

```
LiveKit Cloud (managed)            VPS (/opt/livekit-sarvam)
├── WebRTC media                   ├── agent.py        → restaurant-agent.service (systemd)
├── SIP service + trunk            ├── token_server.py → restaurant-token.service (web)
└── per-caller rooms               └── .venv (livekit-agents + soniox + openai)

Twilio  → routes +15878175156 to the LiveKit Cloud SIP URI
```

See `../vps-config.md` for service definitions, SIP IDs, env, and ops commands.
