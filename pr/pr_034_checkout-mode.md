# PR 034 — Checkout mode (LLM off, single speak)

## Branch
`pr_034_checkout-mode`

## Status
⬜ **Open** — implemented on branch; awaiting review.

## What This PR Does

Replaces the hybrid ladder+LLM checkout (PR 032–033) with **Checkout Mode**:

1. **`restaurant/checkout_runner.py`** — one state machine from `"bas"` → `place_order()`
2. **LLM blocked** — after checkout starts, every turn ends with `StopResponse` (no guidance, no fillers, no GPT speech)
3. **Single speak** — `PHONE_PREEMPTIVE_TTS=0` default on phone + `interrupt()` before each line
4. **Fixed phrases only** — `phrase_name_for_order`, `phrase_phone_for_order`, read-back templates
5. **`is_confirm_yes`** — `"ਹਾਂ ਜੀ, ਹਾਂ ਜੀ"` counts as yes at read-back

## Checkout steps

```
ORDER_DONE → allergies → pickup → read-back → name → phone → final confirm → place_order
```

## Files Added

- `restaurant/checkout_runner.py`
- `tests/test_checkout_runner.py`

## Files Modified

- `agent.py` — `CheckoutRunner`, remove `_try_ladder_step`
- `restaurant/conversation.py` — confirm-yes fix
- `restaurant/session_config.py` — preemptive TTS default off (phone)
- `.env.example` — `PHONE_PREEMPTIVE_TTS=0`

## Post-Merge: VPS

```bash
cd /opt/livekit-sarvam && git fetch origin && git checkout main && git reset --hard origin/main && uv sync && systemctl restart restaurant-agent
```

Add to VPS `.env` if not present:

```
PHONE_PREEMPTIVE_TTS=0
```

## Verification

```bash
journalctl -u restaurant-agent -f | grep -E 'CHECKOUT|CHECKOUT entered|TURN_GUIDANCE'
```

During checkout you should see **`CHECKOUT`** logs and **no** `TURN_GUIDANCE` until call ends.
