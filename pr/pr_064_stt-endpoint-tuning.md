# PR 064 — Env-tunable Soniox STT endpoint detection (end-of-speech latency)

## Branch
`pr_064_stt-endpoint-tuning`

## What This PR Does
Fixes the long end-of-speech delay reported on live conversation. The session has
no explicit VAD, so a user turn can only commit once Soniox delivers a FINAL
transcript — and the Soniox plugin only finalizes when its server-side endpoint
model fires. That endpoint was running at plugin defaults: `max_endpoint_delay_ms`
= **2000ms**, `endpoint_sensitivity` unset. So every reply paid up to ~2s of
Soniox endpoint delay *before* the LiveKit turn detector and the 0.2–0.5s dynamic
endpointing window even started. This PR sets `max_endpoint_delay_ms` to a
1000ms default and makes both knobs env-tunable (with clamping to Soniox's valid
ranges so a bad env var can never crash the worker at startup).

## Files Added
### `tests/test_voice_stack.py`
Tests for the two new env helpers: defaults, env overrides, invalid-value
fallback, and clamping to Soniox's valid ranges (500–3000ms, -1.0–1.0).

### `localtesting.md`
Full local-testing runbook: the `AGENT_NAME` swap that isolates localhost
from the VPS worker, launch/verify/measure steps, and teardown + deploy
checklist for when testing is done.

### `turnwatchdog.md`
Plan + session-handoff doc for the follow-up work (PRs 065–067): why
end-of-speech still stalls 3.4–14s in noise (turn commit gated on Soniox
semantic endpointing), and the staged fix (latency-tracker repair, explicit
tuned VAD + Soniox sensitivity, EOU watchdog force-commit). Doc only — no
code from that plan is in this PR.

## Files Modified
### `restaurant/voice_stack.py`
- New `stt_max_endpoint_delay_ms()` — reads `SONIOX_MAX_ENDPOINT_DELAY_MS`
  (default **1000**), clamps to 500–3000 (STTOptions raises outside that range).
- New `stt_endpoint_sensitivity()` — reads `SONIOX_ENDPOINT_SENSITIVITY`
  (default **unset/None** = Soniox neutral), clamps to -1.0–1.0.
- `build_stt()` passes both into `soniox.STTOptions`.

### `.env.example`
Documents the two new vars under the Soniox section (delay set to the 1000ms
default, sensitivity left commented out / neutral).

### `docs/vps-config.md`
Adds both vars to the phone-tuning env table so they can be overridden on the
VPS without a code deploy.

### `restaurant/agent/worker.py` / `token_server.py`
Both now read the agent name from `AGENT_NAME` (default `restaurant-agent`,
so production is byte-for-byte unchanged). Setting a local-only name (e.g.
`restaurant-agent-local`) keeps local test calls off the VPS worker and
production calls off your laptop — see `localtesting.md`.

## Files Deleted
None.

## What's NOT in This PR
- No change to LiveKit-side endpointing (`PHONE_ENDPOINTING_MIN/MAX`) or the
  turn detector — those were already env-tunable and are not the bottleneck.
- No default for `endpoint_sensitivity` — start neutral; raise it (e.g. 0.3)
  via env only if real calls still feel slow. Going aggressive risks cutting
  off callers who pause mid-sentence (phone-number dictation especially).

## How to Test
```
uv run python -m pytest tests/test_voice_stack.py -q
uv run python -m pytest tests/ -q
```
Live: make a test call before/after and compare `transcript_delay` in agent
debug logs / TurnLatencyTracker analytics; tune via env:
```
SONIOX_MAX_ENDPOINT_DELAY_MS=800
SONIOX_ENDPOINT_SENSITIVITY=0.3
```

## Post-Merge: VPS Pull Command
`cd /opt/livekit-sarvam && git pull origin main && uv sync && systemctl restart restaurant-agent`
