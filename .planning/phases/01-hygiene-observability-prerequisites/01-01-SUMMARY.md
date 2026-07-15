---
phase: 01-hygiene-observability-prerequisites
plan: 01
subsystem: voice-agent-hygiene
tags: [phone-echo, background-filter, stt, regression-tests, pytest]

# Dependency graph
requires: []
provides:
  - Content-word-aware echo overlap in `is_likely_phone_echo` (option-list answers no longer flagged as echo)
  - Meaningful-token background rescue in `is_likely_background_speech` (short declines like "No, thanks." no longer swallowed by TV-chatter regex)
  - `_question_pending()` predicate + single-drop reprompt safety net in the background-drop branch of the turn hook
affects: [phase-3-persona-rewrite]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Content-word gate: strip function-word stopwords before comparing an answer's tokens to the agent's question tokens, so answers that reuse question phrasing are still recognized as new content"
    - "Compute reusable token list once, before regex/heuristic checks, so short-reply rescues can run ahead of coarser pattern matches"

key-files:
  created: []
  modified:
    - restaurant/channels/phone_echo.py
    - restaurant/channels/phone_background.py
    - restaurant/agent/core.py
    - tests/test_phone_echo.py
    - tests/test_phone_background.py

key-decisions:
  - "_STOPWORDS excludes 'want' and 'ji'/'haan' by design — those carry answer content, not filler, per echo_gaps.md"
  - "Meaningful-token background rescue runs before _BACKGROUND_FRAGMENT_RE so short real replies win over the TV-chatter pattern; a rare background false negative is preferred over muting a real caller"
  - "Echo-drop branch left silent and unchanged (echo reprompts risk feedback loops) — only the background-drop branch gets the question-pending single-drop reprompt"

patterns-established:
  - "Pure predicate helpers (e.g. _question_pending) live in the channel filter modules, imported by core.py's turn hook — keeps the hook thin and the logic unit-testable"

requirements-completed: [HYG-01]

coverage:
  - id: D1
    description: "Option-list answers ('I would keep it spicy') are no longer flagged as phone echo, while true echo (verbatim + truncated) is still caught"
    requirement: "HYG-01"
    verification:
      - kind: unit
        ref: "tests/test_phone_echo.py#test_option_answer_not_echo"
        status: pass
      - kind: unit
        ref: "tests/test_phone_echo.py#test_true_echo_still_filtered"
        status: pass
      - kind: unit
        ref: "tests/test_phone_echo.py#test_truncated_echo_still_filtered"
        status: pass
    human_judgment: false
  - id: D2
    description: "'No, thanks.' is no longer dropped as background chatter, while TV junk ('thank you for watching', 'Thank you.') is still filtered"
    requirement: "HYG-01"
    verification:
      - kind: unit
        ref: "tests/test_phone_background.py#test_no_thanks_not_background"
        status: pass
      - kind: unit
        ref: "tests/test_phone_background.py#test_tv_thankyou_still_background"
        status: pass
    human_judgment: false
  - id: D3
    description: "A single background drop right after Sierra asks a question schedules a reprompt within ~1s instead of waiting for a streak of 3 drops"
    requirement: "HYG-01"
    verification:
      - kind: unit
        ref: "tests/test_phone_background.py#test_question_pending_predicate"
        status: pass
    human_judgment: true
    rationale: "The predicate and threshold-selection logic are unit tested, but the end-to-end phone reprompt timing (scheduled task firing ~0.6-1s after a drop right after a question) can only be confirmed on a live call, per the plan's optional manual verification step."

# Metrics
duration: 12min
completed: 2026-07-15
status: complete
---

# Phase 01 Plan 01: Turn-Filter False Positives Summary

**Content-word-aware echo overlap, meaningful-token background rescue, and a `_question_pending` single-drop reprompt safety net — fixing the two dropped-turn shapes documented in echo_gaps.md (PR 073)**

## Performance

- **Duration:** 12 min
- **Started:** 2026-07-15T05:18:00Z (approx, worktree spawn)
- **Completed:** 2026-07-15T05:30:30+05:30
- **Tasks:** 3
- **Files modified:** 5

