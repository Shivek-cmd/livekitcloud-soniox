# PR 067 — EOU Watchdog

## Branch
`pr_067_eou-watchdog`

## What This PR Does
Bounds the worst-case end-of-speech latency — the real fix for the 5–14s dead
air measured on 2026-07-11 (`turnwatchdog.md` Part I). In livekit-agents 1.6.5
a turn can never commit before Soniox emits a FINAL transcript, and Soniox's
semantic endpoint model can sit on a final indefinitely under continuous
background noise. The framework already has a rescue path —
`session.commit_user_turn()` silence-flushes the STT and falls back to the
interim transcript on timeout — but nothing calls it during live turns. This
PR adds a watchdog that pulls that lever: if the VAD says the user stopped
speaking and no final transcript arrives within `EOU_WATCHDOG_SEC` (default
2.0), it forces the commit. Worst-case EOU latency becomes ≈2s + flush instead
of unbounded.

## Files Added
### `restaurant/channels/eou_watchdog.py`
`EouWatchdog` — same `.attach(session)` pattern as `TurnLatencyTracker`.
Listens to `user_state_changed` + `user_input_transcribed`:
- On user speaking → listening (VAD end-of-speech): arm an asyncio timer for
  `EOU_WATCHDOG_SEC`.
- Timer fires → force `session.commit_user_turn(transcript_timeout=2.0,
  stt_flush_duration=2.0)` **only if** all guards pass: no final transcript
  since speech stopped, a non-empty interim transcript exists (pure noise has
  nothing to commit), user still `listening`, agent not
  `thinking`/`speaking`, and the watchdog hasn't already fired this turn.
- Cancels on final transcript or the user resuming speech; the fired-flag
  resets when the user next starts speaking (max one fire per turn).
- `EOU_WATCHDOG_SEC=0` disables entirely (kill switch, same convention as
  `AUTO_HANGUP_AFTER_ORDER`).

### `tests/test_eou_watchdog.py`
Fake-session tests: normal fast final → no fire; late final → fires and
`commit_user_turn` called once with the plan's timeouts; user resumes speaking
→ no fire; agent already speaking/thinking at deadline → no fire; no interim
transcript (pure noise) → no fire; disabled via env → no handlers attached;
one fire max per turn, re-arms on the next turn.

## Files Modified
### `restaurant/agent/worker.py`
Attach `EouWatchdog` to the session right after `TurnLatencyTracker`.

### `.env.example`, `docs/vps-config.md`
Document `EOU_WATCHDOG_SEC`.

## Files Deleted
None.

## What's NOT in This PR
- No tuning changes (PR 066) and no upstream plugin work.
- Watchdog flush timeouts (2.0s/2.0s) are constants per the plan, not env
  knobs — add env only if live evidence demands.

## How to Test
```
uv run python -m pytest tests/test_eou_watchdog.py -q
uv run python -m pytest tests/ -q   # 4 known order-dependent failures pre-exist
```
Live (per `localtesting.md`): call on speakers with ambient audible; when
Soniox stalls, expect a `eou-watchdog … forcing commit` warning and the reply
to start ≈2s after you stop speaking instead of 5–14s.

## Post-Merge: VPS Pull Command
`cd /opt/livekit-sarvam && git pull origin main && uv sync`
