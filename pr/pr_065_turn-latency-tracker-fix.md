# PR 065 — Turn Latency Tracker Fix

## Branch
`pr_065_turn-latency-tracker-fix`

## What This PR Does
Fixes `TurnLatencyTracker` so every user turn emits a `LATENCY` summary instead
of only the first one. The old slice lifecycle only began a new turn when
`user_final_at is None` / `turn_index == 0` — both permanently false after the
first turn, so a session logged exactly one summary (always labeled `turn=2`)
and we were blind on live latency after turn 1. This is the measurement
prerequisite for the noise-robust endpointing work (PRs 066–067, see
`turnwatchdog.md`). Also adds `transcript_delay` (user stopped speaking →
Soniox FINAL transcript arrived) to the summary line and the analytics dict —
this is the exact metric that showed the 5–14s stalls.

## Files Added
### `tests/test_turn_latency.py`
Fake-session tests: three consecutive turns each emit one `LATENCY` summary
with indices 1, 2, 3; slice resets between turns (no stale timestamps);
`transcript_delay` appears in both the log line and the `on_turn_latency`
dict; a final-transcript-first turn (final arrives before the user-state
listening transition) still opens a turn.

## Files Modified
### `restaurant/analytics/turn_latency.py`
- Turn lifecycle now uses an explicit `_turn_active` flag: a turn begins on the
  first signal of a new turn (user starts speaking, or a final transcript
  arrives with no active turn) and ends when the summary is emitted on agent
  `speaking`. The next turn's first signal starts a fresh slice, so turn
  numbering is 1, 2, 3… and every turn emits.
- `transcript_delay=<ms>` added to the `LATENCY` line and
  `transcript_delay_ms` to the `on_turn_latency` payload → flows into Supabase
  analytics unchanged via `worker.py:_on_turn_latency` →
  `SessionRecorder.attach_latency` (stores the whole dict).

## Files Deleted
None.

## What's NOT in This PR
- No endpointing/VAD tuning (PR 066) and no EOU watchdog (PR 067).
- No change to what Soniox/the framework does — this is observability only.

## How to Test
```
uv run python -m pytest tests/test_turn_latency.py -q
uv run python -m pytest tests/ -q   # 4 known order-dependent failures pre-exist
```
Live: run a local call per `localtesting.md`; every turn must print
`LATENCY turn=N … transcript_delay=…` with N incrementing.

## Post-Merge: VPS Pull Command
`cd /opt/livekit-sarvam && git pull origin main && uv sync`
