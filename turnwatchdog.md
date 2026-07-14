# Noisy-Environment End-of-Speech Plan — Turn Watchdog + Endpoint Tuning

> **Read this first if you're a new session picking up the EOU-latency work.**
> Written 2026-07-11. Local branch stack: `pr_060…pr_063` (hybrid-brain rebuild,
> unmerged, see `refactor.md`) → `pr_064_stt-endpoint-tuning` (committed locally,
> not pushed). This doc plans PRs **065–067**.
> Companion docs: `refactor.md` (agent rebuild), `localtesting.md` (VPS-isolated
> local testing), `pr/pr_rules.md` (workflow), `docs/vps-config.md` (env).

---

## Part I — The problem (session handoff context)

### Symptom

During local testing of the hybrid agent (web channel, laptop speakers, agent's
ambient music audible), the gap between the caller finishing a sentence and
Sierra replying ran **5–14 seconds**. The framework's own measurement,
`transcript_delay` (user stops speaking → Soniox FINAL transcript arrives),
logged **3.4s / 4.3s / 6.1s / 7.8s / 9.7s / 14.1s** across six turns
(job `AJ_9T42wKzJ8qLP`, 2026-07-11). The caller literally asked Sierra why she
was so slow.

PR 064 (`pr/pr_064_stt-endpoint-tuning.md`) made Soniox's endpoint knobs
env-tunable (`SONIOX_MAX_ENDPOINT_DELAY_MS` default 1000, was 2000;
`SONIOX_ENDPOINT_SENSITIVITY` optional) — necessary, but **cannot explain or
fix delays >3s**, because 3000ms is the parameter's hard ceiling. Something
else stalls.

### Root cause (verified in livekit-agents 1.6.5 source, installed venv)

The pipeline is Soniox STT (`stt-rt-v5`, hints pa/en/hi) → GPT-4o-mini →
Soniox TTS, with LiveKit `TurnDetector(v1-mini)` and dynamic endpointing
0.2–0.5s (`restaurant/session_config.py`). The end-of-turn chain:

1. **A default Silero VAD IS active** — `AgentSession` auto-loads
   `inference.VAD(model="silero")` (backed by the native
   `livekit-local-inference` package, no silero plugin needed) when no `vad`
   kwarg is passed (`agent_session.py:453-456`). We pass none.
2. **But being the *default* VAD, the framework distrusts its timing**:
   `_using_default_vad=True` makes `audio_recognition.py` prefer STT token
   timestamps over VAD timestamps (`audio_recognition.py:1123,1183,1234`).
3. **A turn can NEVER commit before Soniox emits a FINAL transcript.**
   `_run_eou_detection` early-returns when STT is configured and no transcript
   text has accumulated (`audio_recognition.py:1352`). VAD END_OF_SPEECH fires,
   triggers EOU detection, and… returns. The 0.2–0.5s endpointing window and
   the v1-mini turn detector only run *after* the final arrives.
4. **Soniox finals are gated on its own semantic endpoint model** (`<end>`
   token → FINAL_TRANSCRIPT + END_OF_SPEECH, `plugins/soniox/stt.py:431-480`).
   Soniox endpointing uses "pauses, intonation, speech patterns, and
   conversational context" — NOT plain silence. `max_endpoint_delay_ms` caps
   the delay only *after the model believes speech ceased*. In continuous
   background audio (restaurant chatter, music, speaker echo of Sierra's own
   voice + ambient track), the model may not believe speech ceased for many
   seconds. **That belief is what stalled — the knob never engaged.**
5. **The framework HAS a rescue path, but never uses it automatically.**
   `_commit_user_turn` (`audio_recognition.py:929-1019`) pushes
   `stt_flush_duration` (2.0s) of silence frames to force Soniox to finalize,
   waits `transcript_timeout` (2.0s), and **falls back to the interim
   transcript** on timeout. It is reachable only via the manual public API
   `session.commit_user_turn(...)` (`agent_activity.py:1468-1483`) and the
   session-close path. Nothing calls it during live turns. **This is the lever
   the watchdog pulls.**

### Why this matters for the product

This agent's whole deployment context is noise: phone callers in kitchens and
dining rooms, and the agent itself plays `data/audio/restaurant_ambience.mp3`
into every call. "Works in a quiet room" is not the bar. Today the worst-case
end-of-speech delay is **unbounded** — one architectural hole, not a tuning
problem.

### External research (Soniox + LiveKit docs, 2026-07-11)

- Soniox endpoint params (v5 model): `max_endpoint_delay_ms` 500–3000 (default
  2000), `endpoint_sensitivity` -1.0–1.0 (default 0.0),
  `endpoint_latency_adjustment_level` 0–3 (default 0). Soniox's recommended
  voice-AI starting point: **level 2, sensitivity 0.3, max_delay 1500**.
  Soniox docs have **no noise-robustness guidance at all**.
