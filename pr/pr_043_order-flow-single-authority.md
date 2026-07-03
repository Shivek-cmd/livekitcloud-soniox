# PR 043 — Single-authority order flow (production hardening)

## Branch
`pr_043_order-flow-single-authority`

## Problem

Live calls became inconsistent when callers went off-script (fake menu items, random
questions, partial answers). Root cause was **two authorities** for “where we are” in
the order:

1. **`sync_from_cart()`** — derived phase from cart + flags  
2. **`_phase_guidance()` + `build_turn_plan()`** — re-derived checkout instructions with overlapping conditions  

The overloaded **`confirming`** phase meant four different moments (read-back, wait for
yes, name/phone, ready to place). The LLM received long, sometimes contradictory
`[TURN GUIDANCE]` while the checkout **ladder in `agent.py`** also spoke fixed lines.

Secondary issues:

| Bug | Symptom |
|-----|---------|
| Duplicate `mark_items_complete` / `mark_allergies_asked` | Allergies asked twice or skipped |
| `quantity_allowed` toggled in 3 places per turn | “How many?” flips turn-to-turn |
| Single-word names filtered as background | `"ਸੰਦੀਪ"` dropped at name step |
| No detour recovery after tool miss | After “not on menu”, LLM improvises off-flow |

## Solution

### 1. Single authority — `compute_phase(cart, state)`

`restaurant/order_flow.py` now has one function that decides the step. `sync_from_cart()`
only assigns `state.phase = compute_phase(...)`.

### 2. Split overloaded `confirming`

| Phase | Meaning |
|-------|---------|
| `readback` | Awaiting read-back + “All good?” yes (replaces old `confirming`) |
| `customer_name` | Name not saved |
| `customer_phone` | Phone not saved |
| `ready_to_place` | Contact complete — call `place_order()` |

`OrderPhase.CONFIRMING` kept as **alias** → `readback` for analytics backward compat.

### 3. Code-owned checkout — LLM silenced on checkout steps

During `CODE_OWNED_CHECKOUT_PHASES`, `[TURN GUIDANCE]` is minimal:

> Checkout step is spoken by the system. Do NOT ask allergies / pickup / read-back / name / phone.

Checkout speech stays in `agent.py` → `_try_run_checkout_ladder()` and
`_try_capture_customer_info()`.

**Exception:** `delivery_address` still uses LLM + `set_delivery_address` tool.  
**Detours:** price, availability, order status, human transfer still allowed mid-checkout.

### 4. One path for flag mutations

- Removed duplicate `mark_items_complete()` / `mark_allergies_asked()` from `build_turn_plan` ORDER_DONE branch  
- `_advance_from_user_turn()` only advances when `compute_phase` matches  
- `quantity_allowed` computed once per turn (collecting + add intent only)

### 5. Collecting-phase detour recovery

When `add_to_order` fails (item not on menu), guidance now says: apologize once,
suggest `search_menu_items`, ask “anything else?” — **stay in collecting**.

### 6. Phone background filter bypass at contact capture

`phone_background.py` skips filtering when `phase` is `customer_name`, `customer_phone`,
or `readback` — fixes single-word Punjabi names like `"ਸੰਦੀਪ"` being dropped.

## Files changed

| File | Change |
|------|--------|
| `restaurant/order_flow.py` | Rewrite: `compute_phase`, split phases, minimal checkout guidance |
| `agent.py` | `CONFIRMING` → `READBACK`; pass phase to background filter |
| `restaurant/fillers.py` | Block fillers on `readback`, `ready_to_place` |
| `restaurant/phone_background.py` | Phase-aware bypass for contact capture |
| `restaurant/prompts.py` | Comment points to single authority |
| `tests/test_order_flow.py` | New phase machine tests |
| `tests/test_conversation.py` | Updated expectations |

## Scalability (1000+ concurrent calls)

Each LiveKit worker session owns one `OrderFlowController` + `OrderCart` in memory —
no shared mutable state between calls. `compute_phase()` is pure (cart + local state).
This refactor reduces LLM token load per checkout turn (shorter guidance) and removes
nondeterministic duplicate instructions, which lowers latency variance under load.

## Analytics note

Dashboard phase `confirming` → now logged as `readback` (same enum value via alias).
Downstream queries using `phase = 'confirming'` should use `readback` or `IN ('readback','confirming')`.

## Deploy

```bash
cd /opt/livekit-sarvam && git fetch origin && git checkout main && git reset --hard origin/main && uv sync && systemctl restart restaurant-agent
```

## Test plan

```bash
PYTHONPATH=. uv run pytest tests/test_order_flow.py tests/test_conversation.py tests/test_fillers.py tests/test_phone_background.py -q
```

- [ ] Happy path: add items → done → allergies → pickup → read-back → name → phone → place  
- [ ] Off-menu item mid-order → stays collecting, asks anything else  
- [ ] Random question mid-checkout → detour answer, no checkout restart  
- [ ] Single-word Punjabi name on phone → not filtered as background  
- [ ] Stress: 10 parallel web sessions — no phase cross-talk (isolated carts)
