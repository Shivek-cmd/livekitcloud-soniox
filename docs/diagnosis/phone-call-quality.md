# Diagnosis — Phone Call Quality (Slow Voice + Voice Breaking)

> Status: **DIAGNOSIS ONLY — no code changed.** Goal here is to find the root cause, not fix yet.
> Captured 2026-06-26 from LiveKit docs (turn detection, interruptions, noise cancellation,
> SIP troubleshooting) cross-referenced against our `agent.py` and `docs/vps-config.md`.

## The two reported symptoms

1. **Voice speaks too slowly on the phone.**
2. **Voice breaks / cuts out — mostly at the start of the agent's turn ("echo problem").**
   This is the painful one. Calls connect but don't flow like two humans talking.

---

## Symptom 2 (voice breaking, "echo") — PRIMARY ROOT CAUSE

### What's happening, in plain terms

On a phone call there is **no echo cancellation on the caller's audio coming back to us.**
The agent (Sierra) speaks → her TTS audio goes out over SIP → the PSTN/phone path reflects some
of it back → it arrives as the SIP participant's "microphone" audio → our STT/VAD hears it as the
caller speaking → the framework treats it as a **barge-in and cuts Sierra off**. It's worst at the
start of a turn (e.g. the greeting), because that's when Sierra is talking and the caller is silent,
so the only thing on the inbound channel is the echo of her own voice.

This is a textbook **false interruption / self-echo barge-in**. LiveKit's docs describe it exactly:
> "The framework detects human speech audio and interrupts the agent, but the transcription comes up
> empty as no actual words are spoken… considered a false positive."

Our own git history confirms we've been circling this for weeks:
- PR 006 echo-cancellation, PR 016 "raise phone VAD thresholds to suppress echo of Sierra's own TTS"
  (then **reverted** because high values broke call pickup), PR 017 "fix the echo loop".

### Why a month of tuning hasn't stuck — three structural reasons

**A. We're self-hosted, so the recommended fix (Krisp BVC) isn't available.**
LiveKit's headline answer to phone echo is *"Enable background voice cancellation (BVC) for your
agent."* But BVC / BVCTelephony and trunk-level `krisp_enabled` are **LiveKit Cloud-only** features.
We run our own LiveKit server (`devkey` on the VPS). So the entire Krisp path is off the table for us
as-is. (Details + the self-hosted alternative in `../reference/livekit-noise-cancellation.md`.)

**B. We're using the least interruption-robust turn-detection mode, with a key piece missing.**
`agent.py` sets `turn_detection="stt"`. Per LiveKit docs, STT-endpointing is explicitly *"less
responsive to user interruptions"* and you *"should still provide a VAD plugin for responsive
interruption handling."* **We provide no Silero VAD plugin.** So interruption detection is driven
purely by Sarvam's raw STT/VAD frames — which is exactly what the echo trips.

**C. We never enabled the framework's built-in false-interruption defenses.**
LiveKit has purpose-built knobs for "noise/echo interrupts the agent":
- `interruption.min_words` > 0 → require **actual transcribed words** before a barge-in counts.
  Echo usually transcribes as empty/garbage, so this alone kills most false interruptions.
- `interruption.min_duration` → require a longer burst before counting.
- `interruption.mode="adaptive"` → an audio model separates real interruptions from backchannel/echo
  (**caveat: adaptive is the Cloud default; on self-hosted it may fall back to `vad`** — to verify).
- `resume_false_interruption=True` + `false_interruption_timeout` → if it does cut, resume where it
  left off after a short silence.

Instead, we've been hand-tuning Sarvam's low-level VAD frame counts (`interrupt_min_speech_frames`,
`min_speech_frames`, `num_initial_ignored_frames`, …). The Sarvam STT docs **warn against tuning
several of these at once** ("makes it harder to understand why an agent… waits too long"). That's the
loop we've been stuck in: change frame thresholds → fix echo but break call pickup → revert.

### Ranked hypotheses for Symptom 2

| # | Hypothesis | Confidence | How to confirm |
|---|---|---|---|
| 1 | Self-echo barge-in / false interruption (agent hears own TTS, gets cut) | **High** | Log `user_interruption_detected` + `agent_false_interruption`; check `USER:` log lines during the greeting — if STT logs fragments while only Sierra is talking, confirmed. |
| 2 | `turn_detection="stt"` + no Silero VAD makes interruptions fragile | **High** | Compare a test run with a VAD plugin added + turn detector model. |
| 3 | No `min_words` / false-interruption resume configured | **High** | Code review (confirmed absent in `agent.py`). |
| 4 | RTP network quality (packet loss/jitter) on the SIP path | **Medium** | `tcpdump` on VPS SIP RTP ports (20000–30000), analyze in Wireshark; loss >3% or jitter >20ms = breakup independent of echo. |
| 5 | TTS chunk/buffer gaps perceived as breakup | **Low–Med** | Try `min_buffer_size` / `max_chunk_length`; listen for gaps at sentence boundaries vs mid-word. |

> Mid-word breakup → interruption/echo (hyp. 1–3). Gaps only at sentence boundaries → TTS buffering
> (hyp. 5). Random crackle/static regardless of who's talking → network/codec (hyp. 4).

---

## Symptom 1 (voice too slow on phone) — likely causes

