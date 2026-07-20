# PR 083 — Gap 7: cap phonetic-only ASCII single-token menu matches

## Branch
`pr_083_matcher-phonetic-cap`

## What This PR Does
Closes **Gap 7**: `phonetic_key` folds `butter` and `bhatura` both to `btr`, so a
lone ASCII token like `item_query="butter"` scored a phonetic-only match of 0.919
against Bhatura — above the 0.7 clarify gate — enabling a **silent wrong add**.
This PR caps confidence for phonetic-only ASCII single-token matches below the
clarify gate, routing them to the existing "did you mean?" disambiguation instead
of a silent add. Cart correctness stays in code.

## Files Modified
### `restaurant/clover/match.py`
- New constant `PHONETIC_ONLY_ASCII_SINGLE_CONF = 0.65` (< 0.7 clarify gate,
  > 0.55 floor so the match still surfaces for disambiguation).
- `best()` precomputes `single_ascii_query` (exactly one content token, `.isascii()`);
  after scoring, if `single_ascii_query and exact_tokens == 0`, caps confidence at
  0.65. Result: `add_item("butter")` → disambiguation branch, cart unchanged.
  Multi-token queries and exact ASCII token matches untouched.

## Tests
- `tests/test_menu_match.py` (+4): Bhatura added to the fixture cache;
  `find_item_scored("butter")` ≤ 0.65 (never ≥ 0.7 to Bhatura); regressions —
  "butter chicken" 1.0, descriptor phrase, "ਪਕੌੜਾ" unique-single, Gurmukhi
  variants, matra tests; a direct `MatchIndex` test with a Gurmukhi `speak_as`
  label present to lock in that the cap keys off the ASCII **query**, not the label.
- `tests/test_agent_tools.py` (+1): `add_item("butter")` → ⛔/AMBIGUOUS, cart unchanged.
- Full suite: **391 passed**. Live-repro: `find_item_scored("butter")` → Bhatura
  **0.65** (was 0.9189); "butter chicken"/"butter naan" → 1.0; "ਪਕੌੜਾ" → 0.9189
  (uncapped); "kheer" → 1.0.

## Deviations from Plan
- **Dropped the "matched label tokens are ASCII" sub-condition.** The real Bhatura
  carries a Gurmukhi `speak_as` ("ਭਟੂਰਾ") that also folds to key "btr"; a per-label
  ASCII check let that label re-surface the collision at 0.9189 uncapped — the live
  bug would NOT have been fixed. The cap now fires on `single_ascii_query and
  exact == 0` regardless of the matched label's script. Gurmukhi/Devanagari
  *queries* stay uncapped (their designed primary path, PR 032); exact ASCII token
  matches are never capped, so legitimate single-word English orders are untouched.

## Notes
The `_MENU_HINT_MIN_CONF=0.8` name-hint veto is unaffected by a 0.65 cap — verified green.

## How to Test
```
PYTHONPATH=. uv run --with pytest pytest tests -q
```
