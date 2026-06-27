# Clover Platform — overview & data model

> Captured 2026-06-27 from Clover Platform Docs (`https://docs.clover.com/dev/docs/home`,
> `clover-data-model`, `select-an-integration`, `canadian-merchants`, `making-rest-api-calls`).
> Full doc index (Markdown): `https://docs.clover.com/llms.txt`
> Why we care: Sierra needs a **production POS sink** — menu from Clover, orders back to Clover.

## What Clover is

Clover is an **open Android-based POS platform** (Fiserv) for SMB restaurants and retail.
Third-party developers build apps on the **Clover App Market** or private integrations.
Merchants install apps and grant **OAuth permissions** per data category (inventory, orders, etc.).

Supported regions include **United States, Canada**, UK/Ireland, Germany/Austria, Argentina
(expanding). Our target market is **Canadian Punjabi restaurants** → Canada docs matter.

## Integration paths (decision tree)

Clover offers several integration types. For Sierra (external voice agent, no Clover device UI):

| Path | What it is | Relevant to Sierra? |
|---|---|---|
| **REST API + OAuth** | Server-side web app; read/write merchant data | **Yes — primary path** |
| Ecommerce API | Card-not-present payments, hosted checkout | Maybe later (pay-on-call) |
| Android SDK | On-device Clover apps | No (we run on our VPS) |
| Semi-integration / REST Pay | External POS talks to Clover device for payment | No for v1 (we submit orders, pay at pickup) |
| Order Connector (Android) | On-device order sync | No |

**Our integration type:** REST API web app — OAuth per merchant, server-to-server API calls.

## Clover data model (relationships)

Everything hangs off **Merchant** (`merchantId` / `mId` UUID):

```
Merchant (mId)
├── Inventory (items, categories, modifier groups, modifiers, tags, stock)
├── Orders (line items, modifiers, discounts, taxes, service charges, payments)
├── Customers (optional link to orders)
├── Employees (who took the order)
└── Payments (linked to orders)
```

Key concepts for restaurants:

- **Item** — menu entry (name, price in **cents**, categories, tax rates).
- **Modifier group** — e.g. "Spice level", "Salad add-ins"; has `minRequired` / `maxAllowed`.
- **Modifier** — option within a group (e.g. "Mild", "Extra paneer"); adds price in cents.
- **Item ↔ modifier group** — associated via `item_modifier_groups` endpoint.
- **Order type** — merchant-specific classification: online, delivery, pick-up, dine-in.
- **Order cart** — temporary pre-checkout state (`state: active`).
- **Order** — finalized purchase (`state: open`, `closed`, `voided`, etc.).
- **Line item** — one inventory item (or ad-hoc item) on an order, with optional modifications.

Orders **sync automatically** between Clover servers and merchant devices (Register, kitchen printers).

## Developer environments

| Environment | REST base URL | Auth |
|---|---|---|
| **Sandbox** | `https://apisandbox.dev.clover.com` | Merchant-specific **test API token** (no OAuth required for dev) |
| **Production NA** | `https://api.clover.com` | **v2/OAuth expiring tokens** (access + refresh) |
| **Production EU** | `https://api.eu.clover.com` | Same OAuth pattern |
| **Production LATAM** | `https://api.la.clover.com` | Same OAuth pattern |

- Sandbox + production share the **Global Developer Dashboard** (`clover.com/global-developer-home`).
- **Never use sandbox test tokens in production.**
- All REST API traffic is **HTTPS only**, request/response **JSON**.
- Every request needs `Authorization: Bearer {token}` and `{mId}` in the path.

## Canada-specific notes

Source: `canadian-merchants`

- Merchants can process **CAD or USD** (merchant-config dependent).
- Devices support **English and French** payment flows.
- **Interac debit** has regional SDK limitations (auth/pre-auth not supported, vault not supported).
- Supported merchant plans include **Register, Counter Service, Table Service Restaurant**.
- For our v1 (order submission, pay at pickup): **REST Orders API is the focus**, not payment SDK.

## Sandbox workflow (what we have now)

1. Create global developer account + sandbox app.
2. Install app on **test merchant**; set **Requested Permissions** (Read/Write inventory + orders).
3. Generate **merchant-specific test API token** from test Merchant Dashboard.
4. Import sample inventory or build menu in sandbox.
5. Test atomic order creation against sandbox base URL.

## App launch path (production SaaS)

High-level checklist from Clover docs:

1. Build + test in sandbox.
2. Set app permissions with **justifications** (DevRel reviews during approval).
3. Configure OAuth (Alternate Launch Path, CORS domain).
4. Submit developer account + app for approval.
5. Publish to Clover App Market (or use **private app** per merchant).
6. Merchants install → OAuth → we store refresh tokens per tenant.

## Related docs in this repo

- [clover-oauth-and-api.md](clover-oauth-and-api.md) — auth, rate limits, permissions
- [clover-inventory-menu.md](clover-inventory-menu.md) — menu sync for Sierra
- [clover-orders-api.md](clover-orders-api.md) — order creation flow
- [clover-sierra-integration-notes.md](clover-sierra-integration-notes.md) — how this maps to our agent
