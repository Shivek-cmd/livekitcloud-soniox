# System Architecture

## High-Level Flow

```
User (Browser/App)
      |
      | WebRTC (audio)
      v
LiveKit Server (self-hosted, Docker)
      |
      | audio frames
      v
LiveKit Agent Worker (Python)
      |
      |---> Sarvam STT (Saaras v3, pa-IN)  --> Punjabi transcript
      |
      |---> Sarvam LLM (Sarvam-30B)         --> Punjabi response text
      |
      |---> Sarvam TTS (Bulbul v3, pa-IN)   --> Audio
      |
      | audio frames back
      v
LiveKit Server
      |
      | WebRTC
      v
User hears response
```

## Component Breakdown

### 1. LiveKit Server (Infrastructure)
- Runs in Docker with host networking
- Handles WebRTC signaling and media relay
- Embedded TURN server (no separate Coturn needed)
- Redis for multi-worker coordination
- Exposed ports: 7880 (HTTP/WS), 7881 (RTC/TCP), 50000-60000 (RTC/UDP), 443 (TURN)

### 2. LiveKit Agent Worker (Application)
- Python process using `livekit-agents` SDK
- Registers with LiveKit server, waits for dispatch
- On user join → spawns a job subprocess → joins the room
- Runs the STT → LLM → TTS pipeline
- Handles turn detection and interruptions automatically

### 3. Sarvam STT — Saaras v3
- Mode: `transcribe` (returns Punjabi text as-is)
- Alt mode: `code-mixed` (handles Punjabi-English mixing)
- Streaming via WebSocket for low latency
- Language code: `pa-IN`
- Sample rate: 16000 Hz

### 4. Sarvam LLM — Sarvam-30B
- OpenAI-compatible chat completions API
- System prompt written in Punjabi to keep responses in Punjabi
- Tool calling supported (for future features)
- Context window: 16K tokens (30b-16k variant)

### 5. Sarvam TTS — Bulbul v3
- 30 voices (16 female, 14 male)
- Default: `shubh` (male)
- HTTP streaming for low-latency output
- Sample rate: 22050 Hz
- Target language: `pa-IN`

## Data Flow Timing (Target)

| Step | Target Latency |
|---|---|
| Audio capture → STT result | < 300ms |
| STT result → LLM first token | < 500ms |
| LLM first token → TTS audio start | < 200ms |
| **End-to-end (TTFA)** | **< 1 second** |

## Deployment Topology

```
VPS / Cloud VM
├── docker-compose.yml
│   ├── livekit       (LiveKit server)
│   └── redis         (session state)
└── Python venv
    └── agent.py      (agent worker process)
```

The agent worker runs outside Docker (or as a separate container) and connects to the LiveKit server via its internal/external URL.
