---
phase: 01-hygiene-observability-prerequisites
plan: 03
subsystem: order-taking / checkout
tags: [stt-normalization, phone-parsing, python, regex, punjabi, hindi, gurmukhi, devanagari]

# Dependency graph
requires:
  - phase: 01-hygiene-observability-prerequisites
    provides: "01-02 hermetic test fixtures (conftest.py autouse fixture isolating menu_provider cache) that this plan's tests build on"
provides:
  - "_spoken_words_to_digits helper in restaurant/customer_info.py normalizing English/romanized-Hindi-Punjabi/Gurmukhi/Devanagari spoken digit words + double/triple dictation prefixes to ASCII digits"
  - "extract_phone_digits accepts word-dictated phone numbers, not just ASCII digit strings"
  - "looks_like_phone_utterance recognizes word-dictated numbers as phone utterances"
  - "set_customer_contact reports captured digit count/value on extraction failure so the LLM can stitch a number dictated across turns"
affects: [checkout, agent-core, customer-contact-capture]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Whole-token spoken-digit-word normalization via re.split(r'(\\s+)', text) + tok.lower().strip('.,') key lookup (mirrors existing enforce_english_phone_in_speech technique) -- prevents substring false-matches like 'one' inside 'someone'"
    - "Length-gated safety net (len == 10/11/12 digits) preserved unchanged as the false-positive guard so non-phone utterances ('do samosa') still return None even after digit-word normalization"

key-files:
  created: []
  modified:
    - restaurant/customer_info.py
    - restaurant/agent/core.py
    - tests/test_customer_info.py

key-decisions:
  - "Cross-module import of private _spoken_words_to_digits and _INDIC_NUMERAL_MAP into core.py (existing codebase precedent: _question_pending is already imported privately from phone_background.py) rather than adding a new public wrapper function, since plan explicitly scoped Task 3 files to core.py + tests only (not customer_info.py)"
  - "Kept the len==10/11/12 length-gate in extract_phone_digits completely unchanged as the false-positive safety net; normalization only ever produces additional digit characters, never removes the safety net's precision"

requirements-completed: [HYG-03]

coverage:
  - id: D1
    description: "extract_phone_digits accepts English, romanized Hindi/Punjabi, and Gurmukhi/Devanagari spoken digit words (plus oh/double/triple dictation forms) and normalizes them to the correct 10-digit string"
    requirement: "HYG-03"
    verification:
      - kind: unit
        ref: "tests/test_customer_info.py#test_english_word_phone"
        status: pass
      - kind: unit
        ref: "tests/test_customer_info.py#test_mixed_digit_and_word_phone"
        status: pass
      - kind: unit
        ref: "tests/test_customer_info.py#test_oh_double_triple_forms"
        status: pass
      - kind: unit
        ref: "tests/test_customer_info.py#test_romanized_hindi_punjabi_phone"
        status: pass
      - kind: unit
        ref: "tests/test_customer_info.py#test_indic_script_word_phone"
        status: pass
    human_judgment: false
  - id: D2
    description: "Non-phone utterances and incomplete word-digit dictations are still rejected (False positive safety net intact); gates.py untouched"
    requirement: "HYG-03"
    verification:
      - kind: unit
        ref: "tests/test_customer_info.py#test_word_phone_negatives"
        status: pass
      - kind: unit
        ref: "tests/test_customer_info.py#test_looks_like_phone_utterance_word_digits"
        status: pass
    human_judgment: false
  - id: D3
    description: "Failed phone extraction yields an actionable reply reporting the captured digit count/value so the LLM can stitch a number dictated across turns"
    requirement: "HYG-03"
    verification:
      - kind: unit
        ref: "manual source assertion — restaurant/agent/core.py set_customer_contact phone-failure branch"
        status: pass
    human_judgment: true
    rationale: "The reply text format itself is verified by source inspection and a standalone digit-count computation check, not by exercising the full async Agent/tool-call path (would require constructing a live AgentSession) -- a human/live-call check (localtesting.md) is the final confirmation this loop is gone in practice, per the plan's own optional Verification step 3."

# Metrics
duration: 3min
completed: 2026-07-15
status: complete
---

