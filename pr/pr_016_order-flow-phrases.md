# PR 016 — Order flow phrases + phase fixes

## Branch
`pr_016_order-flow-phrases`

## What This PR Does

Fixes live-call phrase and flow bugs from PR 015 testing:

1. **Allergies question** — exact code-mix line `"Any allergies or special instructions?"` (no formal **ਹਦਾਇਤਾਂ**).
2. **Phase advancement** — after caller answers allergies step, advance to pickup/delivery (was stuck on `special_instructions`).
3. **Order read-back** — `get_order_summary()` includes a spoken template: voice_line names, English quantities (one/two), `"All good?"` — no **ik/do**, no **ਸੰਬੰਧ**, no confirm before pickup.
4. **Pickup/delivery intent** — `"ਚਾਹੀਦਾ pickup"` no longer misclassified as `add_item`.
5. **Quantity ask** — template `"How many — one or two?"` (English numbers only).

## Files Modified

- `restaurant/conversation.py` — templates, pickup/delivery/no-allergy intents
- `restaurant/order_flow.py` — phase transitions, exact SAY EXACTLY guidance
- `restaurant/orders.py` — `spoken_readback_hint()` for tool output
- `restaurant/prompts.py` — ban Roman ik/do for quantities
- `agent.py` — sync flow on customer/delivery tools
- `tests/test_conversation.py` — new cases

## Post-Merge: VPS

```bash
bash /opt/livekit-sarvam/scripts/vps_deploy.sh
```
