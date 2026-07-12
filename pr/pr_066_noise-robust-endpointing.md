# PR 066 — Noise-Robust Endpointing

## Branch
`pr_066_noise-robust-endpointing`

## What This PR Does
Tunes the end-of-speech stack for the agent's real deployment context —
continuous background noise (restaurant chatter, the agent's own ambient
track). Three levers, per `turnwatchdog.md` Part II: (1) pass an **explicit,
tuned Silero VAD** so the framework trusts VAD end-of-speech timing instead of
waiting on STT token timestamps (`_using_default_vad=False`); (2) apply
Soniox's recommended voice-AI endpoint settings by default — sensitivity 0.3
and `endpoint_latency_adjustment_level=2` (the latter injected into the WS
config, since `livekit-plugins-soniox` 1.6.5 doesn't expose it); (3) a probe
harness that measures speech-end→FINAL delay under mixed restaurant noise so
tuning is evidence-based. The unbounded worst case is fixed in PR 067
(watchdog); this PR shrinks the common case.

## Files Added
### `scripts/endpoint_noise_probe.py`
Dev harness (not imported by the app). Synthesizes a test order phrase with
macOS `say` (16kHz mono PCM), mixes `data/audio/restaurant_ambience.mp3` at
SNRs {clean, 10dB, 5dB}, streams it to the Soniox WS API in real time (20ms
frames, `asyncio.sleep` pacing) with a noise-only tail, and prints the
last-speech-frame→FINAL delay per (sensitivity × max_delay × latency-level)
combo. Needs `SONIOX_API_KEY` in `.env` and `ffmpeg` for the mp3 decode.

### `tests/test_session_vad.py`
Env-helper tests for `VAD_ACTIVATION_THRESHOLD` / `VAD_MIN_SILENCE_SEC` and a
smoke test that `build_agent_session` passes an explicit VAD (monkeypatched
`inference.VAD` + `AgentSession` capture — no native model load in tests).

## Files Modified
### `restaurant/session_config.py`
- New `vad_activation_threshold()` (env `VAD_ACTIVATION_THRESHOLD`, default
  0.6 — lib default 0.5, LiveKit noisy-telephony example ~0.7) and
  `vad_min_silence_seconds()` (env `VAD_MIN_SILENCE_SEC`, default 0.25 = lib
  default), plus `build_vad()`.
- `build_agent_session` now passes `vad=build_vad()`. Passing any explicit VAD
  flips `_using_default_vad=False` in livekit-agents 1.6.5, making
  `audio_recognition.py` trust VAD END_OF_SPEECH timestamps. The VAD sees
  Krisp-BVC-cleaned audio (PR 022/`build_room_options`).

### `restaurant/voice_stack.py`
- `stt_endpoint_sensitivity()` default flips unset → **0.3** (Soniox's
  recommended voice-AI starting point). An explicitly empty/`none`/`unset`
  env value is a sentinel meaning "use Soniox server default" (returns None).
  Invalid values fall back to 0.3.
- New `stt_endpoint_latency_adjustment_level()`
  (env `SONIOX_ENDPOINT_LATENCY_ADJUSTMENT_LEVEL`, 0–3, default **2** per
  Soniox voice-AI rec; same empty-value sentinel disables injection).
- The plugin's `STTOptions` has no `endpoint_latency_adjustment_level` field,
  so `build_stt` returns a `_ConfigInjectingSTT(soniox.STT)` whose stream
  wraps the WebSocket and merges extra keys into the **first** JSON config
  message only (keepalives and audio untouched; per-connection flag resets on
  reconnect). If the extra-config dict is empty, behavior is byte-identical
  to the stock plugin. Upstream ask noted below.

### `tests/test_voice_stack.py`
Sensitivity default tests updated (unset → 0.3, sentinel → None, invalid →
0.3); new tests for the latency-level helper and the first-message-only WS
config injection (fake ws).

### `.env.example`, `docs/vps-config.md`
New knobs documented: `SONIOX_ENDPOINT_LATENCY_ADJUSTMENT_LEVEL`,
`VAD_ACTIVATION_THRESHOLD`, `VAD_MIN_SILENCE_SEC`; sensitivity default note
updated.

## Files Deleted
None.

## What's NOT in This PR
- The EOU watchdog that bounds the worst case (PR 067).
- No upstream plugin PR — `endpoint_latency_adjustment_level` support in
  `livekit-plugins-soniox` should be requested upstream; the injection here is
  a stopgap pinned to plugin 1.6.5 behavior (first `send_str` after
  `ws_connect` is the config message).

## How to Test
```
uv run python -m pytest tests/test_voice_stack.py tests/test_session_vad.py -q
uv run python -m pytest tests/ -q   # 4 known order-dependent failures pre-exist
uv run python scripts/endpoint_noise_probe.py   # needs real SONIOX_API_KEY
```
Live: local call per `localtesting.md` on speakers with ambient audible;
`LATENCY … transcript_delay=…` should stay well under the old 5–14s stalls.

## Post-Merge: VPS Pull Command
`cd /opt/livekit-sarvam && git pull origin main && uv sync`
