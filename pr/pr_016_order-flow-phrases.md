# PR 016 — Order flow phrases + phase fixes

## Branch
`pr_016_order-flow-phrases`

## Status
⬜ **Open** — not merged to `main` as of 2026-06-29. Included in branch `pr_017_echo-and-flow-hardening`.

## What This PR Does

Fixes live-call phrase and flow bugs from PR 015 testing (session ~2026-06-28):

1. **Allergies question** — exact code-mix line `"Any allergies or special instructions?"` (no formal **ਹਦਾਇਤਾਂ**).
2. **Phase advancement** — after caller answers allergies step, advance to pickup/delivery (was stuck on `special_instructions`).
3. **Order read-back** — `get_order_summary()` includes spoken template: voice_line names, English quantities (one/two), `"All good?"` — no **ik/do**, no **ਸੰਬੰਧ**, no confirm before pickup.
4. **Pickup/delivery intent** — `"ਚਾਹੀਦਾ pickup"` no longer misclassified as `add_item`.
5. **Quantity ask** — template `"How many — one or two?"` (English numbers only).
6. **Restaurant branding** — **Punjab Da Dhaba** → **Bizbull Restaurant** in `menu.py`, tenant defaults, web title, npm package name, systemd descriptions.

## Files Modified

- `restaurant/conversation.py` — templates, pickup/delivery intents
- `restaurant/order_flow.py` — phase transitions, SAY EXACTLY guidance
- `restaurant/orders.py` — read-back hint in tool output
- `restaurant/prompts.py` — ban Roman ik/do for quantities
- `agent.py` — sync flow on customer/delivery tools
- `tests/test_conversation.py`
- `restaurant/menu.py`, `restaurant/tenants/store.py`
- `web/index.html`, `web/package.json`, `web/package-lock.json`
- `deploy/restaurant-agent.service`, `deploy/restaurant-token.service`

## Depends on

PR **015** (merged).

## Superseded by

PR **017** stacks on this branch — merge 017 after 016 or merge 017 alone if it contains 016 commits.

## Post-Merge: VPS

```bash
bash /opt/livekit-sarvam/scripts/vps_deploy.sh
```

## Verification

- [ ] Allergies line is exact English question
- [ ] Browser tab title says Bizbull Restaurant
- [ ] Sierra prompt uses Bizbull not Punjab Da Dhaba
