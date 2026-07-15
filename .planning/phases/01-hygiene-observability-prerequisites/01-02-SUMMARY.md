---
phase: 01-hygiene-observability-prerequisites
plan: 02
subsystem: testing
tags: [customer-info, menu-matching, pytest, hermetic-tests, name-parsing]

# Dependency graph
requires: []
provides:
  - "_MENU_HINT_MIN_CONF confidence floor (0.8) gating the menu-item name veto"
  - "Hermetic tests/conftest.py autouse fixture (no test can lazily pin the production Clover cache)"
  - "Pinned fake-cache test harness for customer-name parsing regressions (mirrors test_menu_match.py's _item/_cache pattern)"
affects: [customer_info, menu_provider, agent-core-set_customer_contact]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Confidence-gated hints: menu-item detection heuristics used for precision (name veto) must check match_confidence, not mere presence, distinct from recall-oriented order-path matching"
    - "Hermetic pytest suite via autouse conftest fixture pinning module globals to a known static-menu baseline"

key-files:
  created:
    - tests/conftest.py
  modified:
    - restaurant/customer_info.py
    - tests/test_customer_info.py

key-decisions:
  - "Confidence floor set at 0.8, calibrated against the match-confidence ladder (1.0 exact, ~0.85-0.92 phonetic-full-coverage, 0.65 UNIQUE_SINGLE_CONF bug, 0.5 cache.search fallback)"
  - "Dropped 'my' alternative from the second _NAME_PATTERNS regex entry so English 'my name is <name>' routes through the existing _NAME_FILLER_RE filler-strip path instead of a single-token capture group that cannot hold multi-word names"

patterns-established:
  - "New tests requiring a specific menu-cache shape use a local pytest fixture (monkeypatch.setattr on menu_provider._cache/_cache_loaded) layered on top of the hermetic conftest autouse fixture, mirroring tests/test_menu_match.py's clover_cache fixture"

requirements-completed: [HYG-02]

coverage:
  - id: D1
    description: "Confidence floor (_MENU_HINT_MIN_CONF=0.8) added to _menu_item_hint_in_text so only high-confidence dish matches veto a customer-name candidate; the 0.65 flat single-token false positive ('Singh' -> 'Bhatura (single)') no longer fires"
    requirement: "HYG-02"
    verification:
      - kind: unit
        ref: "tests/test_customer_info.py#test_singh_name_survives_menu_hint"
        status: pass
      - kind: unit
        ref: "tests/test_customer_info.py#test_confidence_ladder_guard"
        status: pass
    human_judgment: false
  - id: D2
    description: "Dish answers to the name question are still rejected as names (precision survives the floor), in both English and Gurmukhi"
    requirement: "HYG-02"
    verification:
      - kind: unit
        ref: "tests/test_customer_info.py#test_dish_answer_still_rejected"
        status: pass
    human_judgment: false
  - id: D3
    description: "Gurmukhi and filler-prefixed English variants of 'Sandeep Singh' parse correctly, including the companion _NAME_PATTERNS fix for 'my name is <two-word name>'"
    requirement: "HYG-02"
    verification:
      - kind: unit
        ref: "tests/test_customer_info.py#test_singh_gurmukhi_variant"
        status: pass
      - kind: unit
        ref: "tests/test_customer_info.py#test_name_with_filler_prefix"
        status: pass
    human_judgment: false
  - id: D4
    description: "tests/conftest.py autouse fixture makes the suite hermetic and order-independent — no test can lazily pin the production Clover cache into module globals"
    requirement: "HYG-02"
    verification:
      - kind: unit
        ref: "tests/ full suite: both test_menu_match.py + test_customer_info.py orderings, 32 passed each"
        status: pass
      - kind: unit
        ref: "tests/test_menu_match.py tests/test_menu_browse.py tests/test_menu_cache_load.py tests/test_agent_tools.py -q: 58 passed, zero order-path regressions"
        status: pass
    human_judgment: false

duration: 35min
completed: 2026-07-15
status: complete
---

# Phase 01 Plan 02: Menu-Hint Precision Fix for Customer Name Parsing Summary

**Confidence-floor gate (`_MENU_HINT_MIN_CONF = 0.8`) on the menu-item name-veto heuristic, plus a hermetic pytest conftest and a companion `_NAME_PATTERNS` fix that together stop "Singh" (and similar single-token phonetic collisions) from being dropped as a customer name.**