## Accomplishments
- `restaurant/channels/phone_echo.py`: content-word gate (`_STOPWORDS` + per-agent-line content-token check) so an answer reusing the question's function words but adding new content ("I would keep it spicy") is no longer flagged as echo, while verbatim and truncated-prefix echo are still caught
- `restaurant/channels/phone_background.py`: `<=3`-token meaningful-token rescue runs before `_BACKGROUND_FRAGMENT_RE`, so "No, thanks." is recognized as a real decline instead of matching the "thanks" TV-chatter pattern; TV junk ("thank you for watching", "Thank you.") still drops
- `restaurant/channels/phone_background.py` + `restaurant/agent/core.py`: new pure `_question_pending()` predicate selects a reprompt threshold of 1 (vs. the existing streak-of-3) when the last agent line was a question, closing the dead-air gap for any future single false-positive drop
- Six new regression tests locking all three behaviors, plus the pre-existing PR 053 cases and echo cases confirmed untouched

## Task Commits

Each task was committed atomically:

1. **Task 1: RED — regression tests for the two dropped-turn shapes** - `5b7cd8a` (test)
2. **Task 2: GREEN — content-word echo overlap + meaningful-token background rescue** - `a06ea7e` (feat)
3. **Task 3: single-drop reprompt when a question is pending** - `8a7396a` (feat)

**Plan metadata:** (this SUMMARY commit, see below)

## Files Created/Modified
- `restaurant/channels/phone_echo.py` - added `_STOPWORDS` frozenset + content-word gate inside the per-agent-line overlap loop of `is_likely_phone_echo`
- `restaurant/channels/phone_background.py` - meaningful-token rescue moved ahead of `_BACKGROUND_FRAGMENT_RE`; new `_question_pending()` pure predicate
- `restaurant/agent/core.py` - background-drop branch now selects reprompt threshold (1 vs 3) via `_question_pending(self._recent_agent_lines)`
- `tests/test_phone_echo.py` - `test_option_answer_not_echo`, `test_true_echo_still_filtered`, `test_truncated_echo_still_filtered`
- `tests/test_phone_background.py` - `test_no_thanks_not_background`, `test_tv_thankyou_still_background`, `test_question_pending_predicate`

## Decisions Made
- `_STOPWORDS` deliberately excludes "want" and "ji"/"haan" — these carry answer content per echo_gaps.md, not filler; verified the set does not contain them
- Background rescue favors passing a turn over dropping it when ambiguous (per echo_gaps.md: "a rare background false negative just means the LLM answers once; a false positive mutes a real caller")
- Echo-drop branch intentionally left silent and unchanged — only background drops get the question-pending reprompt escalation, avoiding echo-reprompt feedback loops

## Deviations from Plan

None - plan executed exactly as written. All three tasks matched their `<action>` specs; no architectural changes, no missing critical functionality beyond what the plan already specified.

## Issues Encountered

None specific to this plan's scope. While running the full test suite (`uv run --with pytest python -m pytest tests/ -q`) for cross-file regression verification, 4 pre-existing failures were observed in files outside this plan's `files_modified` list (`tests/test_ambient_audio.py`, `tests/test_customer_info.py`) — confirmed via `git diff --stat` that this plan touched only `phone_echo.py`, `phone_background.py`, `core.py`, and the two target test files. These are logged in `deferred-items.md` and left untouched per the scope-boundary rule (the customer_info.py failures match the already-known parked "customer-name-menu-hint-bug", not started per prior user instruction).

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- HYG-01 requirement complete: the two documented false-positive shapes are fixed and regression-locked; the persona rewrite in a later phase can proceed without inheriting this dead-air risk
- Manual live-call verification (per the plan's optional `<verification>` step) was not performed in this automated execution — recommend a live test call before/alongside the persona-rewrite phase to confirm the ~1s reprompt timing end-to-end
- `deferred-items.md` in this phase directory tracks the two pre-existing, out-of-scope test failures for future triage

---
*Phase: 01-hygiene-observability-prerequisites*
*Completed: 2026-07-15*

## Self-Check: PASSED

- FOUND: restaurant/channels/phone_echo.py
- FOUND: restaurant/channels/phone_background.py
- FOUND: restaurant/agent/core.py
- FOUND: tests/test_phone_echo.py
- FOUND: tests/test_phone_background.py
- FOUND commit: 5b7cd8a (test)
- FOUND commit: a06ea7e (feat)
- FOUND commit: 8a7396a (feat)
