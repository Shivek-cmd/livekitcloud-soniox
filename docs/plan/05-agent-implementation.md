# Agent Implementation Plan

## Project Structure

```
livekit-sarvam/
├── .env                    # secrets (gitignored)
├── .env.example            # template for env vars
├── pyproject.toml          # deps via uv
├── agent.py                # main agent entrypoint
├── prompts/
│   └── system_pa.txt       # Punjabi system prompt
├── docs/
│   └── plan/               # this folder
└── docker/
    ├── docker-compose.yml  # LiveKit + Redis
    └── livekit.yaml        # LiveKit server config
```

---

## Dependencies

```toml
# pyproject.toml
[project]
name = "livekit-sarvam-agent"
version = "0.1.0"
requires-python = ">=3.10"

dependencies = [
    "livekit-agents[sarvam]~=1.5",
    "python-dotenv",
]
```

---

## agent.py (Planned Structure)

```python
import os
from dotenv import load_dotenv
from livekit.agents import AgentSession, Agent, RoomInputOptions, cli, WorkerOptions
from livekit.plugins import sarvam

load_dotenv()

SYSTEM_PROMPT = """
ਤੁਸੀਂ ਇੱਕ ਮਦਦਗਾਰ ਵੌਇਸ ਅਸਿਸਟੈਂਟ ਹੋ।
ਹਮੇਸ਼ਾ ਪੰਜਾਬੀ ਵਿੱਚ ਜਵਾਬ ਦਿਓ।
ਛੋਟੇ ਅਤੇ ਸਪੱਸ਼ਟ ਵਾਕਾਂ ਵਿੱਚ ਬੋਲੋ ਕਿਉਂਕਿ ਇਹ ਇੱਕ ਵੌਇਸ ਕਾਲ ਹੈ।
"""


class PunjabiVoiceAgent(Agent):
    def __init__(self):
        super().__init__(instructions=SYSTEM_PROMPT)


async def entrypoint(ctx):
    session = AgentSession(
        stt=sarvam.STT(
            language="pa-IN",
            model="saaras:v3",
            mode="transcribe",
            sample_rate=16000,
        ),
        llm=sarvam.LLM(model="sarvam-30b-16k"),
        tts=sarvam.TTS(
            target_language_code="pa-IN",
            model="bulbul:v3",
            speaker="shubh",
            speech_sample_rate=22050,
            pace=1.0,
        ),
    )

    await session.start(
        room=ctx.room,
        agent=PunjabiVoiceAgent(),
        room_input_options=RoomInputOptions(),
    )

    await session.generate_reply(
        instructions="ਯੂਜ਼ਰ ਦਾ ਸਵਾਗਤ ਕਰੋ।"  # "Welcome the user"
    )


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
```

---

## Running the Agent

```bash
# Install deps
uv sync

# Development (connects to local LiveKit)
python agent.py dev

# Production (connects to self-hosted LiveKit)
python agent.py start
```

---

## Turn Detection & Interruption Handling

LiveKit Agents handles this automatically:
- **End-of-utterance detection**: built-in VAD (voice activity detection)
- **Interruptions**: user can interrupt the agent mid-speech
- **Barge-in**: configurable sensitivity

No custom code needed for Phase 1.

---

## Frontend (Minimal Test Client)

For testing, use the LiveKit example token server + prebuilt React UI:
- LiveKit provides a hosted Playground at `https://agents-playground.livekit.io`
- Connect it to our self-hosted server using the API key + secret to generate a token
- No custom frontend needed for Phase 1 testing

---

## Conversation Quality Considerations

| Issue | Plan |
|---|---|
| LLM responds in Hindi/English | Force Punjabi via system prompt + temperature tuning |
| TTS mispronounces Punjabi words | Test multiple `speaker` values in bulbul:v3 |
| High latency | Use `sarvam-30b` (not 105b) for speed, enable TTS streaming |
| Code-mixed input (Punjabi + English) | Switch STT mode to `code-mixed` |
| User speaks Romanized Punjabi | Handle via `transliterate` mode + normalize before LLM |
