# PR 082 — Gap 3: EOU watchdog absolute wall-clock cap

## Branch
`pr_082_eou-watchdog-cap`

## What This PR Does
Closes **Gap 3**: the end-of-utterance watchdog re-armed its 2.0s timer on
**every interim token**, so slow digit dictation slid the commit deadline
indefinitely while Soniox held the final — `transcript_delay` reached 16s on the
live call. This PR adds an **absolute wall-clock cap** measured from the VAD
end-of-speech, so a turn commits no later than `EOU_WATCHDOG_MAX_SEC` after the
user stops, no matter how the interims dribble in.

Behind `EOU_WATCHDOG_MAX_SEC` (default **4.0**; `0` disables → bit-for-bit
current behavior).

## Files Modified
### `restaurant/channels/eou_watchdog.py`
- New env accessor `eou_watchdog_max_seconds()` (`EOU_WATCHDOG_MAX_SEC`, default
  4.0, 0 disables).
- New fields `max_sec: float`, `_user_stopped_at: float`. On `"speaking"` →
  reset to 0.0 (existing stand-down); on `"listening"` → stamp `time.time()` then
  arm. A real STT final also resets `_user_stopped_at` so a following VAD-missed
  utterance gets a fresh budget instead of an instant fire.
- `_arm_timer()` now computes the delay: `delay = min(timeout_sec, max(0,
  _user_stopped_at + max_sec - now))`; `delay <= 0` → commit synchronously.
  `_watch()` takes the delay as a parameter. Downstream commit / STT-reset /
  rescue paths untouched.

## Tests
- `tests/test_eou_watchdog.py` (+7): interims sliding past the cap → exactly one
  `commit_user_turn` ≈cap after the listening transition (the 16s repro in
  miniature); cap disabled → existing slide test unchanged; user resumes
  "speaking" mid-cap → no fire; final mid-window restarts the budget; delay≤0
  immediate-commit path; env parsing default/invalid.
- Full suite: **385 passed**.

## Deviations from Plan
- `_maybe_commit`'s warning still logs `self.timeout_sec`, not the capped delay
  actually waited (plan said leave `_maybe_commit` untouched). Cosmetic; live-verify
  uses the `LATENCY`/`transcript_delay` lines.
- After a real final, `_user_stopped_at` is cleared to 0.0, so a following
  VAD-missed utterance re-arms with the cap inactive (effectively the full
  `timeout_sec` sliding budget); the 4s cap re-anchors on the next real VAD
  end-of-speech. Matches plan intent ("fresh budget, not an instant fire").

## Notes
Fully independent of the other gap-fix PRs. Synergy with PR 081: a force-committed
digit fragment lands in the phone buffer instead of being lost.

## How to Test
```
PYTHONPATH=. uv run --with pytest pytest tests -q
```
