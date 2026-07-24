# Store Uber Direct — Plan (courier fulfillment for delivery)

> **Status:** ✅ **P0–P5 complete** (code) — flip `STORE_UBER_DIRECT_ENABLED=1` + n8n SMS branch when testing  
> **Last updated:** 2026-07-24
> **Channel:** Web **Store** tab only (`voice.bizbull.ai`) — **not phone / Sierra voice**  
> **Depends on:** PR 089 Store · PR 090 optional pay-now — [`14-web-store.md`](14-web-store.md) · [`15-store-optional-payment.md`](15-store-optional-payment.md)  
> **CRM:** [`13-ghl-n8n-order-sync.md`](13-ghl-n8n-order-sync.md)  
> **POS:** [`09-clover-pos.md`](09-clover-pos.md)  
> **PR:** [`pr/pr_093_store-uber-direct.md`](../../pr/pr_093_store-uber-direct.md)  
> **Branch:** `pr_093_store-uber-direct`  
> **Environment:** Uber Direct **test / sandbox mode** first

---

## 1. Goal (one sentence)

On Store **delivery** checkout, use **Uber Direct** to quote a real courier fee/ETA and (after the kitchen order is placed) dispatch an Uber courier — customer still orders on Bizbull’s Store, not on Uber Eats.

---

## 2. Locked decisions

| # | Decision | Value | Status |
|---|----------|--------|--------|
| 1 | Scope | **Store only** — no phone / Sierra voice | ✅ Locked |
| 2 | Mode | Uber Direct **sandbox** until you say go live | ✅ Locked |
| 3 | Product role | Sierra = **integration partner**; each restaurant owns menu, POS, Uber bill / courier headache | ✅ Locked |
| 4 | This PR tenancy | **Bizbull only** — sandbox values in `.env` as default tenant; schema/design stays tenant-ready | ✅ Locked |
| 5 | Uber credentials | Per-tenant eventually (same idea as Clover on `Tenant`); **now** Bizbull values in env | ✅ Locked |
| 6 | Order types | Uber only for `delivery`; **pickup unchanged** | ✅ Locked |
| 7 | Who pays Uber | **Restaurant** (Bizbull’s Direct billing). Customer pays restaurant (pay later / pay now) | ✅ Locked |
| 8 | Fee policy (v1) | **A — pass-through** Uber quote to customer (restaurant doesn’t subsidize via platform) | ✅ Locked |
| 9 | Fee fallback | When Direct off / quote fails → tenant `delivery_charge` (Bizbull today = $5) | ✅ Locked |
| 10 | Quote timing | Quote **before** Place; show fee + ETA; quote ~15 min TTL | ✅ Locked |
| 11 | Dispatch timing | Create delivery **after** kitchen place; prep **25 min** (20–30) | ✅ Locked |
| 12 | Restaurant pickup | `99 Wye Rd #31, Sherwood Park, AB T8B 1C9, Canada` | ✅ Locked for now |
| 13 | Customer dropoff | Structured fields (street, city, province, postal) | ✅ Locked |
| 14 | Tracking | Success UI **+ tracking SMS via n8n in this PR** | ✅ Locked |
| 15 | Kill switch | `STORE_UBER_DIRECT_ENABLED=0` default | ✅ Locked |
| 16 | Build style | **One PR (093)** — P0→P5; approval after each phase | ✅ Locked |
| 17 | Pay now | Unchanged (PR 090/091) | ✅ Locked |

### 2.1 Fee policy (locked = A for v1)

Restaurant owns the Uber invoice. Platform only surfaces the quote.

| Option | Customer sees | Restaurant effect | v1 |
|--------|---------------|-------------------|-----|
| **A — Pass-through** | Exact Uber quote | Break-even on courier | ✅ **Ship this** |
| B — Markup | Quote + $N | Extra margin | Later (per-tenant) |
| C — Flat | Always tenant flat fee | May lose money vs Uber | Fallback only when quote fails / Direct off |
| D — Cap | min(quote, cap) | Eats overage | Later (per-tenant) |

