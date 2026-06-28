# PR 017 — Echo filter + order flow hardening

## Branch
`pr_017_echo-and-flow-hardening`

## What This PR Does

Fixes live phone call failures from session `AJ_au2zatxEoKfG` (2026-06-28): echo filter dropping real pickup/order speech, weak add-item intent, garbled pickup/delivery prompts, allergies “no” not advancing, and name/phone asked before cart read-back.

## Files Modified

### `restaurant/phone_echo.py` (B-1)
- Bypass echo filter for meaningful intents (pickup, delivery, add_item, price, etc.) and order/price signals.
- Stricter token-overlap thresholds; require near-exact repeat for long utterances.
- Treat user turns with 2+ unique tokens vs agent line as real speech.

### `restaurant/conversation.py`
- Detect quantity+dish orders (`one paneer`, `1 paneer`, `ਕਿਹਾ`, `ਕਰ ਦ`).
- Detect allergies denial (`not at all`, `not not`, mixed English/Punjabi no).
- `is_want_to_order_only()` → fixed pickup/delivery template instead of LLM improvisation.

### `restaurant/order_flow.py`
- `readback_confirmed` gate — name/phone only after “All good?” read-back.
- Early “want to order” → SAY EXACTLY pickup/delivery question.
- Add-item guidance: confirm dish if STT differs from last suggestion.

### `agent.py`
- Pass intent into echo filter; auto-set `cart.order_type` on pickup/delivery intent.
- `set_order_type` tool text no longer skips to name before read-back.

### `tests/test_phone_echo.py`, `tests/test_conversation.py`
- Regression tests from live call log strings.

## Post-Merge: VPS

```bash
bash /opt/livekit-sarvam/scripts/vps_deploy.sh
```

## Verification checklist

- [ ] “Yeah, I'm looking for pickup” → **not** ignored as echo; pickup saved
- [ ] Full dish order after Sierra lists paneer items → processed, not “go ahead ji”
- [ ] “I want to order” → exact “Will that be pickup or delivery?”
- [ ] “One paneer tikka and two mango shake” → add_item intent
- [ ] “not not at all” after allergies → advances to pickup (if unset) or read-back
- [ ] Name/phone only after read-back + “All good?” yes

## Depends on

PR 016 (`pr_016_order-flow-phrases`) — merge 016 first or merge 017 as stacked PR.