# Phase 01 Plan 03: Checkout Phone-Digit Word Normalization Summary

**Word-dictated phone numbers (English/Hindi/Punjabi/Gurmukhi/Devanagari, plus "oh"/"double"/"triple" dictation forms) now normalize to digits at checkout, fixing the infinite phone-rejection loop from PR 072.**

## Performance

- **Duration:** 3 min
- **Started:** 2026-07-15T06:15:00+05:30
- **Completed:** 2026-07-15T06:17:42+05:30
- **Tasks:** 3
- **Files modified:** 3

## Accomplishments
- Added `_spoken_words_to_digits` helper normalizing whole-token spoken digit words (English, romanized Hindi/Punjabi, Gurmukhi, Devanagari) plus "double X"/"triple X" dictation prefixes to ASCII digits
- Wired the helper into `extract_phone_digits` (after the Indic-numeral translate, before the `\D` strip) and `looks_like_phone_utterance` (counts digits on normalized text) — ASCII behavior (10/11+1/12+91 digit forms) unchanged
- `set_customer_contact`'s phone-failure reply now reports the captured digit count/value so the LLM can stitch a number dictated across turns instead of blindly re-asking
- Full regression suite (`tests/` — 259 tests) green; `gates.py` untouched

## Task Commits

Each task was committed atomically:

1. **Task 1: RED — `_spoken_words_to_digits` helper + failing word-digit extraction tests** - `d99a909` (test)
2. **Task 2: GREEN — wire normalization into extraction + utterance detection** - `bf096eb` (feat)
3. **Task 3: actionable failure reply + negatives regression** - `9b09703` (fix)

_Note: TDD tasks — RED (d99a909) precedes GREEN (bf096eb) in git log, confirming the gate sequence._

## Files Created/Modified
- `restaurant/customer_info.py` - Added `_spoken_words_to_digits` + `_DOUBLE_TRIPLE_WORDS`; wired into `extract_phone_digits` and `looks_like_phone_utterance`
- `restaurant/agent/core.py` - `set_customer_contact` phone-failure reply now reports captured digit count/value
- `tests/test_customer_info.py` - 7 new tests: 5 word-digit extraction tests (RED→GREEN) + 2 negative/utterance-detection regression tests

## Decisions Made
- Imported the private `_spoken_words_to_digits` / `_INDIC_NUMERAL_MAP` symbols directly into `core.py` rather than adding a new public wrapper in `customer_info.py`, since Task 3's plan-scoped files were `core.py` + tests only. This mirrors an existing codebase precedent (`_question_pending` is already imported privately from `phone_background.py` into `core.py`).
- Left the `len == 10/11/12` length-gate in `extract_phone_digits` completely unchanged — it remains the sole false-positive safety net (e.g. "do samosa" → 1 digit → still `None`), and normalization only ever adds digit characters, never weakens this guard.

## Deviations from Plan

None - plan executed exactly as written. All three tasks (RED helper + tests, GREEN wiring, actionable-reply fix) match the plan's task definitions, acceptance criteria, and behavior specs precisely.

## Issues Encountered

One test-design correction during Task 1 authoring: the initial draft of `test_oh_double_triple_forms`'s "triple" assertion used a malformed word list that didn't sum to exactly 10 digits (would have silently passed via `or True`). Caught and fixed before running — replaced with a word list that resolves to a real, verifiable 10-digit dictation (`"triple five one three seven five two six eight"` → `"5551375268"`). Not a deviation from the plan (same behavior spec, corrected test data), just an authoring self-correction verified by running `_spoken_words_to_digits` directly on all seven behavior-spec inputs before committing.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- HYG-03 fully resolved: word-dictated phone numbers at checkout no longer trigger the infinite rejection loop; `restaurant/agent/gates.py` (readback/place-order validation) is untouched, so downstream gate behavior is unaffected.
- The plan's optional Verification step 3 (live/local call through localtesting.md to confirm the loop is gone in a real session) was not exercised in this executor run — flagged as `human_judgment: true` in the coverage block (D3) for a follow-up live-call check.

---
*Phase: 01-hygiene-observability-prerequisites*
*Completed: 2026-07-15*