**Later multi-tenant:** fee mode (A/B/C/D) + markup/cap live on the tenant record next to `delivery_charge` — not in this PR’s schema migration unless needed; env/Bizbull default is enough to ship Store.

### 2.2 Tenancy note (important)

`restaurant/tenants/store.py` already has per-tenant `delivery_charge` / Clover fields (“schema ready for N tenants later”).  
This PR **does not** build full multi-restaurant Uber onboarding UI. It:

1. Implements Store ↔ Uber Direct for **Bizbull** via env defaults.  
2. Keeps config **tenant-shaped** (read through a small helper that today returns Bizbull/env; later reads `Tenant` + per-tenant Uber fields).

Uber Direct headache (billing, coverage, failed drops) stays on the **restaurant**, not on Chrishan as partner.
---

## 3. What Uber Direct is (short)

White-label courier API: customer buys on **your** Store; Uber only moves the bag restaurant → customer.  
**Not** Uber Eats marketplace (no listing, no % food commission).  
API shape: **OAuth** → **Create Quote** → **Create Delivery** (with `quote_id`) → **track / webhooks**.

Docs: [Uber Direct overview](https://developer.uber.com/docs/deliveries/overview) · [Get started](https://developer.uber.com/docs/deliveries/get-started)

---

## 4. Customer flow (Store delivery)

```
Browse → cart → choose Delivery
  → name + phone + structured address
  → [NEW] Request Uber quote (pickup = restaurant, dropoff = customer)
       → Show fee + ETA (or fall back to flat $5 if Direct off / quote fails)
  → Payment choice (pay later / pay now — unchanged)
  → Place order
       → Clover kitchen ticket (as today)
       → Confirm SMS (as today)
       → [NEW] Create Uber delivery (sandbox) using quote_id + prep buffer
       → Thank-you: order id + tracking link (when available)
  → [NEW] Status webhooks (courier assigned → picked up → delivered / failed)
```

**Pickup path:** identical to today — no Uber calls.

**Pay now + delivery:** payment flow unchanged; Uber create still happens after kitchen place (same as pay later). Pay-first kitchen wait (PR 091) still applies: create Uber only when the kitchen order actually exists.

---

## 5. Architecture (target)

```
  Store checkout (browser)
       │
       ├── GET  /store/config          → uber_direct_enabled, prep_minutes, …
       ├── POST /store/delivery-quote  → Uber Create Quote (test)
       │         returns fee, eta, quote_id, expires_at
       │
       └── POST /store/checkout
              │
              ├── validate + reprice (use quoted fee if quote_id valid)
              ├── Clover atomic order (kitchen) — as today
              ├── n8n order.placed → confirm SMS — as today
              │
              └── if delivery + Direct enabled + valid quote
                     ├── Create Uber delivery (sandbox)
                     ├── Persist delivery_id + tracking_url
                     └── return tracking_url in checkout response

  Uber → POST /store/uber-direct-webhook  (status changes)
              └── update local delivery state (fail-open)
```

Browser never talks to Uber. Token server owns OAuth + quote/create/webhook.

### 5.1 Module sketch (implementation later — not now)

| Piece | Likely home |
|-------|-------------|
| OAuth + quote + create + get | `restaurant/uber_direct/` (or `restaurant/integrations/uber_direct.py`) |
| Pending quote / delivery map | small JSON store (same pattern as `store_pay_now_store.py`) |
| HTTP routes | `token_server.py` under `/store/*` |
| UI | `web/src/components/StoreTab.tsx` — structured address + quote display |
| Env | `.env.example` only (never commit secrets) |

### 5.2 Relationship to today’s flat fee

| `STORE_UBER_DIRECT_ENABLED` | Delivery fee |
|-----------------------------|--------------|
| `0` | Today’s `DELIVERY_CHARGE` ($5) |
| `1` | Uber quote when available; else fail-open to $5 + log |

---

## 6. Phases (step by step — approval gate each time)

### P0 — Plan + branch ✅ decisions locked

- [x] Plan doc + PR doc + branch `pr_093_store-uber-direct`
- [x] Locked decisions (§2) including fee **A** + Bizbull/env tenancy
- [x] Sandbox credentials + pickup address in `.env`
- [ ] Pickup phone / lat-lng optional later
- **Stop. No code until you approve P1.**

### P1 — Uber client + quote API (no UI dispatch yet) ✅

**Done:**
- `restaurant/uber_direct/` — config (kill switch, pickup from env, fee policy A), address validation, OAuth + `create_delivery_quote`, `request_store_delivery_quote`
- `POST /store/delivery-quote` on token server (structured dropoff → fee, ETA, `quote_id`)
- `GET /store/config` exposes `uber_direct_enabled`, prep minutes, fallback fee (no secrets)
- Kill switch off → `enabled=false` + flat fallback; no Uber call
- Unit tests: `tests/test_uber_direct.py` (11 passed, mocked HTTP)

**Stop for approval before P2 (structured address UI).**

### P2 — Structured delivery address in Store UI ✅

**Done:**
- Store checkout: street, unit, city, province, postal, country (default CA), delivery notes
- Client validation (CA postal) before review/place
- Composes one-line `delivery_address` for existing Clover / n8n / checkout API
- Delivery notes folded into order `note`
- Helpers: `web/src/lib/storeDeliveryAddress.ts`

**Stop for approval before P3** — continuing per your “complete the phases” go-ahead.

### P3 — Wire quote into checkout pricing ✅

**Done:**
- Quote store `data/store_uber_quotes.json` (gitignored)
- Checkout accepts `uber_quote_id`; applies pass-through fee when valid; fail-open to flat fee
- Store UI debounced quote fetch + live delivery line + hint
- Summary echoes `uber_quote_id` / `uber_quote_applied`

### P4 — Create delivery after kitchen place ✅

**Done:**
- `create_delivery` + `dispatch_store_delivery` (prep buffer from env)
- After pay-later place and pay-now fulfill — fail-open
- Success UI **Track delivery** when `uber_tracking_url` present

### P5 — Webhooks + tracking SMS + hardening ✅

**Done:**
- `POST /store/uber-direct-webhook` + `GET /store/delivery-status`
- `delivery.dispatched` n8n emit + guide `n8n/DELIVERY_DISPATCHED_TRACKING_SMS.md`
- `.gitignore` for quote/delivery JSON stores; config flags on `/store/config`

### P3 — Wire quote into checkout pricing

**Goal:** Delivery total uses Uber fee when quote is fresh; place still works if Direct off.

- Checkout accepts `uber_quote_id` (optional)
- Re-validate quote expiry + fee before place
- Summary shows `delivery_charge` from quote
- Fail-open path documented

**Stop for approval.**

### P4 — Create delivery after kitchen place

**Goal:** After Clover place succeeds, create sandbox delivery with prep buffer.

- `pickup_ready` / prep minutes from env
- Persist `delivery_id`, `tracking_url`, status
- Checkout response includes tracking URL
- Success UI: “Track delivery” when present
- Fail-open: kitchen + SMS still succeed if Uber create fails

**Stop for approval.**

### P5 — Webhooks + hardening + docs

**Goal:** Status updates + production-ready ops notes (still test mode until you flip).

- `POST /store/uber-direct-webhook` (verify signature if Uber provides one)
- Status store + optional `GET /store/delivery-status`
- Rate limits, `.env.example`, `LOCAL_DEV.md` / `vps-config.md` notes
- Test checklist
- **Tracking SMS in-scope:** emit n8n event (e.g. `delivery.dispatched` / include `tracking_url` on place) → GHL SMS with track link (same pattern as `order.paid`)

**Stop — ready for your review / merge when you say.**

---

## 7. Kill switches / env (planned)

| Env | Effect |
|-----|--------|
| `STORE_UBER_DIRECT_ENABLED` | `0` (default) = today’s flat fee, no Uber calls |
| `UBER_DIRECT_CUSTOMER_ID` | From Direct dashboard (Developer) |
| `UBER_DIRECT_CLIENT_ID` | OAuth client id |
| `UBER_DIRECT_CLIENT_SECRET` | OAuth secret |
| `UBER_DIRECT_ENV` | `sandbox` \| `production` (default `sandbox`) |
| `UBER_DIRECT_PICKUP_*` | Restaurant name, phone, structured address, lat/lng |
| `UBER_DIRECT_PREP_MINUTES` | Buffer before courier pickup (e.g. `25`) |
| `UBER_DIRECT_WEBHOOK_SECRET` | If applicable |
| Existing `DELIVERY_CHARGE` | Fallback when Direct off / quote fail |
| Existing `CLOVER_SUBMIT_ORDERS` / `N8N_SYNC_ENABLED` | Unchanged |

Exact env names can be adjusted in P1; secrets never committed.

---

## 8. Out of scope (this PR)

- Phone / Sierra voice delivery dispatch
- Uber Eats **marketplace** listing / menu sync
- Own-driver fleet logic / hybrid routing
- Changing pay-now / Hosted Checkout (PR 090/091)
- Tips, proof-of-delivery UI beyond tracking URL
- Multi-restaurant / multi-tenant Direct accounts
- Production go-live (separate approval after sandbox works)

---

## 9. What I need from you (ops)

Provide these when ready (chat / 1Password — **not** committed to git):

### 9.1 Uber Direct (test mode)

| Item | Status |
|------|--------|
| Customer ID / Client ID / Client secret | ✅ in local `.env` (you may rotate later) |
| `UBER_DIRECT_ENV=sandbox` | ✅ |
| Confirm Canada sandbox deliveries work | ⬜ verify on first live quote in P1 |

### 9.2 Restaurant pickup

| Item | Value / status |
|------|----------------|
| Address | ✅ `99 Wye Rd #31, Sherwood Park, AB T8B 1C9, Canada` |
| Name | ✅ `Bizbull Restaurant` (change in env if needed) |
| Pickup phone | ⬜ still empty in `.env` — add when you have it |
| Lat / lng | ⬜ optional for now — add if Uber rejects address-only quotes |
| Prep minutes | ✅ `25` (hardcoded mid of 20–30) |

### 9.3 Product choices before P1

1. Fee policy — ✅ **A pass-through** for v1  
2. Prep minutes — ✅ 25  
3. Tracking SMS in this PR — ✅ yes  
4. Tenancy — ✅ Bizbull/env now; per-tenant-shaped for later  

### 9.4 Optional later

- Production credentials (only after sandbox pilot)  
- Rotate Client secret (recommended after paste in chat)  
- Tenant DB columns for Uber client ids / fee mode (B/C/D) when onboarding restaurant #2  
- Per-restaurant Uber Direct org under partner account 

---

## 10. How we work on this PR

1. Doc first (this plan + PR doc) → branch name matches.  
2. **One phase at a time.** After each phase: show what changed → **wait for your approval** → next phase.  
3. No push / no GitHub PR / no VPS deploy unless you ask.  
4. Never commit `.env` / Uber secrets.  
5. Sandbox only until you explicitly approve production.

---

## 11. Test checklist (filled in as phases land)

### Unit
```
PYTHONPATH=. uv run --with pytest pytest tests/test_uber_direct*.py tests/test_store_checkout.py -q
```

### Local manual (after P4)
1. Token server + `cd web && npm run dev`  
2. Pickup order → no Uber calls  
3. Delivery + Direct off → flat $5 as today  
4. Delivery + Direct on → quote → place → tracking URL (sandbox)  
5. Quote expire / Uber down → fail-open path  

### Phone
Unchanged — out of scope.

---

## Related

| Doc | Role |
|-----|------|
| [`14-web-store.md`](14-web-store.md) | Store browse/checkout baseline |
| [`15-store-optional-payment.md`](15-store-optional-payment.md) | Pay later / pay now |
| [`13-ghl-n8n-order-sync.md`](13-ghl-n8n-order-sync.md) | Confirm SMS |
| [`pr/pr_093_store-uber-direct.md`](../../pr/pr_093_store-uber-direct.md) | Ship record for this PR |
| [Uber Direct get started](https://developer.uber.com/docs/deliveries/get-started) | Official API flow |