- The installed plugin `livekit-plugins-soniox==1.6.5` (latest on PyPI as of
  2026-07-11) exposes only `max_endpoint_delay_ms` and `endpoint_sensitivity`
  (`STTOptions`, `plugins/soniox/stt.py:108-142`). **No
  `endpoint_latency_adjustment_level` field** — raw WebSocket API supports it,
  so exposing it requires config injection (see PR 066 stretch) or upstream PR.
- LiveKit guidance: always provide a VAD alongside the turn detector; Krisp
  agent-side noise cancellation recommended (we already run BVC/BVCTelephony
  on inbound, `session_config.py:build_room_options`); their noisy-telephony
  example raises VAD threshold to ~0.7.

### Bonus bug found: latency telemetry is broken

`restaurant/analytics/turn_latency.py` emits a `LATENCY` summary **once per
session** (always labeled `turn=2`). The single `_TurnSlice` is only reset by
`_begin_turn`, which is gated on `user_final_at is None` /
`turn_index == 0` — both permanently false after the first user turn
(`turn_latency.py:88-125`). All later turns emit nothing. Until this is fixed
we are nearly blind on live latency; fix it FIRST (PR 065).

---

## Part II — The plan (defense in depth, three staged PRs)

Next PR number: **065** (064 = endpoint env knobs, committed locally).
Workflow per `pr/pr_rules.md`: doc first, branch = doc name, never on main,
no push without the repo owner's explicit OK.

### PR 065 — `pr_065_turn-latency-tracker-fix` (measure before tuning)

`restaurant/analytics/turn_latency.py`:
- Fix slice lifecycle: begin a new turn on the first signal of a new turn
  (user starts speaking, or a final transcript arrives after a summary was
  emitted); reset the slice after `_emit_summary`. Every turn emits `LATENCY`;
  numbering 1,2,3….
- Add `transcript_delay` (user_stopped_at → user_final_at) to the summary line
  and the `on_turn_latency` dict → flows into Supabase analytics
  (`worker.py:_on_turn_latency` → `recorder.attach_latency`).
- New `tests/test_turn_latency.py`: fake session emitting 3 turns of
  (user speaking → listening → final → agent thinking → speaking); assert 3
  summaries, correct indices, slice resets.

### PR 066 — `pr_066_noise-robust-endpointing` (tune the stack for noise)

1. **Explicit, tuned VAD** — `restaurant/session_config.py`
   `build_agent_session`: pass
   `vad=inference.VAD(model="silero", activation_threshold=…, min_silence_duration=…)`.
   Env: `VAD_ACTIVATION_THRESHOLD` (default 0.6; lib default 0.5; LiveKit noisy
   example ~0.7) and `VAD_MIN_SILENCE_SEC` (default 0.25 = lib default).
   Passing it explicitly flips `_using_default_vad=False` → framework trusts
   VAD end-of-speech timing. VAD sees Krisp-BVC-cleaned audio.
2. **Soniox noise defaults** — `restaurant/voice_stack.py`: default
   `SONIOX_ENDPOINT_SENSITIVITY` unset→**0.3** (Soniox rec). Keep max delay
   default 1000. Empty env value must mean "explicit unset" (sentinel).
3. **Stretch — `endpoint_latency_adjustment_level=2`**: plugin doesn't expose
   it; inject by subclassing the Soniox stream where the WS config dict is
   built (`plugins/soniox/stt.py:264-275`). If brittle, SKIP and note as an
   upstream ask in the PR doc — do not fight the plugin.
4. **Probe harness** — `scripts/endpoint_noise_probe.py`: synth a test order
   phrase (macOS `say`, 16kHz LEI16), mix `data/audio/restaurant_ambience.mp3`
   at SNRs {clean, 10dB, 5dB}, stream real-time to Soniox + noise-only tail,
   print speech-end→FINAL delay per (sensitivity × max_delay) combo. A partial
   prototype existed in a session scratchpad (`endpoint_probe.py`) — key
   details: 20ms frames, real-time `asyncio.sleep` pacing, measure from last
   speech frame, cap wait at 8s. Soniox TTS synth for the clip failed
   (APIConnectionError) — use `say` instead.
5. Docs: `.env.example`, `docs/vps-config.md` tuning table.
6. Tests: env-helper tests (mirror `tests/test_voice_stack.py`); smoke test
   that `build_agent_session` receives an explicit VAD.

### PR 067 — `pr_067_eou-watchdog` (bound the worst case — the real fix)

