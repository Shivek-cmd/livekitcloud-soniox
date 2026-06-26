# Sarvam STT Plugin Reference (LiveKit Agents)

> Source: LiveKit docs › Models › STT › Sarvam (`/agents/models/stt/sarvam`).
> Captured 2026-06-26. Update when the plugin or our pinned version changes.
> Our pinned version: `livekit-plugins-sarvam 1.6.3` (see `docs/vps-config.md`).

## Overview

Speech recognition for Indian languages, English, and code-mixed audio. For new
agents use `saaras:v3` and set the language explicitly.

Auth: `SARVAM_API_KEY` in `.env`.
Install: `uv add "livekit-agents[sarvam]~=1.5"`.

## Recommended baseline config (from docs)

```python
from livekit.plugins import sarvam

stt = sarvam.STT(
    language="en-IN",            # set expected input language explicitly
    model="saaras:v3",
    mode="transcribe",           # default
    sample_rate=16000,           # 16000 for Python streaming unless pipeline needs otherwise
    high_vad_sensitivity=True,   # detect softer/shorter utterances
    flush_signal=True,
)
```

## Parameters

| Param | Type | Default | Notes |
|---|---|---|---|
| `language` | LanguageCode | `en-IN` | `saaras:v3` supports the full set incl. `pa-IN`, `hi-IN`, `en-IN`, and `unknown` (auto-detect). |
| `model` | str | `saarika:v2.5` | Use `saaras:v3` — supports mode control + broadest languages. |
| `mode` | str | `transcribe` | v3 only. See modes below. |
| `sample_rate` | int | `16000` | Streaming input rate. Must be > 0. Python only. |
| `high_vad_sensitivity` | bool | — | `True` to detect softer/shorter utterances. Python only. |
| `flush_signal` | bool | — | Sends Sarvam `flush_signal` streaming option. Python only. |
| `input_audio_codec` | str | `audio/wav` | Encoding for streaming WS messages. Python only. |

### Modes (saaras:v3 only)

| Mode | Use |
|---|---|
| `transcribe` | Standard transcription in source language (default). |
| `translate` | Translate spoken input (to English). |
| `verbatim` | Preserve speaker's exact wording. |
| `translit` | Transliterated (Romanized) output. |
| `codemix` | Optimized for code-mixed speech (keeps English words in English). |

### Fine-grained VAD options (saaras:v3 only, Python only)

> Sent to Sarvam only when `model=saaras:v3`. If unset, Sarvam uses its own defaults.
> **Tune ONE at a time.** Changing several at once makes it hard to tell why the agent
> listens too early, misses short utterances, or waits too long to finalize a turn.

| Param | Meaning |
|---|---|
| `positive_speech_threshold` | Frame prob above this (0–1) = speech. |
| `negative_speech_threshold` | Frame prob below this (0–1) = silence. |
| `min_speech_frames` | Consecutive speech frames before opening a new segment. |
| `first_turn_min_speech_frames` | Speech frames needed to recognize the first user turn. |
| `negative_frames_count` | Silence frames in the window that close a segment. |
| `negative_frames_window` | Window size (frames) for counting silence toward end-of-speech. |
| `start_speech_volume_threshold` | Volume floor (dB); quieter frames ignored. |
| `interrupt_min_speech_frames` | Speech frames required before incoming audio is treated as a barge-in. |
| `pre_speech_pad_frames` | Frames kept ahead of detected speech start so the utterance start isn't clipped. |
| `num_initial_ignored_frames` | Frames discarded at the very start of the WS stream. |

## Troubleshooting (official)

- **Wrong language/script** → set `language` explicitly; for translation/translit/code-mix use `saaras:v3` + the right `mode`.
- **Short utterances missed** → try `high_vad_sensitivity=True`; if using fine-grained VAD, tune one value at a time.
- **No / delayed transcripts** → confirm participant is publishing audio; confirm Sarvam is the configured STT; use `sample_rate=16000` unless pipeline requires otherwise; **try disabling custom VAD options and retest with defaults.**

## Our project notes (Punjabi restaurant agent)

- We use `model=saaras:v3`, `mode="codemix"`, `language="unknown"` (auto-detect), `flush_signal=True` (PRs 017 + 019).
- Phone uses `sample_rate=8000` to match native SIP audio (PR 019); web uses `16000`.
- We set several fine-grained VAD params on phone (`num_initial_ignored_frames`, `interrupt_min_speech_frames`, `first_turn_min_speech_frames`, `min_speech_frames`). Docs explicitly warn against tuning many at once — see `docs/diagnosis/phone-call-quality.md`.
- We do **not** set `high_vad_sensitivity`.
