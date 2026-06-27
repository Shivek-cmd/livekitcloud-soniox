# Clover × Sierra — integration planning notes

> Captured 2026-06-27 — internal planning doc derived from Clover docs + current Sierra architecture.
> **Not implemented yet.** Use this when designing the POS milestone; update as decisions are made.

## Current Sierra state (pre-POS)

| Component | Today | With Clover |
|---|---|---|
| Menu | Static `restaurant/menu.py` | Synced from Clover Inventory API |
| Cart | In-memory in agent session | Same during call; validated against Clover catalog |
| Place order | Local tool, no persistence | Atomic order → Clover + kitchen print |
| Tenants | Single (Bizbull) | Per-restaurant OAuth + config |
| Payments | None (confirm verbally) | Pay at pickup (v1); Ecommerce later |

Existing seam: `restaurant/voice_stack.py` is already a per-tenant factory — mirror with
`build_menu_client(tenant)` and `build_order_client(tenant)`.

## Target flow (phone/web → Clover)

```
Caller speaks to Sierra
    │
    ▼
Agent session cart (validated against cached Clover menu)
    │
    ▼
Verbal confirmation (items, modifiers, name, phone, pickup time)
    │
    ▼
POST atomic_order/checkouts  → speak total from Clover
    │
    ▼
Customer confirms
    │
    ▼
POST atomic_order/orders     → order id
    │
    ▼
POST print_event             → kitchen ticket
    │
    ▼
Sierra: "Order #XYZ confirmed, ready in ~N minutes"
```

## v1 scope (recommended)

**In:**
- Pickup orders only (single order type per tenant)
- Single location per Clover merchant
- Atomic orders with inventory item IDs + modifier IDs
- Menu read + webhook-driven cache refresh
- Customer create/link by phone
- Kitchen print via `print_event`
- Sandbox first, then one production pilot merchant

**Out (defer):**
- Delivery / address capture by voice
- Payment on call (Ecommerce API / 3DS)
- Multi-location chains under one tenant
- Write inventory (86 items from Sierra)
- Clover Dining table assignment
- Refunds / voids from Sierra

## Multi-tenant data model (sketch)

Per restaurant tenant:
```
tenant_id
clover_merchant_id (mId)
oauth_access_token (encrypted)
oauth_refresh_token (encrypted)
oauth_expires_at
order_type_id          # pick-up
order_type_delivery_id
menu_cache_json        # Clover sync + speak_as + aliases per item
menu_cache_updated_at
voice_config           # STT/TTS (existing voice_stack seam)
phone_number           # Twilio → LiveKit
```

OAuth tokens must **never** live in `.env` alongside shared keys — per-tenant storage (DB).

## Edge cases to design for

| Edge | Handling |
|---|---|
| Item 86'd mid-call | Re-check `available` / stock at checkout; offer alternative |
| STT misheard item name | Fuzzy match + confirm item back; never guess UUID |
| Modifier min/max | Enforce group rules before add-to-cart |
| Clover API down | Don't confirm order; queue retry or "team will call back" |
| Duplicate submit | Idempotency key per session (client order ref in `note` field?) |
| Customer hangs up before confirm | No order submit until explicit verbal yes |
| Clover accepts, print fails | Order exists; log print failure; optional retry print |
| Staff edits order in Register | After submit, Clover is source of truth |
| Wrong total spoken | Always use checkout endpoint total, not mental math |
| Sandbox vs prod token mix | Strict env separation in config |

## App permissions checklist (Clover app settings)

- Read inventory ✓
- Write orders ✓
- Read orders ✓
- Read customers ✓
- Write customers ✓
- Read merchant ✓
- Webhooks: I, IG, IM, IC, O

## Sandbox next steps (when we start building)

1. Confirm sandbox `mId` + test API token work: `GET /v3/merchants/{mId}/items`
2. Import or create Punjabi-restaurant-like test menu with modifier groups (spice level, etc.)
3. Create pick-up **order type**; note its id
4. Test atomic checkout → create → print_event end-to-end
5. Register webhook URL (ngrok) for inventory change events

## Open questions (for planning session)

1. **Private app vs App Market** for early pilots? (Private = faster, per-merchant install)
2. **Where does order service live?** — inside `agent.py` tools vs separate FastAPI service?
3. **Menu alias mapping** — UI for restaurant owners to map voice names → Clover items?
4. **Order notes field** — put phone-order metadata (channel=sierra, call_id) in order `note`?
5. **Currency/locale** — CAD formatting in TTS; Clover prices already in cents

## Related docs

- [../plan/01-overview.md](../plan/01-overview.md) — Sierra product overview
- [../plan/09-clover-pos.md](../plan/09-clover-pos.md) — **canonical plan** (architecture, phases, decisions)
- [../plan/06-milestones.md](../plan/06-milestones.md) — Phase 8 tracker
- [clover-platform-overview.md](clover-platform-overview.md)
- [clover-oauth-and-api.md](clover-oauth-and-api.md)
- [clover-inventory-menu.md](clover-inventory-menu.md)
- [clover-orders-api.md](clover-orders-api.md)
