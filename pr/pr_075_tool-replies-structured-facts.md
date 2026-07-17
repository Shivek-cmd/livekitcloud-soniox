# PR 075 — Tool Replies: SAY EXACTLY → Structured Facts

## Branch
`pr_075_tool-replies-structured-facts`

## What This PR Does
Step 2 of the Human Conversation Rebuild (refactor.md). Mutating order tools
stop scripting the agent's speech. Instead of `SAY EXACTLY: "..."` cue cards,
every cart mutation now returns three lines of structured facts the LLM
phrases in its own words:

```
ADDED: 2 x ਬਟਰ ਚਿਕਨ (Butter Chicken), note: medium.
ORDER NOW: 2 x ਬਟਰ ਚਿਕਨ (Butter Chicken) [medium]; 1 x Garlic Naan. total=$34
GUIDE: confirm the add briefly in the customer's language using the exact dish
name and quantity above (quantity spoken as "two", never a digit), then keep
the order moving.
```

Facts must never be contradicted; phrasing is the LLM's. `total=` stays in the
facts on every reply so "how much?" is answerable without another tool call —
the no-price-on-phone policy lives in the prompt only (unchanged). This ships
BEFORE the persona prompt (Step 4) so scripts and persona freedom never
coexist contradictorily.

All money-path guarantees are untouched: `_resolve_menu_item` refusals
(AMBIGUOUS / NOT FOUND / NEEDS SPICE / NEEDS INFO / unavailable), gates,
revision-gated readback, additive-add guard.

## Files Added
### `restaurant/agent/facts.py`
`format_mutation_reply(mutation, cart)` (head + ORDER NOW + GUIDE, per
mutation kind: added / merged / updated / removed) and
`format_cart_facts(cart, label=...)` (the ORDER NOW snapshot line, also used
with an `ORDER SO FAR` label by `get_order_summary`). Home of `_qty_word`
(moved from `replies.py`; used for the spoken-quantity hint in GUIDEs).
Gurmukhi/Devanagari voice_lines pass through untouched, with the English name
in parentheses for grounding.

### `tests/test_agent_facts.py`
Facts formatting: qty words, note rendering, Gurmukhi voice_line pass-through,
empty cart, whole-dollar totals, correction-vs-add wording, label override,
no name duplication when voice_line == name.

## Files Modified
### `restaurant/orders.py`
`add_item` / `remove_item` / `update_item_quantity` now return a
`CartMutation` dataclass (kind added|merged|updated|removed, name, voice_line,
resulting line-total quantity, note) or the unchanged error/refusal string
(unavailable, not-found). The `restaurant.agent.replies` import is gone —
orders.py no longer knows anything about speech. Web-RPC by-id paths
unchanged (they never used the returns).

### `restaurant/agent/core.py`
`add_item`, `set_item_quantity`, `remove_item` format `CartMutation` returns
via `format_mutation_reply`; `set_item_spice` (was an inline SAY EXACTLY) →
`SPICE SET:` + ORDER NOW + GUIDE; `get_order_summary` → `ORDER SO FAR (state
ONLY these items — never from memory): …` + GUIDE (the per-reply phone price
warning is dropped — the channel prompt already owns that policy). Refusal
strings unchanged.

### `restaurant/agent/replies.py`
Deleted `format_add_tool_reply`, `format_remove_tool_reply`,
`format_update_tool_reply`, `confirm_items_added`, and the local `_qty_word`
table (now imported from `facts.py`). Readback/status formatters and canned
lines stay until Steps 4–6.

### `restaurant/agent/prompt.py`
Minimal touch: the "confirm like a cashier (\"Yes — one X and one Y\")"
exact-wording clause → "confirm using the exact dish names and quantities
from the tool's ORDER NOW line". The never-"I've added" rule stays.

### Tests
`tests/test_orders.py` rewritten for `CartMutation` returns (+ revision-bump
and refusal-string coverage); `tests/test_agent_replies.py` drops the deleted
formatter tests; `tests/test_agent_tools.py` reply assertions updated to the
facts pattern — all money-path assertions (refusals, additive-add guard,
revision invalidation, contact validation) unchanged.

## Harness (vs. baseline)
`docs/eval/pr075/` — full re-run, 8/8 machine-green. Notable diffs vs.
`docs/eval/baseline/`:
- **Phone price-ask now answered:** "How much will that be?" → "nineteen
  dollars ninety-nine cents" (baseline: "Sorry, I can't share prices right
  now"). Price is still never volunteered unasked in any transcript.
- Confirms are LLM-phrased but grounded: "Two Butter Chicken with medium
  spice, anything else?"; Punjabi "ਦੋ ਬਟਰ ਚਿਕਨ medium spice ਨਾਲ ਜੋੜ ਦਿੱਤੇ। ਹੋਰ
  ਕੁਝ?" — correct qty words + exact dish names.
- Corrections read as fixes, not adds: "Butter Chicken changed to one…".
- (Environment note, not a regression: `delivery_split_phone` logged a Clover
  customer-upsert HTTP 400 — fail-open, order still submitted.)

## What's NOT in This PR
No flow changes (per-dish spice interrogation still present — Step 3), no
persona prompt (Step 4), no readback change (still VERBATIM — Step 5), no
speech-guard deletion (Step 6).

## How to Test
```
PYTHONPATH=. uv run --with pytest pytest tests        # 285 passed
uv run python scripts/dialogue_harness.py --out docs/eval/pr075
```

## Post-Merge: VPS Pull Command
`cd /opt/livekit-sarvam && git pull origin main && uv sync`
