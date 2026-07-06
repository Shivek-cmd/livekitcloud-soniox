# PR 050 — Generalize checkout re-ask fallback to all code-owned phases

## Branch
`pr_050_checkout-ladder-generic-reask`

## Problem (live call, 2026-07-06)

At the final "All good?" read-back confirmation, the caller pointed out a
missed item:

```
Sierra: Okay — two Palak Paneer and one Dal Makhani, pickup. All good?
Caller: ਚਾਇ, ਚਾਇ ਵੀ ਬੋਲੀ ਸੀ ਮੈਂ ਨੇ। (Chai, I also said chai)
[... silence ...]
Caller: ਹੈਲੋ.
Caller: हैलो।
Caller: ਹੈਲੋ.
Caller: ਹੈਲੋ.
[... still silence — call effectively dead ...]
```

Root cause: PR 047 added a re-ask fallback so the checkout ladder wouldn't go
dead silent, but it was scoped **only to the `SPECIAL_INSTRUCTIONS` (allergies)
phase**. The same silent-mute gap exists at every other code-owned checkout
phase — `READBACK`, `ORDER_TYPE`, `CUSTOMER_NAME`, `CUSTOMER_PHONE` — because
the general mute block (`is_code_owned_checkout(phase) and intent not in
DETOUR_INTENTS → StopResponse`) has no fallback speech of its own, and
`fillers.py` blocks fillers in every one of those phases too. This call hit it
at `READBACK`, producing the worst possible outcome: total call breakdown.

## Fix

### `agent.py`
- Removed the `SPECIAL_INSTRUCTIONS`-only re-ask `elif` added in PR 047.
- New `_reask_current_checkout_question()` — generic version covering every
  phase that has a clear single pending question:
  - `SPECIAL_INSTRUCTIONS` (if allergies already asked) → re-ask
    `ALLERGIES_QUESTION`
  - `ORDER_TYPE` → re-ask `PICKUP_DELIVERY_QUESTION`
  - `READBACK` (only if the read-back was already spoken once — otherwise a
    different branch owns speaking it the first time, so this must not
    double-speak) → re-speak the full order read-back + "All good?"
  - `CUSTOMER_NAME` → re-ask for name
  - `CUSTOMER_PHONE` (only once name is saved) → re-ask for phone
  - `READY_TO_PLACE` / `PLACED` / `DELIVERY_ADDRESS` — no fallback (see
    "What's NOT in This PR")
- Called from the general checkout-mute block: tries the re-ask first: if it
  spoke something, `raise StopResponse()`; otherwise falls back to the old
  filler+guidance behavior exactly as before (no regression for phases with
  no applicable re-ask).

### `tests/test_checkout_ladder_reask.py` (new)
Constructs a real `RestaurantAgent` with a mocked session and directly
exercises `_reask_current_checkout_question()` across every phase: correct
line spoken for allergies/pickup-delivery/name/phone, full read-back repeated
(not just "All good?" alone) at `READBACK`, no double-speak before read-back
is first spoken, phone re-ask requires name already saved, and no-op at
`READY_TO_PLACE`.

## What's NOT in This PR

- `DELIVERY_ADDRESS` isn't in `CODE_OWNED_CHECKOUT_PHASES` at all (LLM handles
  it freely already), so it was never affected by this bug.
- `READY_TO_PLACE`/`PLACED` have no re-ask — in practice `place_order()` is
  auto-triggered the moment phone is captured, so getting "stuck" here across
  multiple turns shouldn't normally happen; if it does, the old
  filler+guidance fallback still applies (unchanged from before this PR).
- Does **not** add any ability to actually parse/act on a correction like "you
  missed the chai" — this PR only stops the silence. Handling read-back
  corrections is a separate, bigger feature (see PR 052 for the related
  duplicate-item bug from the same call).
- Does not touch `_DONE_RE`'s bare "ਬਸ" bug that dropped the chai order in the
  first place — that's PR 051.

## How to Test

```bash
PYTHONPATH=. pytest tests/test_checkout_ladder_reask.py tests/test_conversation.py tests/test_order_flow.py -q
```

Live: reproduce the exact scenario — at the "All good?" read-back, say
something that isn't a plain yes/no (e.g. point out a missing item). Confirm
Sierra re-speaks the read-back + "All good?" instead of going silent.

## Post-Merge: VPS Pull Command
`cd /opt/livekit-sarvam && git pull origin main && uv sync`
