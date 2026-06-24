# System Architecture

## Dual-Channel Design

Two entry points — web browser and phone call — both converge on the same LiveKit room and the same agent worker. The user experience is identical regardless of channel.

```
┌─────────────────────────────────────────────────────────────────┐
│                        ENTRY CHANNELS                           │
│                                                                 │
│  WEB CHANNEL                    PHONE CHANNEL                   │
│  ──────────────                 ──────────────                  │
│  User (Browser)                 User (Phone)                    │
│       │                              │                          │
│       │ WebRTC (audio/video)         │ PSTN call                │
│       │                              ▼                          │
│       │                       Twilio Number                     │
│       │                              │                          │
│       │                              │ SIP trunk                │
│       │                              ▼                          │
│       │                    LiveKit SIP Service   ◄── (Docker)   │
│       │                              │                          │
│       │                              │ SIP participant          │
│       ▼                              ▼                          │
│              LiveKit Server (self-hosted, Docker)               │
│                         [Room created]                          │
└─────────────────────────────────────────────────────────────────┘
                                │
                                │ audio frames (WebRTC internally)
                                ▼
                    LiveKit Agent Worker (Python)
                                │
                    ┌───────────┼───────────┐
                    ▼           ▼           ▼
               Sarvam STT  Sarvam LLM  Sarvam TTS
               Saaras v3   Sarvam-30B  Bulbul v3
               (pa-IN)     (pa-IN)     (pa-IN)
                    │           │           │
                    └───────────┼───────────┘
                                │ audio frames
                                ▼
                    LiveKit Server (routes back)
                          │           │
                    WebRTC back    SIP back
                          │           │
                    Browser        Phone
```

---

## Component Breakdown

### 1. LiveKit Server
- Core media server — handles WebRTC signaling and media routing
- Runs in Docker with **host networking** (required for WebRTC)
- Embedded TURN server (no Coturn needed)
- Redis for multi-worker coordination
- Ports: 7880 (HTTP/WS), 7881 (RTC/TCP), 50000-60000 (RTC/UDP), 443 (TURN)

### 2. LiveKit SIP Service
- **Separate Docker container** — not bundled with LiveKit server
- Bridges Twilio ↔ LiveKit by translating SIP ↔ WebRTC
- Receives inbound SIP calls from Twilio, creates a SIP participant in a LiveKit room
- Dispatch rules decide which room the caller lands in
- Ports: 5060 (SIP/UDP+TCP), 5061 (SIP/TLS), 10000-20000 (RTP media)
- Connects to LiveKit server via API (same API key/secret)

### 3. Twilio (Phone Channel)
- Provides a phone number (Indian DID for `+91` number)
- Configured with a SIP trunk pointing to LiveKit SIP Service's public IP:5060
- Twilio IP ranges must be allowlisted on the SIP service
- No Twilio SDK in agent code — Twilio is purely a SIP relay

### 4. Web App (Web Channel)
- React frontend using `@livekit/components-react`
- User opens browser → clicks "Start Call" → joins LiveKit room via WebRTC
- Token generated server-side (Python/Node) and passed to frontend
- No phone number needed

### 5. LiveKit Agent Worker
- Python process using `livekit-agents` SDK
- Registers with LiveKit server on startup, waits for dispatch
- When any user joins (web or phone) → agent spawns into the same room
- **Same agent code handles both web and phone** — the transport is abstracted by LiveKit

### 6. Sarvam STT — Saaras v3
- WebSocket streaming for live transcription
- Language: `pa-IN` (Punjabi)
- Mode: `transcribe` (Punjabi in → Punjabi out)
- Alt mode: `code-mixed` for Punjabi+English

### 7. Sarvam LLM — Sarvam-30B
- OpenAI-compatible chat completions
- System prompt in Punjabi forces Punjabi-only responses
- 16K context window (`sarvam-30b-16k`)

### 8. Sarvam TTS — Bulbul v3
- HTTP streaming for lowest latency
- Language: `pa-IN`, speaker: `shubh` (default)
- Sample rate: 22050 Hz

---

## Call Flow — Web Channel

```
1. User opens web app
2. Frontend requests token from backend (POST /api/token)
3. Backend generates LiveKit access token
4. Frontend connects to LiveKit room via WebRTC
5. Agent worker detects new participant → joins room
6. Agent greets user in Punjabi (TTS)
7. User speaks → STT → LLM → TTS loop
```

## Call Flow — Phone Channel

```
1. User dials Twilio number (+91-XXXXXXXXXX)
2. Twilio routes call to LiveKit SIP Service via SIP trunk
3. SIP Service applies dispatch rule → creates room + SIP participant
4. Agent worker detects new SIP participant → joins room
5. Agent greets caller in Punjabi (audio sent back via SIP → Twilio → PSTN)
6. User speaks → STT → LLM → TTS loop (audio codec: G.711 µ-law / PCMU)
```

---

## Data Flow Timing (Target)

| Step | Web | Phone |
|---|---|---|
| Audio capture → STT | < 300ms | < 400ms (extra SIP hop) |
| STT → LLM first token | < 500ms | < 500ms |
| LLM → TTS audio start | < 200ms | < 200ms |
| **End-to-end TTFA** | **< 1s** | **< 1.1s** |

---

## Deployment Topology

```
VPS / Cloud VM
├── docker-compose.yml
│   ├── livekit         (LiveKit server — WebRTC)
│   ├── livekit-sip     (LiveKit SIP service — telephony)
│   └── redis           (shared session state)
├── Python env
│   └── agent.py        (agent worker — Sarvam pipeline)
└── Web backend
    └── token-server    (token generation API)
```

---

## What's Shared vs Channel-Specific

| Concern | Web | Phone | Shared |
|---|---|---|---|
| Transport | WebRTC | SIP→WebRTC | — |
| LiveKit room | ✓ | ✓ | ✓ |
| Agent code | ✓ | ✓ | ✓ same file |
| Sarvam STT/LLM/TTS | ✓ | ✓ | ✓ |
| Audio codec | Opus | G.711 PCMU | — |
| Frontend | React app | None (phone) | — |
| Token generation | Required | Not needed | — |
