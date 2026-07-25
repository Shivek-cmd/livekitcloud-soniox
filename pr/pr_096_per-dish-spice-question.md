# PR 096 — The multi-dish spice question names each dish

## Branch
`pr_096_per-dish-spice-question`

## What This PR Does
PR 094 made Sierra ask several dishes' spice levels in **one** question. It did
not say the question has to name them, and every instruction around it showed
the lumped form — the Punjabi tone example literally read `spice ਕਿੰਨਾ ਰੱਖਾਂ ਦੋਹਾਂ
ਲਈ ਜੀ?` ("how much spice for both?") with the customer answering "both medium".
Sierra copied it. On a local call:

```
USER:   चिकन बिरयानी कर दो, जी।
USER:   और 3 चिकन टिक्का मसाला।
SIERRA: एक Chicken Biryani और तीन Chicken Tikka Masala के लिए मसाला कितना रखें —
        mild, medium, spicy या extra spicy?
USER:   मीडियम।
SIERRA: ठीक है जी, ... सभी medium मसाले में।
```

The customer was never offered the chance to want them different. This PR keeps
the one-question rule and adds the missing half: the question must **name each
dish**, and the answer — usually given for all of them in one breath — is mapped
per dish, one `add_item` call each with that dish's own level. A level stated
with no dish named ("medium", "all medium") still applies to every dish asked
about.

Wording is the only lever here, and deliberately so: the tool layer already
enforces the correctness half. `add_item` refuses per dish with `NEEDS SPICE`,
each level arrives on its own call, and the order read-back speaks the per-line
levels before placement — so a mis-mapping is caught out loud rather than
reaching Clover silently. No gate, tool signature or cart behaviour changes.

## Files Modified

### `restaurant/agent/core.py`
The `NEEDS SPICE` refusal text: still "ask about them in the SAME question", now
"but NAME EACH DISH in it, so the customer can give a different level per dish",
with a worked example, an instruction to map each level to the dish it was said
for, and the fallback for one unattributed level. Refusal control flow, the
`pending_add_refusals` decision, `_canonical_spice` and `_cart_line_has_spice`
are untouched.

### `restaurant/agent/prompt.py`
`_your_job()` — the SPICE, PER DISH block carries the same rule and now rules
out the lumped form explicitly ("never a single lumped 'how spicy for both?',
because they may want different levels"). Shared by the persona and legacy
(`PROMPT_STYLE=legacy`) builders, so both pick it up; the tool-contract lines
needed no change.

### `restaurant/agent/persona.py`
The Punjabi tone example is rewritten to demonstrate the behaviour instead of
contradicting it: Sierra asks `Butter Chicken ਕਿੰਨਾ spicy ਰੱਖਾਂ ਜੀ, ਤੇ ਪਨੀਰ ਬਟਰ ਮਸਾਲਾ
ਕਿੰਨਾ?`, the customer answers with two **different** levels in one turn, and the
`[tools: …]` block shows `spice_level="Spicy"` and `spice_level="Mild"` going to
their own dishes. The English single-dish example is unchanged.

## Files Added
### `tests/test_agent_tools.py::test_multi_dish_spice_question_names_each_dish`
Pins the refusal telling the model to name each dish and re-call once per dish
(so the instruction cannot be silently dropped), and that two dishes added in
the same turn keep separate levels in their notes.

## What's NOT in This PR
- No change to when spice is asked, the `NEEDS SPICE` gate itself, `add_item`'s
  signature, `_apply_default_spice`, or the Clover modifier path — PR 094's
  mechanics stand.
- The Store/web UI — it chooses spice per card already.
- `tests/scenarios/*.json` — the harness fixtures order one spiced dish per
  turn, so no scenario exercises the multi-dish question; adding one is
  follow-up work.

## How to Test
```
PYTHONPATH=. uv run --with pytest pytest tests
```
Two pre-existing failures in `tests/test_hosted_checkout.py`
(`test_place_pay_now_disabled_no_url`, `test_place_pay_now_hco_failure_still_places`)
are unrelated to this PR and fail on `main` as well.

Manual call check — order two spiced dishes in one turn: Sierra's single
question should name both, and answering with two different levels ("butter
chicken spicy, paneer mild") must put each level on its own line. Verified on a
local web call (session `restaurant-6f9f343d`): three Chicken Tikka Masala came
back extra spicy and two Amritsari Fish Pakora spicy, from one question.

## Post-Merge: VPS Pull Command
`cd /opt/livekit-sarvam && git pull origin main && uv sync`
