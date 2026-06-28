# PR 012 — Web W2: live order sync + hybrid tap-to-add

## Branch
`pr_012_web-w2-live-order`

## What This PR Does

Second implementation phase (**W2**) of the "Order with Sierra" plan
(`docs/plan/11-web-order-with-sierra.md`). The order panel goes **live** and ordering becomes
**hybrid** (voice + tap):

- The server-side `OrderCart` is the single source of truth. On **every** cart change (voice
  tool *or* tap), the agent publishes the full order state as a reliable `order.state` data
  packet. The browser also pulls state on connect/reconnect via the `get_order_state` RPC.
- **Live order panel**: items with live quantities, per-line totals, qty steppers (±) and
  remove, subtotal / delivery / total, order type + customer details, a status line
  (building → awaiting details → confirming → placed), and a "pay at pickup/delivery" note
  once placed.
- **Tap-to-add**: each menu row gets an **Add** button that calls the `cart_add` RPC. Items
  with required modifiers still add and surface a "Sierra'll confirm" hint (the modifier
  picker lands in W3). Tap controls are enabled only while a call is active, since the cart
  lives in the agent session.

Because the cart is shared server-side, Sierra always reads back the real order (including
tapped items) at confirmation time — voice and tap stay in sync without extra plumbing.

## Data Contract (`order.state`)
```jsonc
{
  "v": 1,
  "status": "empty|building|awaiting_contact|confirming|placed",
  "items": [{ "id", "name", "voice_line", "qty", "unit_price", "line_total", "note", "modifiers" }],
  "order_type": "pickup|delivery|null",
  "delivery_address": "string|null",
  "customer": { "name": "string|null", "phone": "string|null" },
  "subtotal": 0, "delivery_charge": 0, "total": 0,
  "eta": "20-25 min|null", "order_id": "string|null"
}
```
Client → agent RPCs: `get_order_state`, `cart_add {item_id, qty, modifiers}`,
`cart_set_qty {item_id, qty}`, `cart_remove {item_id}` — each returns
`{ ok, error?, needs?, state? }`.

## Files Added
### `restaurant/web_sync.py`
`WebSync`: publishes `order.state` and registers the 4 client cart RPCs against the agent's
participant. Mutates the shared `OrderCart` and re-publishes after each change.
### `web/src/hooks/useCart.tsx`
`CartProvider` + `useCart()`: subscribes to `order.state`, resyncs via `get_order_state` on
agent presence, and exposes `addItem / setQty / removeItem` (RPC wrappers).

## Files Modified
### `restaurant/orders.py`
`OrderCart` gains `placed / order_id / eta`, `set_quantity_by_id`, `remove_by_id`,
`mark_placed`, `status()`, and `to_state_dict()` (the web contract).
### `restaurant/menu_provider.py`
Adds `find_item_by_id()` (tap-to-add lookup) and `required_modifier_groups()`.
### `restaurant/clover/menu.py`
Adds `MenuCache.get_by_id()`.
### `agent.py`
Imports `WebSync`; binds it for the **web** channel after `session.start`; publishes
`order.state` after every cart-mutating tool (`add/remove/set_order_type/set_customer_info/
set_delivery_address`) and marks the cart placed (with ETA) in `place_order`. Phone is
unaffected (no `WebSync` bound → `_sync_web` is a no-op).
### `web/src/components/OrderPanel.tsx`
Rebuilt from the W1 stub into the live panel (items, steppers, totals, status, meta).
### `web/src/components/LiveMenu.tsx`
Adds the **Add** button per item with transient feedback.
### `web/src/components/OrderWithSierra.tsx`
Wraps the panels in `CartProvider`.
### `web/src/lib/api.ts`
Adds `OrderItem`, `OrderState`, `OrderStatus`, `CartRpcResult` types.
### `web/src/App.css`
Styles for the live order panel (items, qty stepper, totals, status, meta) and Add button.

## What's NOT in This PR
- Menu highlight + modifier picker (W3), avatar (W4), hardening/edge cases (W5), web prompt
  variant (W6).
- Spoken acknowledgement of tap-adds (W3), online payment / Clover order submit (8c),
  Store tab.

## How to Test
```bash
cd web && npm install && npm run build   # builds clean
# Live: start a call, then
#  - order by voice -> items appear in the order panel instantly
#  - tap Add on menu rows -> item appears; Sierra still reads it back at confirm
#  - use ± / remove -> totals update; refresh mid-call -> state resyncs
#  - confirm + place -> status flips to "placed", shows ETA + pay-at-pickup note
```

## Post-Merge: VPS
No Caddy change (RPCs/data ride the existing LiveKit WebSocket). Just deploy:
```bash
bash /opt/livekit-sarvam/scripts/vps_deploy.sh   # rebuilds web + restarts agent/token
```