New `restaurant/channels/eou_watchdog.py`, attached in
`restaurant/agent/worker.py` (same `.attach(session)` pattern as
`TurnLatencyTracker`):

- Listen to `user_state_changed` + `user_input_transcribed`.
- On user speaking → listening (VAD end-of-speech): start timer
  `EOU_WATCHDOG_SEC` (env, default **2.0**).
- Timer fires AND no final transcript since speech stopped AND user still
  `listening` AND agent not speaking/thinking →
  `session.commit_user_turn(transcript_timeout=2.0, stt_flush_duration=2.0)`
  → framework silence-flushes Soniox, falls back to interim transcript on
  timeout (`audio_recognition.py:960-992`). Turn proceeds instead of stalling.
- Guards: cancel on final transcript or user resuming speech; max one fire per
  turn; skip if no interim transcript exists (pure noise — nothing to commit);
  `EOU_WATCHDOG_SEC=0` disables (kill switch, like `AUTO_HANGUP_AFTER_ORDER`).
- Net: worst-case EOU latency ≈ 2.0s + flush, versus unbounded today.
- New `tests/test_eou_watchdog.py` with a fake session: normal fast final (no
  fire); late final (fires, commit called); user resumes (no fire); agent
  already speaking (no fire); disabled (no fire).

### Trade-offs accepted

- Sensitivity 0.3 + watchdog can clip a slow, pausing speaker (phone-number
  dictation is the risk case). Mitigations: watchdog only arms after VAD says
  speech ended; 2.0s is conservative; all knobs env-tunable per channel later;
  and the PR-060–063 gates (revision-gated readback, validating tools) catch
  any truncated transcript before an order is placed.
- Interim-transcript fallback may be slightly less accurate than a Soniox
  final — acceptable vs 14s dead air; the tools refuse unknown dishes anyway.

---

## Part III — Verification & rollout

1. `uv run python -m pytest tests/ -q` green at each PR boundary.
   **Known pre-existing failures (NOT ours):** 4 order-dependent failures in
   full-suite runs only (`test_ambient_audio` ×2 RuntimeError,
   `test_customer_info` ×2 name-parse) — they pass in isolation.
2. Probe matrix: `uv run python scripts/endpoint_noise_probe.py` (needs real
   `SONIOX_API_KEY` from `.env`). Expect: clean ≈ sub-second finals; 5dB shows
   the stall; sensitivity 0.3 improves it; watchdog bounds whatever remains.
3. Live local test per `localtesting.md` (AGENT_NAME swap so the VPS is never
   hit): one call on **headphones** (clean baseline), one on **speakers with
   ambient audible** (the noisy repro). Every turn must emit
   `LATENCY … transcript_delay=…`; noisy-case `user_stop→speaking` should stay
   ≤ ~3s (was 5–14s).
4. Rollout: deploy shadow-mode, compare `transcript_delay` distribution in
   admin analytics before/after; tune `VAD_ACTIVATION_THRESHOLD`,
   `SONIOX_ENDPOINT_SENSITIVITY`, `EOU_WATCHDOG_SEC` via VPS env (no code
   deploy needed).

---

## Part IV — Resuming in a new session

- **Where you are (updated 2026-07-13):** the whole stack 060–067 is MERGED
  to `origin/main` (#96, #97, #103–#106). Remaining work is the open audit
  findings in `watchdog_gaps.md` (watchdog rescue latency, stale-final
  phantom turn, re-arm/reset gaps, lifecycle hygiene) — read that doc first.
  **Nothing is pushed or deployed without the owner's explicit OK.**
- **Key measurement artifacts:** framework logs
  `received user transcript … transcript_delay=…` at DEBUG;
  `turn-latency` logger prints `LATENCY turn=…` lines (broken until PR 065 —
  only one line per session, labeled turn=2).
- **Env knobs after this plan:** `SONIOX_MAX_ENDPOINT_DELAY_MS`,
  `SONIOX_ENDPOINT_SENSITIVITY`, `VAD_ACTIVATION_THRESHOLD`,
  `VAD_MIN_SILENCE_SEC`, `EOU_WATCHDOG_SEC` (+ existing
  `PHONE_ENDPOINTING_MIN/MAX`, `PHONE_BVC_ENABLED`).
- **Do NOT**: re-tune only prompt/endpointing numbers and call it fixed (the
  stall is architectural — item 3 in Part I); remove the default VAD; call
  `commit_user_turn` while the agent is speaking; or push/deploy without the
  owner's OK.
- **Versions matter:** all file:line references are livekit-agents **1.6.5** /
  livekit-plugins-soniox **1.6.5**. If `uv sync` bumps these, re-verify
  `_run_eou_detection`'s no-transcript early return and the
  `commit_user_turn` signature before implementing.
