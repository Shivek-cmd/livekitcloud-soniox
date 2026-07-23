# Bizbull · Voice Order → GHL

Importable n8n workflow. **No secrets in this folder.**

**Plan (source of truth):** [`docs/plan/13-ghl-n8n-order-sync.md`](../docs/plan/13-ghl-n8n-order-sync.md)

| Status | Detail |
|--------|--------|
| Phase 0 / G1 / G2b | ✅ Live — contact + Voice Orders opp + confirm SMS (Opportunity Created) |
| Store pay-now receipt | 🔶 PR 090 P4 — Sierra emits `order.paid`; n8n/GHL branch TBD — see [`ORDER_PAID_RECEIPT_SMS.md`](ORDER_PAID_RECEIPT_SMS.md) |
| Next | **G3** abandoned / **G4** completed |

---

## What this workflow does

1. `POST` webhook `sierra-ghl-sync` (path kept so existing URL still works)
2. Normalizes the order payload
3. Upserts GHL contact with **custom fields**
4. **Removes** `order-placed`, then **re-adds** tags (labeling; SMS is **not** tag-triggered)
5. Searches open **Abandoned** opps for same contact + `session_id`; **moves to Placed** or **creates** new Placed opp (`Voice Orders` pipeline — plan §7.2)
6. GHL workflow (**Opportunity Created** / Voice Orders) sends confirm SMS
7. Responds `200` (fail-open)

Tags: `voice-order`, `order-placed`, plus `pickup` or `delivery`.  
Contact source: `Voice Agent`.

---

## Re-import (G2b)

1. In n8n, **deactivate** the old workflow (or delete it)
2. **Import from File** → `n8n/sierra-ghl-connection-stub.json`
3. Attach **GHL Private Integration** on **all** GHL HTTP nodes:
   - `05 · GHL · Upsert Contact + Fields`
   - `06 · GHL · Re-arm SMS (remove order-placed)`
   - `07 · GHL · Apply Order Tags`
   - `09 · GHL · Search Abandoned Opp`
   - `11a · GHL · Move Opp → Placed`
   - `11b · GHL · Create Opp Placed`
4. **Save** → **Active** ON
5. Production URL:

`https://n8n.bizbull.ai/webhook/sierra-ghl-sync`

**n8n 2.12 note:** Code nodes in “Run Once for Each Item” must use `$('Node').item` / `$input.item` — not `.first()`.

---

## Test (PowerShell)

```powershell
$body = @{
  schema_version = 1
  event = "order.placed"
  event_id = "test-g2b-001"
  tenant_id = "bizbull"
  channel = "phone"
  session_id = "test-session-g2b-001"
  customer = @{
    name = "Sierra Test"
    phone_e164 = "+919413752688"
  }
  order = @{
    order_type = "pickup"
    status = "placed"
    clover_order_id = "TEST-CLOVER-G2B-001"
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

- Tags: `voice-order`, `order-placed`, `pickup`
- Contact fields: `last_order_*` as before
- **Opportunities → Voice Orders → Placed:** name like `pickup · Sierra · 1x Butter Chicken`, value `16.99`, custom fields `event_id` / `clover_order_id` / `session_id` / `order_summary`
- Response includes `opp_action` (`created_placed` or `moved_abandoned_to_placed`) and `opp_id`
- Confirm SMS still fires (tag path unchanged)

---

## Credential reminder

Use on **all GHL HTTP nodes**:

| Field | Value |
|-------|--------|
| Type | **Header Auth** |
| Credential label | `GHL Private Integration` |
| **Name** | `Authorization` |
| **Value** | `Bearer <your-PIT>` |

Space after `Bearer`. After every re-import, re-select this credential on each GHL node.
