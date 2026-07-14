# PR 068 — Watchdog Gap Fixes

## Branch
`pr_068_watchdog-gap-fixes`

## What This PR Does
Fixes findings 1–5 from the PR 067 deep audit (`watchdog_gaps.md`), all in
the EOU watchdog:

1. **Rescue latency (HIGH):** `commit_user_turn`'s silence flush only runs
   with detached audio, so with a live mic the rescue was 2.0s timer + 2.0s
   `transcript_timeout` ≈ 4–4.5s dead air. `_TRANSCRIPT_TIMEOUT_SEC` drops to
   1.0s (worst case ≈3s) and the module docstring's wrong "silence-flushes
   the STT" claim is corrected.
2. **Stale-final phantom turn (HIGH):** after a forced commit, Soniox's held
   final can arrive 5–30s later and the framework treats it as a NEW turn —
   observed live as a duplicate reply. The watchdog now resets the STT stream
   (`session.clear_user_turn()`) on the agent's thinking/speaking transition
   after a rescue, tearing down the Soniox WS so the held final dies at the
   socket. Skipped when a real final arrived in time (detected by probing
   `_audio_recognition._last_final_transcript_time` — the forced commit's
   interim promotion emits an event-bus final indistinguishable from a real
   one) or when the user started speaking again.
3. **Mid-utterance commit (MEDIUM):** the re-arm timer now slides on every
   non-empty interim, so the commit fires `timeout_sec` after the LAST token
   instead of the first — no more truncated turns while Soniox is still
   streaming text for VAD-missed speech.
4. **Watchdog death after VAD-missed turns (MEDIUM):** `_fired_this_turn`
   now also resets when a final transcript arrives, not only on a VAD
   "speaking" transition, so back-to-back VAD-missed utterances each get a
   rescue.
5. **Lifecycle hygiene (LOW):** the timer is cancelled on `session.on("close")`
   (a post-close fire made `commit_user_turn` raise inside an unawaited
   task), and the future returned by `commit_user_turn` gets a logging
   done-callback so its exceptions are no longer silently dropped.

## Files Added
### `watchdog_gaps.md`
The audit doc itself — findings 1–7 with source-level traces against
livekit-agents 1.6.5, verification notes, and the design rationale for the
STT-reset approach (why match-and-drop in the `is_final` handler cannot work,
why the reset anchors on the thinking transition, why the reconnect is safe).

## Files Modified
### `restaurant/channels/eou_watchdog.py`
All five fixes above. New state: `_pending_stt_reset`, `_fired_at`. New
handlers on `agent_state_changed` (the reset) and `close` (timer cancel).
Ordering note honored: the `is_final` branch clears interim state before
resetting `_fired_this_turn`.

### `tests/test_eou_watchdog.py`
Nine new tests: sliding deadline under streaming interims; re-arm via final
without a VAD transition; STT reset fires on thinking when the final is still
held; no reset when a real final was consumed, when the user speaks again
first, or when the watchdog never fired; close cancels the pending timer;
commit exceptions are logged not raised. `_FakeSession` grows
`clear_user_turn`, a future-returning `commit_user_turn`, the
`_last_final_transcript_time` probe target, and a `promoted_final` helper
(same event, no timestamp stamp — mirrors the real interim promotion).

### `turnwatchdog.md`
Part IV "where you are" updated: stack 060–067 merged, remaining work is the
`watchdog_gaps.md` findings.

## Files Deleted
None.

## What's NOT in This PR
- Finding 6 (`ws_connect` awaitable-context-manager hardening) — PR 069.
- Finding 7 (VAD threshold tuning for noise-extended `last_speaking_time`)
  and the out-of-scope items (menu-matching loop, turn-detector holds on
  short Punjabi replies) — tracked in `watchdog_gaps.md`, not code changes
  here.

## How to Test
```
uv run --with pytest python -m pytest tests/test_eou_watchdog.py -q
uv run --with pytest python -m pytest tests/ -q   # 4 known order-dependent failures pre-exist
```
Live (per `localtesting.md` and `watchdog_gaps.md` §verification): continuous
background noise near the mic, short replies ("ਹਾਂ ਜੀ"). Expect the
`forcing commit` warning followed by a reply in ≤ ~3.5s, and NO duplicate
reply when the stale final arrives later (a `resetting STT stream` warning
instead). Caveat: the forced-commit path has not yet been observed firing on
a real stall — the 2026-07-13 test call had Soniox finalizing every turn.

## Post-Merge: VPS Pull Command
`cd /opt/livekit-sarvam && git pull origin main && uv sync`
