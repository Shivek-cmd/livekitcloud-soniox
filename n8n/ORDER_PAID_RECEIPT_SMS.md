# n8n · order.paid (Store receipt SMS) — PR 090 P4

Sierra POSTs `order.paid` to the **same** webhook URL as `order.placed`
(`N8N_WEBHOOK_ORDERS_URL` / `https://n8n.bizbull.ai/webhook/sierra-ghl-sync`).

Confirm SMS (`order.placed`) is unchanged. This event is **only** for online
pay-now after Clover Hosted Checkout succeeds.

## Payload (example)

```json
{
  "schema_version": 1,
  "event": "order.paid",
  "event_id": "order.paid:PAYMENT_ID",
  "tenant_id": "bizbull",
  "channel": "web_store",
  "customer": {
    "name": "Alex",
    "phone_e164": "+15875551234"
  },
  "order": {
    "clover_order_id": "…",
    "status": "paid",
    "payment_id": "…",
    "receipt_url": "https://www.clover.com/r/…",
    "checkout_session_id": "…",
    "total": 24.5,
    "order_type": "pickup"
  },
  "meta": {
    "source": "sierra",
    "sms_hint": "Send receipt SMS with receipt_url. Do not re-send order-placed confirm."
  }
}
```

## What to add in n8n / GHL (manual — you do this)

1. In the existing `sierra-ghl-sync` workflow, branch on `event`:
   - `order.placed` → current path (contact + opp + confirm SMS)
   - `order.paid` → **new** path only
2. For `order.paid`:
   - Upsert contact by `customer.phone_e164` (optional if already exists)
   - Send SMS (GHL Conversations / workflow) with the receipt link
3. Suggested SMS copy:

```
Bizbull: Thanks — your online payment is confirmed.
Order {{order.clover_order_id}}
Receipt: {{order.receipt_url}}
```

4. Idempotency: `event_id` is `order.paid:{payment_id}` — ignore duplicates.
5. Do **not** create a second “Placed” opportunity or re-fire the confirm SMS workflow.

## Test (PowerShell)

```powershell
$body = @{
  schema_version = 1
  event = "order.paid"
  event_id = "order.paid:TEST-PAY-001"
  tenant_id = "bizbull"
  channel = "web_store"
  customer = @{
    name = "Sierra Test"
    phone_e164 = "+919413752688"
  }
  order = @{
    clover_order_id = "TEST-CLOVER-PAID-001"
    status = "paid"
    payment_id = "TEST-PAY-001"
    receipt_url = "https://www.clover.com/r/TEST-PAY-001"
    order_type = "pickup"
    total = 16.99
  }
} | ConvertTo-Json -Depth 5

Invoke-RestMethod -Method Post `
  -Uri "https://n8n.bizbull.ai/webhook/sierra-ghl-sync" `
  -ContentType "application/json" `
  -Body $body
```

Until the n8n branch exists, n8n may still return 200 while ignoring `order.paid` — Sierra stays fail-open either way.
