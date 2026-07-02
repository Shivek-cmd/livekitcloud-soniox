# PR 041 — Phase 8c: Submit orders to Clover POS

## Problem

`place_order()` only logged `ORDER_PLACED` JSON locally. Confirmed voice orders never reached Clover — menu sync (8a–8b) worked, but atomic order submit was planned, not wired.

## Solution

| Component | Change |
|-----------|--------|
| **`restaurant/clover/order_submit.py`** | Build atomic `orderCart`, checkout validate, create order, upsert customer by phone, optional kitchen print |
| **`agent.py`** | When `CLOVER_SUBMIT_ORDERS=1`, submit to Clover before marking cart placed; fail gracefully on POS errors |
| **`.env.example`** | Document `CLOVER_SUBMIT_ORDERS`, `CLOVER_PRINT_ORDERS`, `MENU_CACHE_PATH` |
| **`scripts/clover_submit_test.py`** | Sandbox integration script (`--dry-run` or live submit) |
| **`tests/test_clover_order_submit.py`** | Unit tests for cart body, spice modifiers, submit flow |

## Flow

```
place_order() → ready_to_place()
  → [CLOVER_SUBMIT_ORDERS=1] submit_cart_to_clover()
      → build_order_cart_body (clover_item_id + spice modifiers)
      → POST /atomic_order/checkouts (validate)
      → POST /atomic_order/orders (create)
      → upsert customer by phone + attach to order
      → POST /print_event (if CLOVER_PRINT_ORDERS=1)
  → mark_placed(order_id=clover_order_id)
  → ORDER_PLACED log + session analytics event
```

## VPS env (enable submit)

```bash
USE_CLOVER_MENU=1
CLOVER_SUBMIT_ORDERS=1
CLOVER_PRINT_ORDERS=1
CLOVER_BASE_URL=https://apisandbox.dev.clover.com   # or production URL
CLOVER_MID=...
CLOVER_API_TOKEN=...
CLOVER_ORDER_TYPE_PICKUP_ID=...
CLOVER_ORDER_TYPE_DELIVERY_ID=...
MENU_CACHE_PATH=data/menu_cache_bizbull.json
```

Sync menu first: `uv run python scripts/clover_sync_menu.py`

## Deploy

```bash
cd /opt/livekit-sarvam && git fetch origin && git checkout main && git reset --hard origin/main && uv sync && systemctl restart restaurant-agent
```

## Test plan

- [ ] `PYTHONPATH=. USE_CLOVER_MENU=1 uv run python scripts/clover_submit_test.py --dry-run` — valid orderCart JSON
- [ ] `CLOVER_SUBMIT_ORDERS=1` — order appears in Clover Dashboard
- [ ] Live call: complete order → `ORDER_PLACED` log includes `clover_order_id`
- [ ] Clover API failure → agent says cannot place, cart **not** marked placed
- [ ] `CLOVER_SUBMIT_ORDERS=0` → log-only behavior unchanged (backward compatible)
