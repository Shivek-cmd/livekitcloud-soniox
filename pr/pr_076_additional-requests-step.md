# PR 076 — Additional-requests step; kill per-dish spice interrogation

## Branch
`pr_076_additional-requests-step`

## What This PR Does
Step 3 of the human-conversation rebuild (refactor.md). Adds become frictionless
one-liners: `add_item` no longer refuses with NEEDS SPICE when a spiced dish is
ordered without a spice level — the item is added with spice unset. Spice,
allergies, and special instructions are collected in ONE natural wrap-up
question at the end of ordering ("additional requests"), enforced by a hard
gate, not the prompt: `record_allergies` is replaced by
`record_additional_requests`, `OrderSessionState.allergies_recorded` becomes
`additional_requests_recorded`, and the readback blocker demands the wrap-up
question before any readback/placement. When the wrap-up is recorded, code
(not the LLM) deterministically fills **Medium** on every spiced dish still
without a spice level — the existing "no preference = Medium" rule, applied
once. The same fill re-runs at `get_order_readback` so a spiced dish added
*after* the wrap-up can never reach placement spice-unset. Non-spice required
modifier groups (NEEDS INFO, e.g. curry choice in combos) still block —
genuine choices with no sane default.

## Files Added
None.

## Files Modified
### `restaurant/agent/gates.py`
`allergies_recorded` → `additional_requests_recorded` (keeps `allergy_note`);
the allergies blocker in `readback_blockers` becomes the additional-requests
blocker naming `record_additional_requests`.

### `restaurant/agent/core.py`
- `add_item`: NEEDS SPICE refusal deleted. Spice stated at add time still
  passes through (canonicalized; INVALID SPICE refusal kept for unparseable
  values); otherwise the item is added with spice unset.
- `record_allergies` → `record_additional_requests(response)`: sets
  `state.additional_requests_recorded`, stores the answer text as
  `allergy_note` (same `_NO_ALLERGIES_RE` "no" detection; still flows to
  Clover/n8n unchanged), then applies the Medium default via new
  `_apply_default_spice()`. Facts-style reply (RECORDED / SPICE DEFAULTED /
  ORDER NOW / GUIDE); GUIDE tells the LLM to apply specific spice mentions via
  `set_item_spice` first.
- `_apply_default_spice()`: fills `Medium` (via `_note_with_spice`) on every
  cart line where `menu_provider.item_has_spice_level` is true and the note
  has no spice word yet; bumps revision + invalidates readback if anything
  changed. Never overwrites an explicit spice. Also called from
  `get_order_readback` after blockers pass (late-add safety net).

### `restaurant/agent/prompt.py`
Flow section rewritten as the fixed checklist phrased as goals (items → one
final additional-requests question → pickup/delivery → name/phone → readback →
confirm), "the tools tell you what's still missing — trust them." NEEDS SPICE
dropped from TRUST TOOL RESULTS; `add_item` tool line says to pass
`spice_level` only when the customer already stated one and never to ask for
spice while taking items; `record_allergies` tool line replaced.

### `tests/test_agent_gates.py`
State field rename; allergies-blocker test → additional-requests-blocker test.

### `tests/test_agent_tools.py`
NEEDS SPICE test replaced by add-without-spice-succeeds; new tests: Medium
default fills only unset spiced items at `record_additional_requests`,
explicit spice never overwritten, late-added spiced dish defaulted at
readback; `record_allergies` tests renamed; `_complete_order` +
readback-refusal assertions updated. NEEDS INFO and spice-at-add tests
unchanged (still pass).

### `tests/test_agent_place_order.py`
`record_allergies("no")` call sites → `record_additional_requests("no")`.

### `scripts/dialogue_harness.py`
Expect key `allergies_recorded` → `additional_requests_recorded`.

### `tests/scenarios/*.json`
Reflowed to the new conversation shape: no mid-order spice question; one
wrap-up answer turn covering spice + allergies. Expect key renamed. New
scenario `no_spice_mentioned.json`: customer never mentions spice — order ends
with Medium filled by code and the wrap-up question still asked.

## Files Deleted
None.

## What's NOT in This PR
- Persona/prompt rewrite (Step 4) — only the flow section is touched.
- Readback verifier (Step 5), TTS phone enforcement (Step 6).
- `allergy_note` semantics downstream (Clover/n8n) unchanged.

## How to Test
```
PYTHONPATH=. uv run --with pytest pytest tests
uv run python scripts/dialogue_harness.py --out docs/eval/pr076
```

## Post-Merge: VPS Pull Command
`cd /opt/livekit-sarvam && git pull origin main && uv sync`
