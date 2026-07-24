# n8n — delivery.dispatched → tracking SMS (PR 093)

Sierra POSTs `event: "delivery.dispatched"` to the same webhook URL as
`order.placed` / `order.paid` when Uber Direct creates a courier delivery
for a Store order.

## Envelope (subset)

```json
{
  "event": "delivery.dispatched",
  "event_id": "delivery.dispatched:del_…",
  "channel": "web_store",
  "customer": { "name": "…", "phone_e164": "+1…" },
  "order": {
    "clover_order_id": "…",
    "uber_delivery_id": "del_…",
    "tracking_url": "https://www.ubereats.com/orders/…"
  }
}
```

## n8n branch (manual)

1. IF `event` equals `delivery.dispatched`
2. Send SMS (GHL) with tracking link, e.g.

```
Bizbull: your courier is on the way. Track here: {{ $json.order.tracking_url }}
```

3. Idempotent on `event_id` if you already do that for `order.paid`

Kill switch: only fires when `N8N_SYNC_ENABLED=1` and Uber create delivery succeeded.
