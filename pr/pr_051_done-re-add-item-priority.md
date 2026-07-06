# PR 051 — `_DONE_RE`'s bare "ਬਸ" swallowing a live item order

## Branch
`pr_051_done-re-add-item-priority`

## Problem (live call, 2026-07-06)

```
Caller: ਚਲੋ ਮਸਾਲਾ ਚਾ ਕਰ ਦੋ ਫਿਰ। ਬਸ ਇੱਕ ਮਸਾਲਾ ਚਾ ਕਰ ਦੋ ਨਾ।
        ("Okay make masala chai then. JUST make one masala chai, okay.")
Sierra: Any allergies or special instructions?
```

The masala chai order never made it into the cart — confirmed by the final
read-back only listing "two Palak Paneer and one Dal Makhani" and the caller
explicitly flagging it afterward ("ਚਾਇ, ਚਾਇ ਵੀ ਬੋਲੀ ਸੀ ਮੈਂ ਨੇ" — "I also said
chai").

Root cause: `_DONE_RE` (unanchored) matches "ਬਸ" anywhere in the utterance.
Here "ਬਸ ਇੱਕ" means "**just** one" (a quantifier), not the discourse "that's
it/done" the regex is meant to catch — but `detect_intent()` classified the
whole utterance `ORDER_DONE` anyway, verified directly. Same root defect class
as the `_NO_RE` bug (PR 047) and the `"allerg" in t` bug (PR 048): an
unanchored keyword match firing on a word being used in an unrelated
grammatical role.

`_add_item_with_action_cue()` (added in PR 042 for the analogous "ਨਹੀਂ ਨਹੀਂ,
ਕਰੋ" case) already correctly identifies "named dish + add-imperative" and
would classify this text `ADD_ITEM` — but it's checked in `detect_intent()`
*after* `_DONE_RE`, so it never got a chance to override it here (PR 042 only
made it win over the *later* negation check, not `_DONE_RE`).

## Fix

### `restaurant/conversation.py`
- Moved the `_add_item_with_action_cue(t)` check in `detect_intent()` to run
  **before** `_DONE_RE`, so a named dish + add-imperative wins over "done
  ordering" too, not just over bare negation.
- No changes to `_DONE_RE` or `_add_item_with_action_cue` themselves.

### `tests/test_conversation.py`
- `test_bas_as_quantifier_is_add_not_done` — reproduces the exact live-call
  text, asserts `ADD_ITEM`.
- `test_bare_bas_without_item_still_order_done` — confirms a bare "ਬਸ" (no
  dish/imperative) still means "that's it" (no regression).

Full existing suite re-verified — no other test's expectations changed.

## What's NOT in This PR

- Does not touch `_DONE_RE`'s other alternatives (`ਹੋ ਗਿਆ`, `ਔਰ ਨਹੀ`, `ਕੁਝ
  ਨਹੀ`, etc.) — only the specific confirmed "ਬਸ" failure.
- Does not do a full audit of every loose-substring intent regex in
  `conversation.py` — fixes the one confirmed live-call instance.

## How to Test

```bash
PYTHONPATH=. pytest tests/test_conversation.py tests/test_order_flow.py -q
```

Live: order an item using "ਬਸ ਇੱਕ X ਕਰ ਦੋ" ("just one X please") phrasing —
confirm it gets added instead of silently ending the order.

## Post-Merge: VPS Pull Command
`cd /opt/livekit-sarvam && git pull origin main && uv sync`
