# PR 025 — Pickup STT, “All good” confirm, no price until asked

## Branch
`pr_025_pickup-confirm-no-price-readback`

## What This PR Does

Fixes three phone-call issues from live testing:

1. **Pickup misheard as `ਇੱਕ ਕੱਪ` / `ਇੱਕ ਅੱਪ`** — fuzzy pickup STT at order-type step; no pickup/delivery loop.
2. **“All good / ਆਲ ਗੁੱਡ” loop** — recognize code-mix yes after read-back → ask name once (no repeat read-back).
3. **No price in speech** — phone never mentions dollars/totals unless customer asks price (`ASK_PRICE` intent).
4. **Shorter greeting** — `Hi! Sierra from Bizbull here. I speak English, Hindi, and Punjabi. How can I help?`

## Files Modified

### `restaurant/conversation.py`
- `is_likely_pickup_stt()`, `resolve_intent(phase=…)` — pickup before qty-add at `order_type`
- `is_confirm_yes()` — `ਆਲ ਗੁੱਡ`, `ਹਾਂ ਜੀ, all good`, `ਯੇਸ`
- `format_order_readback(include_price=…)` — phone template without total
- `sanitize_assistant_speech` — strip leaked dollar phrases on phone
- `OPENING_GREETING` — shorter Bizbull intro (phone + web)

### `restaurant/order_flow.py`
- Phone read-back guidance without dollars; global phone no-price line

### `agent.py`
- `resolve_intent` with phase; phone `get_order_summary` / `place_order` without spoken price

### `restaurant/prompts.py`
- Phone: never state price unless customer asked

### `tests/test_conversation.py`
- Tests for pickup STT, confirm yes, read-back without price

## How to Test

```bash
uv run python -m pytest tests/test_conversation.py -v
# Phone: order → pickup (or say pickup) → read-back → "ਹਾਂ ਜੀ, ਆਲ ਗੁੱਡ" → name question
# No dollars at any step unless "how much"
```

## Post-Merge: VPS

```bash
bash /opt/livekit-sarvam/scripts/vps_deploy.sh
```
