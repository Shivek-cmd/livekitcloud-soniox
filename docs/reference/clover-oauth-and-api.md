# Clover OAuth, REST API & permissions

> Captured 2026-06-27 from Clover Platform Docs (`clover-development-basics-web-app`,
> `oauth-intro`, `generate-expiring-tokens-using-v2-oauth-flow`, `using-api-tokens`,
> `permissions`, `api-usage-rate-limits`, `webhooks`).
> Why we care: multi-tenant SaaS needs **per-restaurant OAuth** and reliable server-side API access.

## REST API basics

- Base pattern: `GET|POST|DELETE https://{base}/v3/merchants/{mId}/{resource}`
- Query params: `?field=value&expand=...&filter=...&limit=...&offset=...`
- Amounts are in **cents** (e.g. $20.99 → `2099`).
- Timestamps are **Unix milliseconds**.
- Use `expand` to pull nested objects (e.g. `?expand=modifierGroups`, `?expand=customer`).

### Environment URLs

| Purpose | Sandbox | Production (NA) |
|---|---|---|
| REST API | `apisandbox.dev.clover.com` | `api.clover.com` |
| OAuth authorize | `sandbox.dev.clover.com/oauth/v2/authorize` | `www.clover.com/oauth/v2/authorize` |
| OAuth token | `apisandbox.dev.clover.com/oauth/v2/token` | `api.clover.com/oauth/v2/token` |
| OAuth refresh | `apisandbox.dev.clover.com/oauth/v2/refresh` | `api.clover.com/oauth/v2/refresh` |

## Authentication modes

### Sandbox (development)

Generate a **merchant-specific test API token** from the test Merchant Dashboard.
Use directly as `Authorization: Bearer {auth_token}` — no OAuth flow needed.

```bash
curl -H "Authorization: Bearer {auth_token}" \
  "https://apisandbox.dev.clover.com/v3/merchants/{mId}"
```

`{mId}` appears in the Merchant Dashboard URL.

### Production (multi-tenant SaaS)

**v2/OAuth expiring tokens** are required (legacy non-expiring tokens deprecated).

Flow:
1. Merchant installs app from App Market (or connects via your site).
2. Clover redirects to your **Alternate Launch Path** with `code` + `merchant_id`.
3. Your server POSTs to `/oauth/v2/token` → receives `access_token` + `refresh_token` (both expire).
4. Store tokens **per merchant tenant**; refresh before expiry via `/oauth/v2/refresh`.

**High-trust apps** (our backend server): auth code flow with `client_id` + `client_secret` + `code`.

**Low-trust apps** (SPA/mobile): auth code flow with **PKCE** (`code_verifier` / `code_challenge` SHA256).

> Do not store tokens in client-side code or commit to git. All Clover API calls from Sierra
> should be **server-to-server** (agent worker or dedicated order service on VPS).

## Permissions Sierra needs

Request only what we use; DevRel requires justification for each permission.

| Permission | Why Sierra needs it |
|---|---|
| **Read inventory** | Pull menu (items, categories, modifiers, stock/availability) |
| **Write inventory** | Optional — only if we manage availability (86'd items); defer v1 |
| **Read orders** | Verify placed orders, audit trail |
| **Write orders** | Create atomic orders, trigger kitchen print |
| **Read customers** | Look up customer by phone before creating duplicate |
| **Write customers** | Create/link customer on order (name + phone from voice) |
| **Read merchant** | Order types, tax config, business info |

**Not needed for v1:** Write payments (pay at pickup), Write employees, Ecommerce API.

If permissions change after a merchant installed the app, they must **uninstall and reinstall**.

## Rate limits

| Limit | Per app | Per token |
|---|---|---|
| Requests/sec | 50 | 16 |
| Concurrent in-flight | 10 | 5 |

On `429 Too Many Requests`:
- Pause ≥1s; exponential backoff if repeated.
- Response headers: `X-RateLimit-tokenLimit`, `X-RateLimit-crossTokenLimit`, etc.
- Concurrent 429 includes `retry-after: N` (seconds).

**Best practices for Sierra:**
- **Webhooks** instead of polling inventory.
- Cache menu locally; refresh on webhook or TTL.
- Use `modifiedTime` filters for incremental sync.
- Stagger multi-merchant backfill; avoid peak hours.

## Webhooks (menu + order sync)

HTTPS callback URL required (localhost won't work — use ngrok for dev).

Setup (Developer Dashboard → App Settings → Webhooks):
1. Enter HTTPS webhook URL → Send Verification Code.
2. POST arrives with `{"verificationCode":"..."}` → paste back → Verify → Save.
3. Subscribe to event types (each needs matching Read permission).

Verify origin: check `X-Clover-Auth` header (Clover Auth Code from dashboard).

### Event type keys (objectId prefix)

| Key | Event | Permission needed |
|---|---|---|
| `I` | Inventory item CRUD | Read inventory |
| `IC` | Inventory category | Read inventory |
| `IG` | Modifier group | Read inventory |
| `IM` | Modifier | Read inventory |
| `O` | Order CRUD | Read orders |
| `C` | Customer | Read customers |
| `P` | Payment | Read payments |
| `M` | Merchant property | Read merchant |

Message shape:
```json
{
  "appId": "APP_ID",
  "merchants": {
    "MERCHANT_ID": [
      {"objectId": "I:ITEM_UUID", "type": "UPDATE", "ts": 1537970958000}
    ]
  }
}
```

For Sierra: subscribe to **`I`, `IG`, `IM`, `IC`** (menu changes) and optionally **`O`** (order status).

## Security guidelines (from Clover)

- Server-to-server requests; never expose tokens to browser/frontend.
- Never collect card data in our app (PCI — use Clover Ecommerce if we add phone payment later).
- Securely store cached merchant data and OAuth refresh tokens (encrypted at rest).

## Related docs

- [clover-platform-overview.md](clover-platform-overview.md)
- [clover-inventory-menu.md](clover-inventory-menu.md)
- [clover-orders-api.md](clover-orders-api.md)
