# Bizbull · Sierra Events → GHL Router

Importable n8n workflow. **No secrets in this folder.**

**Plan (source of truth):** [`docs/plan/13-ghl-n8n-order-sync.md`](../docs/plan/13-ghl-n8n-order-sync.md)

| Status | Detail |
|--------|--------|
| Existing `order.placed` | Contact + Voice Orders opp + confirm SMS (Opportunity Created) |
| PR 097 P4 | Authenticated router, durable claims, receipt/tracking/staff-alert branches |
| Setup | [`P4_ROUTER_SETUP.md`](P4_ROUTER_SETUP.md) |
| Next | PR 097 P5 delivery lifecycle updates |

---

## What this workflow does

1. Authenticates `POST /webhook/sierra-ghl-sync` using Header Auth.
2. Validates `schema_version`, `event`, and stable `event_id`.
3. Claims the event in the `sierra_event_claims` Data Table.
4. Routes only `order.placed` into the existing contact/tag/opportunity path.
5. Routes `order.paid` to receipt SMS only.
6. Routes `delivery.dispatched` to tracking SMS only.
7. Routes `delivery.dispatch_required` to the private staff-alert number only.
8. Records unknown or invalid branch events as dead letters with no GHL write.
9. Marks success/failure durably so duplicate events do not repeat side effects.

Tags: `voice-order`, `order-placed`, plus `pickup` or `delivery`.  
Contact source: `Voice Agent`.

---

## Import / update

1. Export a dated backup and **deactivate** the old workflow.
2. **Import from File** → `n8n/sierra-ghl-connection-stub.json`
3. Complete every step in [`P4_ROUTER_SETUP.md`](P4_ROUTER_SETUP.md).
4. Run duplicate, unknown-event, receipt, tracking, and staff-alert sandbox tests.
5. **Save** → **Active** ON only after all checks pass.
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
