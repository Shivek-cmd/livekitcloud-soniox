# Soniox STT + TTS plugin guide (LiveKit Agents)

> Captured 2026-06-27 from LiveKit docs (`/agents/models/stt/soniox`, `/agents/models/tts/soniox`)
> and Soniox docs (`soniox.com/docs/tts/concepts/{supported-languages,voices}`, `/docs/tts/models`).
> Why we care: Soniox runs in **US / EU / JP** regions, so for North-America (Canada) callers this
> keeps the whole pipeline on-continent → low latency.

## Why Soniox is in this repo

Our customers are restaurants in **Canada**. The previous voice stack was **India-hosted**, so every
turn crossed the ocean (3×, once each for STT/LLM/TTS) — the root cause of phone latency. Soniox
offers **both STT and TTS** with **Punjabi** support and **US hosting**, cutting latency at the root
while keeping Punjabi. It is the sole voice provider for this project (see
`restaurant/voice_stack.py`).

## Install

```shell
uv add "livekit-agents[soniox]"        # or: uv pip install livekit-plugins-soniox
uv add "livekit-plugins-openai"        # GPT LLM for the Soniox stack
```

Auth: set `SONIOX_API_KEY` (Soniox console) and `OPENAI_API_KEY` in `.env`.

## STT — `livekit.plugins.soniox`

```python
from livekit.plugins import soniox

stt = soniox.STT(
    params=soniox.STTOptions(
        model="stt-rt-v5",                       # latest realtime model
        language_hints=["pa", "en", "hi"],       # Punjabi + English + Hindi code-mix
        enable_language_identification=True,
    )
)
```

Key `STTOptions`:
- **`model`** — `stt-rt-v5` (latest). Realtime streaming.
- **`language_hints`** — bias languages; code-mixing/mid-sentence switching is automatic.
- **`enable_language_identification`** — detect spoken language (default `True`).
- **`context`** — free-form text to bias domain vocab (e.g. menu item names) — useful later.
- **`enable_speaker_diarization`** — per-speaker labels (not needed for 1:1 phone).
- **`translation`** (`TranslationConfig`) — realtime one-way/two-way translation (not used).

## TTS — `livekit.plugins.soniox`

```python
from livekit.plugins import soniox

tts = soniox.TTS(
    model="tts-rt-v1",     # production realtime model (preview alias points here)
    voice="Maya",          # one voice speaks ALL 60+ languages
    language="pa",          # primary language; English/Hindi words handled in-line
)
```

Key params:
- **`model`** — `tts-rt-v1` (realtime; streams audio before the sentence ends → low latency).
- **`voice`** — speaker identity, language-agnostic. We start with **`Maya`** (warm, clear female).
  Other options: `Daniel`, `Adrian` (male), plus British/Australian-accented voices.
- **`language`** — ISO code of the input text. `pa` = Punjabi. Code-mix is handled automatically.

### Supported Indic languages (ISO codes)
`pa` Punjabi, `hi` Hindi, `gu` Gujarati, `bn` Bengali, `mr` Marathi, `kn` Kannada, `ml` Malayalam,
`ta` Tamil, `te` Telugu, `ur` Urdu — plus 50+ more. (Full list in source above.)

## Regions / latency

`tts-rt-v1` is deployed in **US, EU, and JP**. With our agent in **US West (Seattle)** and LiveKit
Cloud in **US West**, a Canada caller's audio path stays in North America end-to-end. This is the
core reason Soniox beats an India-hosted stack for the Canada market.

## Telephony notes (to verify during testing)

- The LiveKit plugin handles audio frame production; LiveKit resamples for the SIP/telephony path.
  If narrowband phone audio sounds off, revisit explicit sample-rate/format handling.
- Soniox advertises accurate rendering of **alphanumerics (phone numbers, IDs)** — relevant for our
  digit-by-digit order/reservation confirmation flow.

## Open questions

- Punjabi **voice naturalness** of `Maya` — judge by ear on real calls; try other voices if needed.
- Whether `language="pa"` fixed at construction is ideal vs. switching per detected caller language.
- Code-mix rendering quality when a Punjabi sentence contains English brand/menu words.

## Menu item pronunciation (Clover + Punjabi)

Soniox TTS with `language="pa"` pronounces **Gurmukhi script** well but often **mispronounces Roman**
dish names (`Chole Bhature` spoken letter-by-letter or oddly). **Fix:** never send Roman Clover item
names to TTS for dish labels — use a separate **`speak_as`** Gurmukhi field in the menu cache
(same pattern as `punjabi` in `restaurant/menu.py`). Clover API still gets English `clover_name`.
See [clover-inventory-menu.md](clover-inventory-menu.md#punjabi-tts--clover-name-vs-gurmukhi-speech-label).
