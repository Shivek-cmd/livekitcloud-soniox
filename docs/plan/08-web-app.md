# Web App Plan

## Stack

| Layer | Choice | Reason |
|---|---|---|
| Framework | React + Vite | Fast setup, LiveKit has official React SDK |
| LiveKit UI | `@livekit/components-react` | Pre-built voice UI components |
| Token Backend | Python (FastAPI) or Node | Generates signed LiveKit tokens |
| Styling | Tailwind CSS | Rapid UI |

---

## How Web Channel Works

```
User clicks "Start Call"
    │
    ▼
Frontend: POST /api/token  ──►  Backend generates LiveKit token
                                (signs room name + identity)
    │
    ▼ token returned
    │
Frontend: LiveKitRoom connects via WebRTC
    │
    ▼
LiveKit Server creates/joins room
    │
    ▼
Agent worker detects participant → joins room → starts Punjabi conversation
```

---

## Frontend (React)

Minimal web app — one page, one button:

```tsx
// App.tsx (planned)
import { LiveKitRoom, VoiceAssistantControlBar, useVoiceAssistant } from "@livekit/components-react";

export default function App() {
  const [token, setToken] = useState<string | null>(null);

  const startCall = async () => {
    const res = await fetch("/api/token");
    const { token } = await res.json();
    setToken(token);
  };

  if (!token) {
    return <button onClick={startCall}>ਗੱਲਬਾਤ ਸ਼ੁਰੂ ਕਰੋ</button>; // "Start Conversation"
  }

  return (
    <LiveKitRoom
      serverUrl={import.meta.env.VITE_LIVEKIT_URL}
      token={token}
      connect={true}
      audio={true}
      video={false}
    >
      <PunjabiVoiceUI />
    </LiveKitRoom>
  );
}

function PunjabiVoiceUI() {
  const { state, audioTrack } = useVoiceAssistant();
  return (
    <div>
      <p>ਅਵਸਥਾ: {state}</p>  {/* "Status: [listening/speaking/thinking]" */}
      <VoiceAssistantControlBar />
    </div>
  );
}
```

---

## Token Backend (FastAPI, Python)

Token generation runs server-side — never expose API secret to frontend:

```python
# token_server.py (planned)
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from livekit.api import AccessToken, VideoGrants
import uuid, os

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"])

@app.get("/api/token")
async def get_token():
    token = (
        AccessToken(os.environ["LIVEKIT_API_KEY"], os.environ["LIVEKIT_API_SECRET"])
        .with_identity(f"user-{uuid.uuid4().hex[:8]}")
        .with_name("Web User")
        .with_grants(VideoGrants(room_join=True, room="punjabi-agent-room"))
        .to_jwt()
    )
    return {"token": token}
```

Run with: `uvicorn token_server:app --port 8080`

---

## Environment Variables (Frontend)

```env
# .env (Vite)
VITE_LIVEKIT_URL=wss://livekit.yourdomain.com
```

---

## Project Structure (Web App)

```
livekit-sarvam/
├── agent.py              # voice agent worker
├── token_server.py       # FastAPI token backend
├── web/                  # React frontend
│   ├── package.json
│   ├── vite.config.ts
│   └── src/
│       ├── App.tsx
│       └── main.tsx
└── docker/
    ├── docker-compose.yml
    ├── livekit.yaml
    └── sip-config.yaml
```

---

## Key npm Packages

```bash
pnpm add @livekit/components-react @livekit/components-core livekit-client
pnpm add react react-dom
pnpm add -D vite @vitejs/plugin-react typescript tailwindcss
```

---

## UI States to Handle

| Agent State | What to Show |
|---|---|
| `disconnected` | "Start Call" button |
| `connecting` | Loading spinner |
| `listening` | Mic icon pulsing (user's turn) |
| `thinking` | Spinner (LLM processing) |
| `speaking` | Audio waveform (agent speaking) |
| `error` | Error message + retry button |

---

## Phase 1 Minimum (No Custom UI)

For initial testing, use **LiveKit Agents Playground** (`https://agents-playground.livekit.io`):
- Enter server URL + API key + secret → generate token → connect
- No frontend code needed until Phase 3
