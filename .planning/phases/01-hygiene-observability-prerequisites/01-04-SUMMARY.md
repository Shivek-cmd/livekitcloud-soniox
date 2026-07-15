---
phase: 01-hygiene-observability-prerequisites
plan: 04
subsystem: testing
tags: [latency, observability, turn-tracking, pytest, livekit-agents]

# Dependency graph
requires: []
provides:
  - "TurnLatencyTracker._on_user_state starts a fresh turn slice on every genuinely new user utterance, including one that follows a filter-dropped turn"
  - "Regression test test_turn_after_dropped_turn_logs_fresh locking the dropped-turn-latency-gap fix"
  - "Ambient-audio test-hygiene fix (test-only, no product code change)"
affects: [phase-3-persona-rewrite (pacing measurement depends on per-turn latency being reliable across noisy/dropped-turn calls)]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Turn-boundary detection driven by slice state (user_final_at) rather than a mutable _turn_active flag, so a dropped turn (StopResponse, no agent thinking/speaking) cannot leak stale anchors into the next turn"

key-files:
  created: []
  modified:
    - restaurant/analytics/turn_latency.py
    - tests/test_turn_latency.py
    - tests/test_ambient_audio.py

key-decisions:
  - "Used the plan's primary approach (self-contained fix in turn_latency.py, no core.py change) rather than the contingency abandon_turn() approach — a new speaking transition reliably delimits utterances in this event model"
  - "Executed optional Task 3 (ambient-audio test-hygiene fix) since it was low-risk and did not affect Tasks 1-2"

patterns-established:
  - "A new user_state_changed 'speaking' transition always starts a fresh latency slice when the current slice already reached user_final_at, regardless of whether the prior utterance was emitted or dropped"

requirements-completed: [HYG-04]

coverage:
  - id: D1
    description: "Every turn that receives an agent response emits exactly one LATENCY line with its own fresh turn index and anchors, including a turn that follows a filter-dropped turn"
    requirement: "HYG-04"
    verification:
      - kind: unit
        ref: "tests/test_turn_latency.py::test_turn_after_dropped_turn_logs_fresh"
        status: pass
      - kind: unit
        ref: "tests/test_turn_latency.py (5 pre-existing tests: test_every_turn_emits_summary, test_transcript_delay_in_line_and_payload, test_slice_resets_between_turns, test_final_before_listening_still_opens_turn, test_interim_transcripts_do_not_open_turn)"
        status: pass
    human_judgment: false
  - id: D2
    description: "TurnLatencyTracker.attach is wired once per session at worker.py:83, unconditional on channel (phone or web)"
    requirement: "HYG-04"
    verification:
      - kind: manual_procedural
        ref: "Read-only source verification: restaurant/agent/worker.py line 83 calls TurnLatencyTracker(channel=channel, on_turn_latency=_on_turn_latency).attach(session) unconditionally, once per session, for both is_phone True and False"
        status: pass
    human_judgment: false
  - id: D3
    description: "(Optional, not HYG-04) Ambient-audio builder tests pass by constructing the player inside a running event loop"
    verification:
      - kind: unit
        ref: "tests/test_ambient_audio.py::test_build_web_ambient_player"
        status: pass
      - kind: unit
        ref: "tests/test_ambient_audio.py::test_build_phone_ambient_player"
        status: pass
    human_judgment: false

duration: 15min
completed: 2026-07-15
status: complete
---

# Phase 01 Plan 04: Fix dropped-turn latency-gap and verify worker wiring Summary

**Fresh-slice-per-utterance fix in TurnLatencyTracker so a filter-dropped turn (StopResponse) no longer leaks its stale anchor/transcript into the next responded turn's LATENCY line, plus a regression test and (optional) ambient-audio test-hygiene fix.**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-07-15T05:20:00Z (approx)
- **Completed:** 2026-07-15T05:24:00Z (approx)
- **Tasks:** 3 (2 required + 1 optional)
- **Files modified:** 3

