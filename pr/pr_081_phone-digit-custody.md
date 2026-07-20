# PR 081 — Gap 2: code-side phone digit custody + tool-side accumulation

## Branch
`pr_081_phone-digit-custody`

## What This PR Does
Closes **Gap 2** (money-path) from the monitored live call: the LLM is an
unreliable courier for phone digits — during the real failure it never called
`set_customer_contact` with a phone at all, stitched fragments mentally, and
kept re-asking. This PR moves digit custody into **code**: `on_user_turn_completed`
captures and accumulates digits before the LLM generates, and the tool itself
accumulates fragmented STT turns instead of replacing. `extract_phone_digits`
was already correct; the fix is *who owns the buffer*.

Behind `PHONE_DIGIT_CUSTODY` (default on; `0/false/off` rolls back).

## Files Modified
### `restaurant/customer_info.py`
- Extends `_PHONEISH` with danda `।॥`.
- New pure `phone_fragment_digits(text) -> str | None`: normalizes (Indic map +
  spoken-word→digit), strips punctuation, and returns the digit string only when
  every non-digit token is a known filler (`it's/is/my/number/haan/ਜੀ/ਹੈ/नंबर…`)
  and digits ≥ 2 — so "two samosas" → None.
- New pure reducer `accumulate_phone(buffer, utterance) -> (new_buffer, event)`
  with `event ∈ {saved, reset, append, repeat, none}`: full 10/11/12-digit hit →
  saved; correction phrase (`no/nahi/galat/ਨਹੀਂ/नहीं…`) → reset; restated fragment
  → repeat; overflow → reset; otherwise append (saved at exactly 10).
- New env accessor `phone_digit_custody_enabled()`.

### `restaurant/agent/core.py`
- `on_user_turn_completed` gains a phone-collection phase (`customer_name` set,
  `customer_phone` unset, `order_type` set) that runs the reducer on the
  transcript. **saved** → sets `cart.customer_phone` in code, clears buffer,
  `_sync_web()`, recorder event `phone_captured_code_side`, injects a system
  "PHONE CAPTURED AND SAVED … do NOT ask again" message. **append/reset** →
  injects "PHONE IN PROGRESS: N of 10 … ask only for the REMAINING digits". Never
  `raise StopResponse()` — the LLM still speaks the confirm/progress turn.
- `set_customer_contact` phone branch runs the same reducer against
  `state.phone_buffer`; at 10 → save; else `PHONE PARTIAL: have N of 10` guide.
  Now-unused `extract_phone_digits`/`_spoken_words_to_digits`/`_INDIC_NUMERAL_MAP`
  imports dropped from core.

### `restaurant/agent/gates.py`
- `OrderSessionState` gains `phone_buffer: str = ""`.

## Tests
- New `tests/test_phone_custody.py` (7): reducer sequences — single-shot save,
  `["80","770","39800"]` stitch to saved, repeat suppression, correction reset
  (`["80770","no, it's 90770","39800"]` → `9077039800`), overflow restatement;
  agent-level phase gating + PHONE CAPTURED / PHONE IN PROGRESS injections.
- `tests/test_customer_info.py` (+9): real-call vectors incl.
  `extract_phone_digits("It's 80770 39800.") == "8077039800"`, fragment/non-fragment cases.
- `tests/test_agent_tools.py`: tool-side partial-then-partial reaching saved
  (`test_contact_rejects_nine_digit_phone` updated to new "PHONE PARTIAL" wording).
- Full suite: **378 passed**.

## Deviations from Plan
- `set_customer_contact` phone branch fully replaced (not just the `not digits`
  sub-branch) — the whole branch runs through `accumulate_phone`; old PR 072
  "PHONE NOT SAVED: heard only N digit(s)" wording is gone.
- Correction words are allowed *inside* `phone_fragment_digits` so "no, it's 90770"
  yields a fragment for the reset rule; a bare "no" (no digits) → `none`, buffer
  unchanged (per the ≥2-digit floor).
- Pure functions live in `customer_info.py` (not core) so the money-path reducer
  stays import-light and unit-tested.

## What's NOT in This PR
- Live-verify of the fragmented-dictation custody path (silent when analytics off;
  verify via reducer + `ORDER_PLACED`) — deferred to the post-all-steps live call.

## How to Test
```
PYTHONPATH=. uv run --with pytest pytest tests -q
```
