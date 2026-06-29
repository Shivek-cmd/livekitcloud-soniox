# LiveKit Turn Detection & Interruptions Reference

> Sources: LiveKit docs › Build Agents › Turn detection & interruptions
> (`/agents/logic/turns` and `/agents/logic/turns/tuning`). Captured 2026-06-26.
> This is the single most important reference for our "voice breaking / echo" problem.

## The pipeline stages that affect turn-taking

1. **User activity detection** — when has the user finished? (turn detection mode + endpointing delays)
2. **Interruption handling** — when can the user cut the agent off? (enable/disable, mode, thresholds, false-interruption recovery)
3. **Preemptive generation** — start LLM/TTS before the turn is confirmed (latency)
4. **Audio pre-processing** — noise cancellation / AGC cleaning input before the above
5. **Agent speech scheduling** — gap between the agent's own utterances

> Captured 2026-06-26; **our config updated 2026-06-27 (PR 008).** See `restaurant/session_config.py`.

## Our current production config (2026-06-27)

Implemented in **`restaurant/session_config.py`** via `TurnHandlingOptions` (livekit-agents 1.6.x).

| Channel | Turn detection | Endpointing | Preemptive | Interruptions |
|---------|----------------|-------------|------------|---------------|
| **Phone** | `TurnDetector(v1-mini)` + bundled Silero VAD | dynamic **0.2–0.5s** | LLM + TTS | adaptive, `min_words=2` (phone) |
| **Web** | `TurnDetector(v1-mini)` | dynamic **0.2–0.5s** | LLM + TTS | adaptive, `min_words=1` |

Env overrides: `PHONE_ENDPOINTING_MAX`, etc. — see `docs/vps-config.md` and `docs/HANDOFF.md`.

**History:**
- PR 005 used slow phone config (`stt`, 1.0s endpointing, no preemptive, no barge-in) for echo stability.
- PR 008 restored latency with TurnDetector + preemptive TTS while keeping `phone_echo.py` + Cloud Krisp.

Per-turn metrics: `journalctl … | grep LATENCY` (`restaurant/turn_latency.py`).

---

## Turn detection modes

| Mode | When to use |
|---|---|
| **Turn detector model** (`inference.TurnDetector()`) | **Recommended default.** Predicts end-of-turn from meaning + acoustics, on top of VAD. `AgentSession` enables the audio turn detector automatically. |
| Realtime models | Only with a realtime LLM (OpenAI Realtime / Gemini Live). |
| VAD only (`turn_detection="vad"`) | Minimal latency, or a language the turn detector doesn't cover. Needs Silero VAD plugin. |
| STT endpointing (`turn_detection="stt"`) | When STT has its own end-of-turn (AssemblyAI, Deepgram Flux). **"Less responsive to user interruptions." Docs say still provide a VAD plugin.** |
| Manual (`turn_detection="manual"`) | Push-to-talk / explicit control. |

~~> ⚠️ Our agent currently uses `turn_detection="stt"`…~~ **Superseded by PR 008** — see "Our current production config" above.

## Endpointing options (how long to wait after speech before replying)

| Option | Default | Notes |
|---|---|---|
| `endpointing.min_delay` | `0.5s` | Min time after detected silence before the turn closes. In STT mode this **adds to** the provider's endpoint signal. |
| `endpointing.max_delay` | `3.0s` | Max wait before forcing the turn closed. |
| `endpointing.mode` | `fixed` | `fixed` always uses the delays; `dynamic` adapts within range (Python). |

> ~~Our agent sets `min_endpointing_delay=0.2` (phone)…~~ **Superseded** — shared endpointing in `session_config.py` (default max **0.5s**, min **0.2s**, phone + web).

## Interruption options — KEY to the echo/voice-breaking issue

| Option | Default | What it does |
|---|---|---|
| `interruption.enabled` | `True` | Master toggle. `False` = agent is uninterruptible. |
| `interruption.mode` | `adaptive` if available, else `vad` | `adaptive` uses an audio model to tell real interruptions from backchannel ("uh-huh"). `vad` triggers on ANY detected speech. **`adaptive` is the default only for agents on LiveKit Cloud.** |
| `interruption.min_duration` | `0.5s` | Min speech duration to count as an interruption. |
| `interruption.min_words` | `0` | Min word count to count as an interruption. **Requires STT.** Set > 0 to require actual words before interrupting. |
| `interruption.false_interruption_timeout` | `2.0s` | After a detected interruption with no transcript (silence), wait this long, then classify it as a FALSE interruption. |
| `interruption.resume_false_interruption` | `True` | Resume the agent's speech from where it left off after a false interruption. |

### False interruptions (exactly our symptom)

> "The framework detects human speech audio and interrupts the agent, but the transcription
> comes up empty as no actual words are spoken. In these cases the VAD-based interruption is
> considered a false positive. By default, the agent resumes speaking from where it left off."

Levers: `resume_false_interruption=True` + `false_interruption_timeout`, and raise
`min_words` / `min_duration` so echo/noise can't trigger a barge-in in the first place.

Events to observe: `user_interruption_detected` (has `.probability`) and `agent_false_interruption`.

## Recommended starting config (from docs, newer API)

> Note: this uses the newer `TurnHandlingOptions` API. Confirm availability on our pinned
> `livekit-agents 1.6.3` before using — older versions set these params directly on `AgentSession`
> (e.g. `min_interruption_duration`, `min_endpointing_delay`). See diagnosis doc.

```python
from livekit.agents import AgentSession, TurnHandlingOptions, inference

session = AgentSession(
    turn_handling=TurnHandlingOptions(
        turn_detection=inference.TurnDetector(),
        endpointing={"mode": "fixed", "min_delay": 0.5, "max_delay": 3.0},
        interruption={"mode": "adaptive", "min_duration": 0.5, "min_words": 0},
        preemptive_generation={"preemptive_tts": False},
    ),
    # ... stt, tts, llm
)
```

## Troubleshooting matrix (official)

| Symptom | Likely fixes |
|---|---|
| Agent cuts users off mid-thought | Switch to turn detector model; raise `endpointing.min_delay`; `interruption.mode="adaptive"`; add voice isolation if cross-talk/noise. |
| Agent interrupted by short acks ("uh-huh", "okay") **— or by echo/noise** | `interruption.mode="adaptive"`; raise `interruption.min_words` (needs STT) or `min_duration`; keep `false_interruption_timeout` + `resume_false_interruption` at defaults so it resumes after silent false positives. |
| Agent feels too slow | Confirm `preemptive_generation` enabled; try `preemptive_tts=True`; lower `endpointing.min_delay`; try dynamic endpointing (Python). |
| Reads partial transcript / replies to incomplete input | Lower `preemptive_generation.max_speech_duration`; lower `max_retries`. |
| Turn detection misfires in noisy rooms | Add voice isolation (single speaker) or background noise suppression (multi-speaker). |
| Back-to-back utterances run together with no breath | `min_consecutive_speech_delay` ≈ `0.2`–`0.4s` (Python). |

## Preemptive generation (latency)

- `enabled` default `True` — start LLM as soon as a final transcript arrives, before the turn is confirmed.
- `preemptive_tts` default `False` — also start TTS early (more latency cut, wasted compute on cancels).
- `max_speech_duration` `10s`, `max_retries` `3`.
