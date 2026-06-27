# Clover Orders API (atomic vs custom)

> Captured 2026-06-27 from Clover Platform Docs (`working-with-orders`, `create-an-atomic-order`,
> `creating-custom-orders`, `calculating-order-totals`, `printing-orders-rest-api`, `orders-faqs`).
> Why we care: Sierra must **place real orders** that appear on kitchen printers and Register.

## Two order creation paths

| | **Atomic order** | **Custom order** |
|---|---|---|
| API calls | **1 call** (checkout + create) | Multiple calls (create order → add line items → modifiers → …) |
| Inventory | Uses **Clover inventory item IDs** | Can use inventory IDs or ad-hoc line items |
| Tax/totals | **Clover calculates** in real time | App must recalculate after changes |
| Best for | Standard menu orders (our case) | Non-standard items, price/tax overrides |
| Sync to devices | Yes — appears on Dashboard + all devices | Yes, if built correctly |

**Recommendation for Sierra v1: Atomic orders.** Single submit, correct tax, fewer failure modes.

## Atomic order workflow (3 steps)

### Step 1 — Checkout (preview, no order created)

`POST /v3/merchants/{mId}/atomic_order/checkouts`

Build `orderCart` with line items + modifiers + discounts. Returns calculated totals/taxes.
Order does **not** appear on merchant devices yet — safe for "confirm your total" step.

### Step 2 — Create order

`POST /v3/merchants/{mId}/atomic_order/orders`

Same body as checkout. Creates the order record — **visible on Merchant Dashboard and devices**.

Required in `orderCart`:
- `lineItems[].item.id` — Clover inventory item UUID
- `orderType.id` — merchant order type (pick-up, delivery, etc.)
- Optional: `modifications[]` with modifier `id`, `name`, `amount`
- Optional: `discounts[]`, service charges

### Step 3 — Payment (optional for v1)

`POST /v1/orders/{orderId}/pay` (Ecommerce API, sandbox: `scl-sandbox.dev.clover.com`)

For **pay-at-pickup** v1: skip payment step. Order stays open; customer pays in store.
Alternative: record external payment via `POST .../orders/{orderId}/payments` (custom tender).

## Order cart request shape (minimal example)

```json
{
  "orderCart": {
    "lineItems": [
      {
        "item": { "id": "INVENTORY_ITEM_UUID" },
        "modifications": [
          {
            "modifier": { "id": "MODIFIER_UUID", "available": true },
            "name": "Medium Spicy",
            "amount": 0
          }
        ]
      }
    ],
    "orderType": { "id": "ORDER_TYPE_UUID" }
  }
}
```

Notes:
- If `modId` omitted, other modifier fields are **ignored**.
- If both `name` and `amount` passed without inventory modifier, they **override** defaults.
- Amounts in **cents**.

## Order types

Each merchant defines order types (online, delivery, pick-up, dine-in).

`POST /v3/merchants/{mId}/order_types` to create; fields include `taxable`, `maxOrderAmount`,
`hoursAvailable`, `isDefault`.

Sierra v1: use **pick-up** order type (create or select existing per tenant config).

## Custom order path (reference)

Multi-step if we need it later:

1. `POST /orders` — create open order with `orderType`, `state: "Open"`
2. `POST /orders/{orderId}/line_items` — single item (or `bulk_line_items` for batch, max 100/request)
3. `POST .../line_items/{lineItemId}/modifications` — add modifier
4. Recalculate totals manually (see calculating-order-totals)
5. Payment / close

Limits: max **2,500 line items** per order; max **100** per bulk request.

## Order states

| State | Meaning |
|---|---|
| `active` | Order cart (pre-checkout) |
| `Open` | Created, not fully paid |
| `null` | Unfinished — may not show on device apps |
| `closed` / paid | Payment recorded |
| `voided` | Cancelled |

**Sierra rule:** only tell customer "order placed" after Step 2 returns success + order `id`.

## Calculate totals (how Clover thinks)

Order total = line item prices + modifier costs − discounts + service charges + taxes.

Tax rules:
- Applied at **line item level** (no order-level tax API).
- If merchant `vat: true`, tax already included — don't add again.
- Multiple items with same tax rate → tax on **combined subtotal**.
- Rounding: **round half up** ($33.455 → $33.46).
- Discounts affect tax base (line-item vs order-level discount behaves differently).

Use atomic checkout endpoint to get **authoritative total** before verbal confirmation.

## Print to kitchen

`POST /v3/merchants/{mId}/print_event` with `{ "orderRef": { "id": "ORDER_ID" } }`

- Requires **Write orders** permission.
- Routes to merchant's default firing device / onboard printer.
- Print job states: `CREATED` → `PRINTING` → (success = job discarded).
- Subscribe to order webhooks; line items get `printed: true` when done.

**Production note:** atomic orders with **valid inventory items + linked modifier groups** print
reliably. Custom/ad-hoc modifiers may **not print** correctly.

## Common 400 errors (atomic orders)

| message | Cause |
|---|---|
| `item_does_not_exist` | Bad inventory item UUID (details = failed id) |
| `invalid_modifier` | Modifier not linked to item or wrong id |
| `cart_is_empty_or_missing` | No line items |
| `insufficient_customer_info` | Customer required but missing |
| `service_charge_does_not_exist` | Bad service charge id |

Always validate item/modifier IDs against cached menu before submit.

## Production FAQs (selected, relevant to Sierra)

From Clover Orders FAQs:

- **Atomic orders sync to all merchant devices** — kitchen sees the order.
- **Orders API ≠ Clover Dining** — table/seating app uses private schema; our orders go to
  Register/Orders apps, not Dining table map.
- **Customer assign is 2-step** — create customer, then update order with `customer.id`.
  Search existing by phone first to avoid duplicates.
- **Order-level vs line-item discounts** — different API expand paths; receipt may show
  order-level discount not visible in line_items expand alone.
- **Refunds** — Platform REST API does **not** process refunds; Dashboard or Ecommerce API only.
- **502 in sandbox** — complex expand/filter queries timeout; simplify queries, paginate.
- **Custom orders with minimal fields** may not show on POS/Go apps — use atomic + full inventory.
- **Tax must exist in merchant inventory** — cannot invent tax rates at order time.

## Payment integration (deferred)

If we add pay-on-call later:
- Ecommerce API: tokenize card → `POST /v1/orders/{orderId}/pay`
- 3DS may be required for CNP transactions in Canada
- Use `delete_order_on_failure: true` in metadata to avoid orphan orders on failed payment

## Related docs

- [clover-inventory-menu.md](clover-inventory-menu.md)
- [clover-sierra-integration-notes.md](clover-sierra-integration-notes.md)
