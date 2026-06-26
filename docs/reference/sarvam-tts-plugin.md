# Sarvam TTS Plugin Reference (LiveKit Agents)

> Source: LiveKit docs › Models › TTS › Sarvam (`/agents/models/tts/sarvam`).
> Captured 2026-06-26. Update when the plugin or our pinned version changes.
> Our pinned version: `livekit-plugins-sarvam 1.6.3` (see `docs/vps-config.md`).

## Overview

Synthesizes Indian-language and English speech. For new agents use `bulbul:v3`,
set `target_language_code` explicitly, and pick a speaker compatible with the model.

Auth: `SARVAM_API_KEY` in `.env`.
Install: `uv add "livekit-agents[sarvam]~=1.5"`.

## Recommended baseline config (from docs)

```python
from livekit.plugins import sarvam

tts = sarvam.TTS(
    target_language_code="hi-IN",   # set the language explicitly
    model="bulbul:v3",
    speaker="shubh",
    speech_sample_rate=22050,       # 8000 ONLY for narrowband telephony
    pace=1.0,                       # start here, then tune by listening
    output_audio_bitrate="128k",
    output_audio_codec="mp3",
    min_buffer_size=50,
    max_chunk_length=150,
    send_completion_event=True,
)
```

## Parameters (commonly used)

| Param | Type | Default | Notes |
|---|---|---|---|
| `target_language_code` | LanguageCode | — | Set explicitly. Text sent must match this language/script. |
| `model` | str | `bulbul:v3` | Use `bulbul:v3` for new builds. `bulbul:v2` only if you need `pitch`/`loudness`/`enable_preprocessing`. |
| `speaker` | str | `shubh` (v3) | Must be compatible with model. See speaker list below. |
| `pace` | float | `1.0` | Speech rate multiplier. Range `0.3`–`3.0`. **Lower = slower.** |
| `temperature` | float | `0.6` | Output randomness `0.01`–`2.0`. v3 / v3-beta only. |
| `pitch` | float | `0.0` | `-0.75`–`0.75`. v2 payload. |
| `dict_id` | str | — | Custom pronunciation dictionary. **v3 only.** Good for names/brands/acronyms. |
| `loudness` | float | `1.0` | `0.5`–`2.0`. v2 payload. |
| `speech_sample_rate` | int | `22050` | Allowed: `8000,16000,22050,24000,32000,44100,48000`. Use `8000` only when downstream requires narrowband telephony. |
| `output_audio_bitrate` | str | `128k` | `32k,64k,96k,128k,192k`. Python only. |
| `output_audio_codec` | str | `mp3` | `aac,alaw,flac,linear16,mp3,mulaw,opus,wav`. Python decodes `mulaw`/`alaw` to 16-bit PCM. Python only. |
| `min_buffer_size` | int | `50` | Char length that triggers buffer flush. Range `30`–`200`. **Lower if agent waits too long before speaking.** |
| `max_chunk_length` | int | `150` | Max length for sentence splitting. Range `50`–`500`. **Lower if long LLM responses delay synthesis.** |
| `send_completion_event` | bool | `true` | Request explicit completion events for streaming. |
| `enable_preprocessing` | bool | `false` | Normalizes English words/numbers/dates. **v2 only.** |
| `enable_cached_responses` | bool | — | Cached responses beta. **v2 only.** |

## Speakers (bulbul:v3, Python plugin)

- **Female:** amelia, ishita, kavitha, kavya, neha, pooja, priya, ritu, roopa, rupali, shruti, shreya, simran, sophia, suhani, tanya.
- **Male:** aayan, aditya, advait, amit, ashutosh, dev, kabir, manan, rahul, ratan, rohan, **shubh** (default), sumit, varun.

bulbul:v2 — Female: anushka (default), arya, manisha, vidya. Male: abhilash, hitesh, karun.

## Troubleshooting (official)

- **Audio starts too slowly** → reduce `min_buffer_size` gradually; reduce `max_chunk_length` if long LLM responses delay synthesis; keep punctuation in generated text so TTS can split naturally; change one latency setting at a time.
- **Speech sounds rushed / slow / unnatural** → start `pace=1.0`, `temperature=0.6`, tune one setting at a time; split long LLM responses into shorter sentences before TTS.
- **Output format mismatch (phone)** → confirm `speech_sample_rate`, `output_audio_codec`, `output_audio_bitrate`. Phone often needs `8000` Hz, `mulaw`/`alaw`, or linear PCM.
- **Romanised Indic input reduces quality** → always send native script (Gurmukhi/Devanagari), never Roman transliteration.
- **Inconsistent pronunciations** → use `dict_id` (v3) for names/brands/acronyms.

## Our project notes (Punjabi restaurant agent)

- Native script rule already enforced in the system prompt (PR 018).
- We currently set `pace=0.95` on phone and `speech_sample_rate=8000` + `output_audio_codec="mulaw"` on phone (see `agent.py`). The `0.95` is a deliberate slow-down — revisit against the "slow voice" complaint (start from `1.0`).
- `min_buffer_size` / `max_chunk_length` are NOT set in our agent (using defaults). These are the first knobs for "audio starts too slowly".