| # | Cause | Confidence | Note |
|---|---|---|---|
| 1 | `pace=0.95` on phone (deliberate slow-down in `agent.py`) | **High** | Docs say start at `1.0`. This is a direct, intentional slowdown only on the phone path. |
| 2 | Perceived slowness from start-up lag (TTS waits for buffer before first audio) | **Medium** | `min_buffer_size`/`max_chunk_length` not set (defaults). Docs "audio starts too slowly" → lower these. |
| 3 | `speech_sample_rate=8000` muffles voice → reads as "low quality/slow" | **Low** | 8000 is correct for narrowband SIP, but narrowband can feel sluggish. This is quality, not literal speed. |
| 4 | Wrong/unsuited voice — `shubh` default | **Subjective** | 14 male + 16 female v3 speakers available; worth A/B listening. User suspects the voice itself. |

> Note: "slow" can also be confused with **latency** (silence before Sierra answers). That's a
> different axis — see below — caused by LLM first-token time + endpointing, not by `pace`.

---

## Cross-cutting: latency ("not like two humans talking")

- **LLM first token (Sarvam-30B): 500–1400ms** is the single biggest latency contributor
  (`docs/plan/09-latency-analysis.md`). Streaming LLM→TTS and preemptive generation are the levers.
- `min_endpointing_delay=0.2` (phone) is already aggressive (default `0.5`). Pushing it lower trades
  "snappier" for "cuts the caller off."
- Preemptive generation (start LLM before turn fully confirmed) is the documented latency win — need
  to confirm it exists / is enabled on our pinned version.

---

## ✅ Version compatibility — VERIFIED (no upgrade needed)

Verified 2026-06-26 by inspecting the installed library on the VPS
(`/opt/livekit-sarvam/.venv/bin/python` → `inspect.signature(...)`). Pinned version: **`livekit-agents 1.6.3`**.

**All planned code-level fixes are available in 1.6.3 — no upgrade required.**

Confirmed on `AgentSession.say(...)`:
- `allow_interruptions` ✅ — enables the un-interruptible greeting fix.

Confirmed on `AgentSession.generate_reply(...)`:
- `allow_interruptions` ✅

Confirmed on `AgentSession.__init__(...)`:
- `allow_interruptions`, `min_interruption_duration`, `min_interruption_words` ✅ — core "stop only on real words" fix
- `false_interruption_timeout`, `resume_false_interruption`, `agent_false_interruption_timeout` ✅ — false-interruption recovery
- `discard_audio_if_uninterruptible` ✅
- `vad` ✅ — can add Silero VAD
- `turn_detection` (TurnDetectionMode) and `turn_handling` (TurnHandlingOptions) ✅
- `preemptive_generation` ✅ — latency fix (start LLM before turn confirmed)
- `min_endpointing_delay`, `max_endpointing_delay` ✅
- `min_consecutive_speech_delay` ✅
- `aec_warmup_duration: float | None = 3.0` ✅ — **built-in acoustic echo cancellation concept; investigate for phone echo**

Still to confirm (does not block the flat-param fixes above):
- Whether interruption **`mode="adaptive"`** (smart real-vs-echo detection, a Cloud default) functions on
  self-hosted, or falls back to `vad`. Note: `min_interruption_words` does NOT depend on adaptive mode —
  it only needs STT, which we have.

---

## Candidate fixes (PROPOSED — not applied; for the fix phase, one at a time)

> Methodology: change ONE variable per test call, keep the rest fixed, and log interruption events.
> Both the Sarvam STT docs and the LiveKit tuning docs insist on one-knob-at-a-time.

1. **Stop the greeting from being interruptible** (smallest, most targeted fix for "breaks at start"):
   make the opening `session.say(...)` non-interruptible (`allow_interruptions=False`). Directly
   addresses the most visible symptom while we work the deeper fix.
2. **Require real words before a barge-in**: set `min_interruption_words` > 0 (and/or raise
   `min_interruption_duration`). Echo transcribes as empty → no false interruption.
3. **Add Silero VAD + switch to the turn detector model** (instead of bare `turn_detection="stt"`),
   per LiveKit's recommended default. Re-test interruption robustness.
4. **Enable false-interruption resume** (`resume_false_interruption=True`, sane `false_interruption_timeout`).
5. **Reset Sarvam fine-grained VAD to defaults** and stop hand-tuning frame counts; let the framework
   layer handle turn-taking. Re-introduce individual VAD params only if a specific need remains.
6. **Voice/pace pass for Symptom 1**: set phone `pace` back to `1.0`; A/B a few v3 speakers; try
   lowering `min_buffer_size`/`max_chunk_length` for faster first audio.
7. **Network baseline**: capture RTP on the VPS during a bad call to rule in/out packet loss & jitter.
8. **If echo persists after 1–5**: evaluate **ai-coustics** voice isolation with our own license
   (the only self-hosted-compatible NC path) — see `../reference/livekit-noise-cancellation.md`.

## What to instrument first (before changing anything)

- Log `user_interruption_detected` (incl. `.probability`) and `agent_false_interruption` events.
- Keep the existing `USER:` / `SIERRA:` logging; specifically watch for `USER:` lines appearing while
  only Sierra is speaking (= echo being transcribed = confirms hypothesis 1).
- One real bad call with RTP capture for the network baseline.
