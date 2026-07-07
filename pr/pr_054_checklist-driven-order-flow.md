# PR 054 — Checklist-driven, model-led order flow (retroactive doc)

## Branch
`claude/repo-review-ujqggd` (merged as GitHub PR **#90**)

> **Process note:** this PR was authored and merged directly by Sandeep Taur
> via Claude Code, without following `pr/pr_rules.md` (no doc-first, branch
> name doesn't match `pr_NNN_<description>`, no `pr/README.md` entry). This
> doc is written **after the fact** to bring it into the repo's tracking
> convention. Numbered 054 because it merged to `main` immediately after PR
> 053 (#89). The in-progress local branch that had been claiming the 054
> number (`pr_054_mid-checkout-add-and-devanagari-coverage`) was split: its
> mid-checkout-add mechanism was redundant with this PR's `reopen_after_add`
> and was dropped; its unrelated Devanagari-coverage fix was moved to
> **PR 055** (`pr/pr_055_devanagari-add-item-coverage.md`).

## Merge info
- Commit: `845a41f` ("Make order flow flexible and human: checklist-driven,
  model-led, adds anytime")
- Merge commit on `main`: `ad5781d` (GitHub PR #90)
- Author: Sandeep Taur (`sandeeptaur@gmail.com`)
- Co-authored-by: Claude Opus 4.8
- Session: `https://claude.ai/code/session_01Lcz2QogtdYojbq6hdGtAZj`
- Merged: 2026-07-06 18:45 (local)

## What This PR Does

Replaces the rigid, one-directional checkout ladder (PR 038/043/044/045/050
lineage) with a **requirements checklist** the LLM works through naturally,
like a human host — while code still owns state transitions, the grounded
read-back, contact capture, and the final `place_order()` gate.

Previously, once a call entered a "code-owned checkout" phase
(`is_code_owned_checkout`), the LLM was muted behind fixed canned lines and
only a hardcoded `_reask_current_checkout_question` fallback prevented dead
air. This PR removes that mute entirely: `outstanding_requirements()` is
injected into the turn guidance on **every** turn (not just during
collecting), and the LLM leads the reply in both collecting and checkout.

## Files Modified

### `restaurant/order_flow.py`
- New `outstanding_requirements(cart, state) -> list[str]` — single source of
  truth for what's still missing before an order can be placed (items,
  spice level per dish, allergies, pickup/delivery, delivery address,
  read-back confirmation, name, phone). Soft guide, not an enforced sequence;
  the only hard gate remains `OrderCart.ready_to_place()`.
- New `format_cart_brief(cart)` — one-line factual cart summary for per-turn
  grounding.
- New `OrderFlowController.reopen_after_add()` — clears
  `readback_spoken`/`readback_confirmed` when a dish is added mid-checkout,
  so a stale read-back can't reach `place_order()`.
- New `_checkout_guidance()` replaces the old fixed-phase branch tree in
  `build_turn_plan` — soft steering (mentions the next outstanding item,
  keeps read-back/phone-readback/place-order code-owned) instead of dictating
  exact phrases per phase.
- Removed `_CODE_OWNED_LINE` constant and the old phase-by-phase
  `is_code_owned_checkout` branch logic from `build_turn_plan`.
- `[TURN GUIDANCE]` line renamed to `[ORDER STATUS]`, now includes cart
  contents and the outstanding-requirements list on every turn.
- `_collecting_guidance()`'s `ADD_ITEM`-during-checkout branch flipped from
  refusing ("finish checkout first") to cooperating (call `add_to_order` or
  `update_item_quantity`).

### `agent.py`
- `add_to_order` tool no longer rejects calls during checkout
  (`is_collecting_phase` gate removed) — works at any point in the call; adding
  mid-checkout calls `reopen_after_add()` so the order is re-read before
  placing.
- New `_ADD_CLARIFY_MIN_CONF` (env `ADD_CLARIFY_MIN_CONF`, default `0.7`):
  matches between the abstain floor (0.55) and this threshold now return a
  "did you mean X?" clarification instead of silently adding.
- New `is_quantity_correction()` check (from `conversation.py`) short-circuits
  `_try_auto_add` so a correction like "I said one, not two" doesn't get
  additively auto-added (which would double it) — routes to
  `update_item_quantity` instead.
- `_fast_forward_checkout()` no longer silently marks allergies/special
  instructions as done — only marks items complete. Silent-skip of the
  allergies question was a live-call defect this closes.
- `_try_run_checkout_ladder()`: `phase` is re-read after every state-changing
  call (was previously captured once at the top and could go stale across a
  branch); readback/confirm branches now bail if
  `special_instructions_done` is still false, so allergies can't be skipped
  by a caller jumping ahead.
- **Removed** `_reask_current_checkout_question()` entirely, and the
  `is_code_owned_checkout(...) and intent not in DETOUR_INTENTS` mute block
  that called it — dead air during checkout is now structurally prevented
  because the LLM always gets a turn instead of being muted.

### `restaurant/conversation.py`
- New `is_quantity_correction(text)` + `_CORRECTION_CUE_RE` — detects
  correction phrasing ("I said X not Y", "make it three", "ਕਿਹਾ ਸੀ", "ग़लत",
  "बदल", etc.) in English/Punjabi/Hindi.

## Files Deleted
- `tests/test_checkout_ladder_reask.py` — tested the removed
  `_reask_current_checkout_question` fallback; obsolete now that the LLM
  always replies.

## Files Modified (tests)
- `tests/test_order_flow.py` — renamed
  `test_checkout_guidance_is_code_owned` → `test_checkout_guidance_is_checklist_driven`;
  added `test_outstanding_requirements_lists_missing_facts` and
  `test_reopen_after_add_invalidates_readback`.
- `tests/test_conversation.py`, `tests/test_phone_echo.py` — assertions
  updated from `"CHECKOUT STEP" in plan.guidance` to
  `"Still needed before you can place this order" in plan.guidance`.

## What's NOT in This PR
- No changes to `docs/HANDOFF.md` or `pr/README.md` (added here, retroactively).
- No changes to the phone-background filter, menu matching, or Clover
  integration.
- Does not touch `place_order()`'s own hard-gate logic
  (`OrderCart.ready_to_place()`).

## Known conflict risk
The local `pr_054_mid-checkout-add-and-devanagari-coverage` branch (currently
uncommitted, based off `0c1b846`, pre-dating this merge) modifies the same
three core files: `agent.py`, `restaurant/conversation.py`,
`restaurant/order_flow.py`. It will need a rebase onto `origin/main`
(`ad5781d` or later) and manual conflict resolution — several functions this
PR removed (`_reask_current_checkout_question`,
`_CODE_OWNED_LINE`) or changed the signature/behavior of
(`_fast_forward_checkout`, `add_to_order`, checkout guidance branching) are
likely touched by that branch's in-progress diff too.

## How to Test
```bash
PYTHONPATH=. pytest tests/test_order_flow.py tests/test_conversation.py tests/test_phone_echo.py -q
```

Live: add a dish mid-checkout (after allergies/pickup have been asked) and
confirm the read-back is spoken again before place order; say "I said one,
not two" for an item already in cart and confirm it corrects the quantity
instead of doubling it; confirm allergies is never silently skipped when the
caller jumps straight to "pickup" while still adding items.

## Post-Merge: VPS Pull Command
`cd /opt/livekit-sarvam && git pull origin main && uv sync`