## Performance

- **Duration:** ~35 min
- **Started:** 2026-07-15T00:33:44Z
- **Completed:** 2026-07-15T01:09Z (approx)
- **Tasks:** 3
- **Files modified:** 3 (1 created, 2 modified)

## Accomplishments

- `_menu_item_hint_in_text` now vetoes a name candidate only when `resolve_item_in_text` returns a match with `match_confidence >= 0.8` — the flat `UNIQUE_SINGLE_CONF = 0.65` "Singh" -> "Bhatura (single)" false positive no longer fires, while genuine dish answers (1.0 exact, ~0.85-0.92 phonetic-full-coverage) still veto correctly.
- New hermetic `tests/conftest.py` autouse fixture eliminates the order-dependence in the test suite caused by `restaurant/clover/client.py`'s import-time `load_dotenv()` lazily pinning the real production Clover cache into `menu_provider` module globals.
- New pinned fake-cache test harness in `tests/test_customer_info.py` (`singh_menu_cache` fixture, mirroring `tests/test_menu_match.py`'s `_item`/`_cache` helpers) deterministically reproduces the bug and its fix, independent of ordering or the real cache file.
- Auto-fixed a latent regression exposed by the confidence-floor change: `_NAME_PATTERNS`'s second entry was capturing the linking word "is" itself as the parsed name for "my name is `<two-word name>`" once "is" stopped being (accidentally) vetoed as a fake dish hint. Verified against both the pinned fake cache and the real production `data/menu_cache_bizbull.json`.

## Task Commits

Each task was committed atomically (TDD: RED -> GREEN -> regression):

1. **Task 1: RED — hermetic conftest + failing "Sandeep Singh" repro** - `e0d2af6` (test)
2. **Task 2: GREEN — confidence floor inside the menu-hint only** - `ca89e18` (fix)
3. **Task 3: precision-survival + suite regression tests** - `efb3b7a` (test)

_Note: This plan follows the RED/GREEN/REFACTOR TDD gate at the plan level (frontmatter has no explicit `type: tdd`, but each task carries `tdd="true"`); no REFACTOR commit was needed — the GREEN implementation required no cleanup pass._

## Files Created/Modified

- `tests/conftest.py` - New autouse fixture (`_no_real_menu_cache`) pinning `menu_provider._cache=None`, `_cache_loaded=True`, `USE_CLOVER_MENU=0` for every test
- `restaurant/customer_info.py` - Added `_MENU_HINT_MIN_CONF = 0.8`; gated `_menu_item_hint_in_text` on `match_confidence`; dropped the `my` alternative from the second `_NAME_PATTERNS` entry
- `tests/test_customer_info.py` - Added `singh_menu_cache` fixture (pinned fake `MenuCache` with "Bhatura (single)" and "Butter Chicken") and 5 new tests: `test_singh_name_survives_menu_hint`, `test_confidence_ladder_guard`, `test_singh_gurmukhi_variant`, `test_name_with_filler_prefix`, `test_dish_answer_still_rejected`

## Decisions Made

- **Confidence floor at 0.8:** Calibrated to sit strictly above `UNIQUE_SINGLE_CONF = 0.65` (the bug) and the `cache.search()` fallback confidence of `0.5`, while staying at or below genuine dish-match confidences (1.0 exact, ~0.85-0.92 phonetic full-coverage). Verified with `test_confidence_ladder_guard`, which pins the exact 0.65 score the floor is calibrated against so a future silent recalibration of the matcher (`restaurant/clover/match.py`) would be caught.
- **Default `1.0` for missing `match_confidence`:** The static-menu fallback path (`restaurant/menu.py`) returns plain dicts with no `match_confidence` key; defaulting to `1.0` preserves its existing (already-precise) substring-match behavior unchanged.
- **`_NAME_PATTERNS` fix (dropping "my"), not `_NAME_FILLER_RE` or `_clean_name_token`:** The regex's single-token capture group is structurally incapable of capturing a two-word name once the linking word ("is") is treated as the captured token. Removing "my" from the pattern's leading alternative routes English "my name is ..." entirely through `_NAME_FILLER_RE`'s existing "my name is" filler-strip, which already correctly handles both single- and multi-word names (proven by both the pinned fake-cache tests and a live-shape smoke test against the real Clover cache). The Hindi/Punjabi "mera naam (hai) X" structure (pattern1, and pattern2's "mera"/"ਮੇਰਾ" alternative) is untouched.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `_NAME_PATTERNS` captured the linking word "is" as the parsed name for "my name is `<two-word name>`"**
- **Found during:** Task 3, while validating `test_name_with_filler_prefix` (`parse_customer_name("my name is Sandeep Singh") == "Sandeep Singh"`)
- **Issue:** Before the confidence-floor fix, `_menu_item_hint_in_text("is")` happened to return `True` under ambient conditions (either the static menu's broad substring match, or the real cache's `cache.search()` fallback at 0.5), which accidentally vetoed the second `_NAME_PATTERNS` entry's captured group ("is") and let execution fall through to the correct `_NAME_FILLER_RE`-based filler-strip path. Once the confidence floor was raised to 0.8, "is" (confidence 0.5, or no match at all against the narrower pinned fake cache) stopped being vetoed, so `_clean_name_token("is")` returned `"is"` as a valid one-word name and `parse_customer_name` returned it immediately — before ever reaching the correct fallback logic. This also broke the pre-existing test `test_parse_customer_name_exact`'s `"my name is Shivek"` case in isolated verification (confirmed via direct script execution against the real production cache before committing the fix).
- **Fix:** Dropped the `my` alternative from `_NAME_PATTERNS`'s second regex entry (`(?:mera|my|...)` -> `(?:mera|...)`), so plain English "my name is ..." no longer matches this Hindi/Punjabi-oriented single-token-capture pattern at all, and instead is handled entirely by the existing (already correct, already tested) `_NAME_FILLER_RE` filler-strip path further down `parse_customer_name`.
- **Files modified:** `restaurant/customer_info.py`
- **Verification:** `test_name_with_filler_prefix` passes; re-ran `test_parse_customer_name_exact` (pre-existing, "my name is Shivek" -> "Shivek") and confirmed no regression; live-shape smoke test against the real `data/menu_cache_bizbull.json` cache confirmed both single- and two-word "my name is ..." inputs resolve correctly.
- **Committed in:** `efb3b7a` (Task 3 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - bug, directly exposed by this plan's own confidence-floor change)
**Impact on plan:** Necessary to satisfy the plan's own acceptance criteria (`test_name_with_filler_prefix`) and to avoid shipping a production regression on a very common phrasing ("my name is `<first> <last>`"). No scope creep — change confined to `restaurant/customer_info.py`, the only file this plan is scoped to modify besides the test files.

## Issues Encountered

None beyond the deviation documented above (which was investigated, root-caused, and fixed within the plan's own task 3, using direct script verification against both the pinned fake cache and the real production Clover cache before finalizing the test suite).

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `parse_customer_name` now reliably preserves "Singh"-suffixed and similar names under the real Clover cache (previously silently dropped to raw filler-laden strings via `set_customer_contact`'s fallback in `restaurant/agent/core.py:597`).
- Order path (`resolve_item_dict_from_text`, `restaurant/clover/match.py`, `restaurant/menu.py`, `restaurant/menu_provider.py`, `restaurant/agent/core.py`) is byte-identical — confirmed via `git diff --stat` after each task and a zero-regression run of `test_menu_match.py`, `test_menu_browse.py`, `test_menu_cache_load.py`, `test_agent_tools.py`.
- Test suite is now hermetic and order-independent — future phases adding menu- or customer-info-related tests can rely on `tests/conftest.py`'s static-menu baseline without needing to guard against ambient Clover-cache pollution.
- Full `tests/` suite is green except the 2 pre-existing, out-of-scope `test_ambient_audio.py` failures (tracked separately in `current_fixes.md` as the "PR 071 candidate" — not in this plan's `files_modified` scope, left untouched per the deviation scope boundary).
- No blockers for the next plan in this phase.

---
*Phase: 01-hygiene-observability-prerequisites*
*Completed: 2026-07-15*

## Self-Check: PASSED

All created/modified files verified present on disk (`tests/conftest.py`, `restaurant/customer_info.py`, `tests/test_customer_info.py`, this SUMMARY.md). All commit hashes verified present in `git log --oneline --all` (`e0d2af6`, `ca89e18`, `efb3b7a`, `d86414b`).