## Accomplishments
- Reproduced the real production gap (dropped-turn latency merge) with a deterministic regression test that failed on current source before the fix (transcript_delay=2900ms instead of the correct 700ms)
- Fixed `TurnLatencyTracker._on_user_state`: a new `speaking` transition now starts a fresh slice whenever the current slice already reached `user_final_at`, regardless of whether the prior utterance was emitted normally or dropped by a channel filter — closing the observability gap for noisy phone calls where filter drops are common
- Verified (read-only) that `restaurant/agent/worker.py:83` attaches `TurnLatencyTracker` once per session, unconditionally for both phone and web channels — no gap there
- (Optional) Fixed the two always-failing `test_ambient_audio.py` builder tests by constructing the player inside a running event loop via `asyncio.run(...)` — test-only change, zero product code touched

## Task Commits

Each task was committed atomically:

1. **Task 1: RED — reproduce the dropped-turn latency gap with a real-ordering test** - `f868b7a` (test)
2. **Task 2: GREEN — fresh slice on each new user utterance + verify worker wiring** - `da90f86` (feat)
3. **Task 3: [OPTIONAL] fix always-failing ambient-audio tests** - `3b9d8f6` (fix)

**Plan metadata:** Not yet committed — worktree mode; `.planning/` is gitignored in this project (`commit_docs: false`, `.gitignore` line 13), so the SDK final-commit step is expected to report `skipped_gitignored`/`skipped_commit_docs_false` rather than force-adding this SUMMARY. The orchestrator handles the shared `.planning/` artifacts centrally after merge.

_Note: no TDD refactor commit was needed — Task 2's fix was a small, clean 11-line change with no follow-up cleanup required._

## Files Created/Modified
- `restaurant/analytics/turn_latency.py` - `_on_user_state` now starts a fresh slice on `speaking` when the current slice already has `user_final_at` set (prior utterance reached final, emitted or dropped)
- `tests/test_turn_latency.py` - new `test_turn_after_dropped_turn_logs_fresh` regression test (RED → GREEN)
- `tests/test_ambient_audio.py` - (optional) wrap `build_web_ambient_player()` / `build_ambient_player(is_phone=True)` calls in `asyncio.run(...)` so `rtc.AudioSource.__init__`'s `asyncio.get_event_loop()` fallback has a running loop, matching production's real call site inside `async def entrypoint`

## Decisions Made
- Used the plan's **primary approach** (self-contained fix inside `turn_latency.py`, keying off `user_final_at` rather than `_turn_active`) rather than the contingency `abandon_turn()` approach that would have required touching `core.py` and pushing this to wave 2. The existing synthetic-event test harness confirms a new `speaking` transition reliably delimits utterances between drops in this event model, so the contingency was not needed.
- Attempted and completed the optional Task 3 (ambient-audio test-hygiene fix) since it was low-risk, test-only, and did not touch Tasks 1-2's files.

## Deviations from Plan

None — plan executed exactly as written, including the optional Task 3.

## Issues Encountered

None. The full test suite (`uv run --with pytest python -m pytest tests/ -q`) shows 239 passed, 2 failed after this plan's changes — the 2 remaining failures (`tests/test_customer_info.py::test_parse_punjabi_name_with_filler_and_two_words`, `::test_parse_two_word_english_name`) are a **pre-existing, out-of-scope parked bug** (menu-hint fuzzy-match false positive, "Singh"→"single" — tracked separately in `current_fixes.md` PR 070 candidate) unrelated to HYG-04 and untouched by this plan's files.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- HYG-04 satisfied: per-turn latency is now observable on every responded turn, including turns following a filter-dropped turn on noisy phone calls — this unblocks measuring pacing regressions once the Phase 3 persona rewrite removes the turn-structure constraint.
- Worker wiring confirmed sound (no changes needed at `worker.py:83`).
- No blockers for Phase 2 (State Grounding) or Phase 3 (Persona Rewrite).

---
*Phase: 01-hygiene-observability-prerequisites*
*Completed: 2026-07-15*
