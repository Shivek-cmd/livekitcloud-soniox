# PR 030 — Order flow quality (strict auto-add, final confirm, cart truth)

## Branch
`pr_030_order-flow-quality`

## What This PR Does

Fixes **global** ordering bugs (wrong auto-add, cart drift, missing final confirm, double goodbye) — not one-off menu patches.

**Principles:**
1. **Strict menu match for auto-add** — no fuzzy token scoring on qty words or short fragments
2. **Cart is law** — read-backs from cart; auto-add only when every spoken segment resolves
3. **Final confirm gate** — name + phone collected → full summary → explicit yes → `place_order()`
4. **Aliases as data** — shikanji → Nimbu Pani (ongoing additions as test calls surface gaps)
5. **No double goodbye** — code-owned closing line not duplicated in LLM context

## Files Added

### `tests/test_order_flow_quality.py`
Regression tests for strict parse, final confirm phase, blocked qty tokens.

## Files Modified

### `restaurant/clover/menu.py`
- `find_item_strict()` — exact / alias match only
- Block qty-only queries in fuzzy `find_item()`
- `_overlay_voice_labels()` — merge latest aliases from `clover_voice_labels.json` on cache load (no Clover resync needed)

### `restaurant/menu_provider.py`
- Export `find_item_strict()`

### `restaurant/order_parse.py`
- Punjabi order-verb stripping (`ਕਰ ਦਿਓ`, `ਆਪਣੀ`, …)
- Strict resolve for auto-add; segment count must match

### `restaurant/order_flow.py`
- `FINAL_CONFIRM` phase + `final_confirmed` flag
- Guidance: final read-back before `place_order()`

### `restaurant/conversation.py`
- `format_final_order_confirm()` — items + pickup + name + phone

### `agent.py`
- `place_order()` requires `final_confirmed`
- Auto-add uses strict parse + segment parity
- Goodbye `add_to_chat_ctx=False`

### `restaurant/prompts.py`
- Cart truth + final confirm rules

### `data/clover_voice_labels.json`
- Shikanji / Punjabi drink aliases → Nimbu Pani

### `docs/HANDOFF.md`
- Order flow ladder update

## What's NOT in This PR

- Full menu alias audit (add iteratively from test calls)
- Auto-add disabled entirely
- Clover order submit (Phase 8c)

## How to Test

```bash
uv run pytest tests/test_order_parse.py tests/test_order_flow_quality.py -q
```

Live: place order → final confirm with name/phone → single goodbye → call ends.

## Post-Merge: VPS

```bash
cd /opt/livekit-sarvam && git pull origin main && systemctl restart restaurant-agent
```
