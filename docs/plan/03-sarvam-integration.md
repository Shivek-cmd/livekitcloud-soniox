# Sarvam AI Integration Plan

## API Key

Set environment variable: `SARVAM_API_KEY=<your_key>`
Base URL: `https://api.sarvam.ai`

## SDK Installation

```bash
# LiveKit plugin (recommended — includes STT + TTS + LLM)
uv add "livekit-agents[sarvam]~=1.5"

# Or standalone Sarvam Python SDK
uv add sarvamai
```

---

## 1. Speech-to-Text (STT)

**Model**: `saaras:v3` (speech-to-text-translate, best for live agents)
**Fallback**: `saarika:v2.5` (transcription only)

### Punjabi Configuration

```python
from livekit.plugins import sarvam

stt = sarvam.STT(
    language="pa-IN",
    model="saaras:v3",
    mode="transcribe",       # keeps output in Punjabi
    sample_rate=16000,
)
```

### Modes Available (v3 only)

| Mode | Use Case |
|---|---|
| `transcribe` | Returns audio in same language (Punjabi in, Punjabi out) |
| `translate` | Returns English translation |
| `code-mixed` | Handles Punjabi + English mix |
| `verbatim` | Exact speech without cleanup |
| `transliterate` | Returns Romanized Punjabi |

### API Details

- REST endpoint: `POST /speech-to-text`
- WebSocket: `/speech-to-text-streaming` (used by LiveKit plugin automatically)
- Supports: `audio/wav`, `audio/mpeg`, `audio/ogg`, `audio/webm`

---

## 2. LLM (Chat Completions)

**Models**:
- `sarvam-30b` — faster, good for conversational use
- `sarvam-30b-16k` — 16K context window
- `sarvam-105b` — more capable, slower
- `sarvam-105b-32k` — 32K context

### Configuration

```python
llm = sarvam.LLM(
    model="sarvam-30b-16k",
)
```

### System Prompt Strategy (Punjabi)

```python
system_prompt = """
ਤੁਸੀਂ ਇੱਕ ਮਦਦਗਾਰ ਵੌਇਸ ਅਸਿਸਟੈਂਟ ਹੋ। ਹਮੇਸ਼ਾ ਪੰਜਾਬੀ ਵਿੱਚ ਜਵਾਬ ਦਿਓ।
ਛੋਟੇ ਅਤੇ ਸਪੱਸ਼ਟ ਜਵਾਬ ਦਿਓ ਕਿਉਂਕਿ ਇਹ ਇੱਕ ਵੌਇਸ ਕਾਲ ਹੈ।
"""
# Translation: "You are a helpful voice assistant. Always reply in Punjabi.
# Give short, clear answers since this is a voice call."
```

### API Details

- OpenAI-compatible endpoint: `POST /chat/completions`
- Tool calling: supported (standard OpenAI format)

---

## 3. Text-to-Speech (TTS)

**Model**: `bulbul:v3` (recommended)

### Configuration

```python
tts = sarvam.TTS(
    target_language_code="pa-IN",
    model="bulbul:v3",
    speaker="shubh",          # male voice (default)
    speech_sample_rate=22050,
    pace=1.0,
)
```

### Available Voices (bulbul:v3)

| Gender | Voices |
|---|---|
| Female (16) | amelia, ishita, and 14 others |
| Male (14) | shubh (default), and 13 others |

> Note: Confirm `pa-IN` is a supported `target_language_code` for TTS at runtime. If not available, `hi-IN` is the closest fallback with natural Indian voice quality.

### API Details

- REST: `POST /text-to-speech`
- HTTP Streaming: `POST /text-to-speech-streaming` (used by LiveKit plugin)
- WebSocket: `/text-to-speech-ws`
- Output: WAV / PCM audio

---

## 4. Full Pipeline Snippet (Reference)

```python
from livekit.plugins import sarvam
from livekit.agents import AgentSession

session = AgentSession(
    stt=sarvam.STT(language="pa-IN", model="saaras:v3", mode="transcribe"),
    llm=sarvam.LLM(model="sarvam-30b-16k"),
    tts=sarvam.TTS(target_language_code="pa-IN", model="bulbul:v3", speaker="shubh"),
)
```

---

## Open Questions to Validate

- [ ] Is `pa-IN` a valid `target_language_code` for `bulbul:v3` TTS? (check Sarvam language docs)
- [ ] Does Saaras v3 handle Punjabi Gurmukhi script accurately?
- [ ] What is the WebSocket streaming latency for Saaras v3 on 16kHz audio?
- [ ] Does Sarvam-30B generate natural Punjabi or transliterated responses?
