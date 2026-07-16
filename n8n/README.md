# Bizbull · Voice Order → GHL (Phase 0 — production sync)

Importable n8n workflow with sticky-note sections. **No secrets in this folder.**

**Plan (source of truth):** [`docs/plan/13-ghl-n8n-order-sync.md`](../docs/plan/13-ghl-n8n-order-sync.md)

| Status | Detail |
|--------|--------|
| Phase 0 | ✅ Live — prod webhook, GHL fields/tags, confirm SMS, multi-order re-arm |
| Next | G1 — Sierra `place_order` → this webhook automatically |

---
## What this workflow does

1. `POST` webhook `sierra-ghl-sync` (path kept so your existing URL still works)
2. Normalizes the order payload
4. Upserts GHL contact with **custom fields**
5. **Removes** `order-placed` (if present), then **re-adds** tags — so confirm SMS fires on **every** order, not only the first
6. Responds `200`

Tags applied: `voice-order`, `order-placed`, plus `pickup` or `delivery`.  
Source on contact: `Voice Agent`.

---

## Re-import (you already have an older workflow)

1. In n8n, **deactivate** the old workflow (or delete it)
2. **Import from File** → `n8n/sierra-ghl-connection-stub.json`
3. Attach **GHL Private Integration** on **all three** GHL HTTP nodes:
   - `05 · GHL · Upsert Contact + Fields`
   - `06 · GHL · Re-arm SMS (remove order-placed)`
   - `07 · GHL · Apply Order Tags`
4. **Save** → **Active** ON
5. Production URL:

`https://n8n.bizbull.ai/webhook/sierra-ghl-sync`

Canvas includes numbered nodes + sticky notes (Ingest → Transform → Gate → GHL Write → Out). You do **not** need to manually remove tags for retesting.

---

## Test (PowerShell)

```powershell
$body = @{
  schema_version = 1
  event = "order.placed"
  event_id = "test-003"
  tenant_id = "bizbull"
  channel = "phone"
  session_id = "test-session-003"
  customer = @{
    name = "Sierra Test"
    phone_e164 = "+919413752688"
  }
  order = @{
    order_type = "pickup"
    status = "placed"
    clover_order_id = "TEST-CLOVER-003"
    items = @(@{ name = "Butter Chicken"; qty = 1; price = 16.99 })
    total = 16.99
  }
} | ConvertTo-Json -Depth 5

$resp = Invoke-RestMethod -Method Post `
  -Uri "https://n8n.bizbull.ai/webhook/sierra-ghl-sync" `
  -ContentType "application/json" `
  -Body $body

$resp | ConvertTo-Json -Depth 5
```

### Expect in GHL (contact +919413752688)

- Tags include: `voice-order`, `order-placed`, `pickup` (keep any old tags)
- Fields:
  - last_order_id = `TEST-CLOVER-003`
  - last_order_type = `pickup`
  - last_order_status = `placed`
  - last_order_total = `16.99`
  - last_order_summary = `1x Butter Chicken`
  - last_channel = `phone`

---

## Credential reminder

Use on **all GHL HTTP nodes** (Upsert, Remove order-placed, Add Tags):

| Field | Value |
|-------|--------|
| Type | **Header Auth** |
| Credential label | `GHL Private Integration` (any name) |
| **Name** | `Authorization` |
| **Value** | `Bearer pit-001eb302-ba82-4dde-b434-3ba970d3b44a` |

Space after `Bearer` — not `+`. After every re-import, re-select this credential on each GHL node.
