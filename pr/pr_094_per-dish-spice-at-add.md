# PR 094 — Spice level asked per dish, at add time

## Branch
`pr_094_per-dish-spice-at-add`

## What This PR Does
Brings the voice flow in line with the Store (web) flow: a dish whose Clover
menu entry has a **Spice Level** modifier group does not enter the order until
the customer has named a level. `add_item` refuses with `NEEDS SPICE`, Sierra
asks right there, the customer answers, Sierra re-calls `add_item` with
`spice_level` — and only then is the line in the cart. This is exactly what the
Store already does (`StoreTab.tsx` flips the card into a spice chooser instead
of adding, and `store_checkout.py` re-checks server-side), so the two channels
now agree.

This reverses the `add_item` half of **PR 076**, which deleted the `NEEDS SPICE`
refusal and moved spice into the closing additional-requests question with a
code-side Medium default. That made adds frictionless but left spice as a
silent default rather than a choice the customer actually made — and diverged
from the Store, where the choice is mandatory. The wrap-up question itself
stays (it still gates the readback) but is now **allergies + special
instructions only**; spice is settled by the time it is asked.

The "no preference = Medium" rule survives in two places: Sierra passes Medium
when the customer expresses no preference (`_canonical_spice` understands "no
preference", "koi bhi", "whatever"), and `_apply_default_spice()` stays as the
code-side safety net for adds that bypass the tool gate entirely — web-RPC taps
(`channels/web_sync.py`) above all. Nothing can reach Clover spice-unset.

## Files Modified

### `restaurant/agent/core.py`
- `add_item`: spice and non-spice required modifier groups are now evaluated
  together into **one** refusal, so a dish needing both (a combo with a curry
  choice) costs one question, not two. The refusal leads with the existing
  `_REFUSAL_PREFIX` (⛔). Nothing mutates: no cart change, no revision bump, no
  readback invalidation. The refusal also tells the LLM to ask about every
  spiced dish from the same turn in ONE question. It deliberately does **not**
  arm PR 081's `pending_add_refusals`: the harness showed Sierra saying "ਦੋ
  Butter Chicken ਲਿਖ ਲੈਂਦੀ ਹਾਂ — spice ਕਿੰਨਾ?", which trips the false-add-claim
  check, and strict mode would then speak "I don't have that on our menu" about
  a real dish that lands a turn later.
- New `_cart_line_has_spice(name)`: "one more of those" on a dish already in
  the order at a chosen level is **not** asked again — the line merges by name,
  and `spice` stays `None` so the existing note (including anything else in it)
  survives the merge.
- `_canonical_spice`: widened beyond the four exact strings, since Sierra now
  asks this every order and relays the answer in the customer's words. Reuses
  `SPICE_ALIASES` from `clover/order_submit.py` (the same table the Clover
  note→modifier matcher uses, so both sides read the same words the same way),
  plus "no preference"/"koi bhi"/"whatever" → Medium and a negation guard so
  "not spicy" is Mild rather than Spicy. Unparseable input still gets
  `INVALID SPICE`.
- `record_additional_requests`: docstring, arg description and GUIDE reworded —
  allergies + special instructions, never re-ask spice.
- `_apply_default_spice`: unchanged behaviour, docstring now says it is the
  bypass safety net rather than the normal route.

### `restaurant/clover/order_submit.py`
`_SPICE_ALIASES` → `SPICE_ALIASES` (now shared with the agent) + a comment
noting the ordering is load-bearing ("extra spicy" before "spicy").

### `restaurant/agent/gates.py`
Wording only: the additional-requests blocker texts drop "spice preferences".
No gate, state field or phase-chain change — item tools stay ungated per PR 091.

### `restaurant/agent/prompt.py`
`_your_job()`: the checklist says spice is asked per dish as it goes in; the old
"NEVER ask about spice while taking items" rule is replaced by the per-dish rule
(ask when the tool refuses, one question for several dishes, "no preference" =
Medium, never re-ask at the end). `NEEDS SPICE` added to TRUST TOOL RESULTS.
Tool contract lines for `add_item` and `record_additional_requests` updated —
**in both the persona and the legacy (`PROMPT_STYLE=legacy`) copies.**

### `restaurant/agent/persona.py`
Tone examples reworked: the English example previously showed a butter chicken
added with no spice (now a refusal), so it now shows the ask and the re-call;
the Punjabi example shows two spiced dishes covered by ONE question and drops
"spice preferences" from the wrap-up line.

### `tests/`
- `test_agent_tools.py`: `test_add_without_spice_succeeds_spice_unset` →
  `test_spiced_dish_without_spice_refused_then_added` (⛔ prefix, empty cart,
  `pending_add_refusals`, then success at Medium). New:
  `test_more_of_an_already_spiced_dish_is_not_asked_again`,
  `test_unspiced_dish_never_asks_for_spice`,
  `test_spice_and_required_group_asked_in_one_refusal`, and a parametrized
  `test_spoken_spice_vocabulary_canonicalized` over the spoken vocabulary.
  The two `_apply_default_spice` tests now reach the net through a direct cart
  add (what the web RPC does) instead of a bare `add_item`.
- `tests/scenarios/*.json`: a spice-answer turn inserted wherever a spiced dish
  is ordered (`english_pickup`, `sloppy_readback`, `punjabi_order`,
  `hindi_order`, `ambiguous_fish`), and the old combined "medium spice + no
  allergies" turn split into two. `no_spice_mentioned` now has the customer say
  "no preference" and still expects Medium. `sloppy_readback` gets one more
  trailing confirmation turn (the extra spice turn shifted its queue).
- **Unrelated fixture repair, needed to run the harness at all:** every
  scenario phone number used the 555 exchange, which PR 091's
  fabricated-contact backstop rejects (`is_plausible_phone`), so every
  order-placing scenario has failed since that PR merged — pr086 was the last
  10/10 run. The exchange is now `304` in all eight fixtures and in the
  harness docstring example; spoken digits and expectations still match.

## What's NOT in This PR
- The Store/web UI — untouched; it already worked this way.
- `_apply_default_spice` semantics, the additional-requests gate, and the
  `allergy_note` path to Clover/n8n — unchanged.
- `web_sync` cart_add is still advisory about required groups; the readback
  safety net covers it.

## How to Test
```
PYTHONPATH=. uv run --with pytest pytest tests
uv run python scripts/dialogue_harness.py --out docs/eval/pr094
```

Manual call-flow check:
1. "Two butter chicken and a garlic naan" — Sierra adds the naan, asks the
   spice level for the butter chicken only, and the butter chicken is **not**
   in the cart until answered.
2. Name two spiced dishes in one turn — one spice question should cover both.
3. "One more butter chicken" afterwards — no second spice question; the
   quantity goes up and the note keeps the original level.
4. Answer "no preference" — the line comes back Medium.
5. At the end, Sierra asks about allergies/special instructions only, never
   spice again.
6. Confirm the placed Clover order carries a Spice Level **modifier** (not a
   fallback note) on every spiced line.

## Post-Merge: VPS Pull Command
`cd /opt/livekit-sarvam && git pull origin main && uv sync`
