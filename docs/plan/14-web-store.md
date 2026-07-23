# Web Store Plan — Classic browse & checkout (production)

> **Status:** **S0→S8 ✅** (PR 089) · **optional pay-now P0→P5 ✅** (PR 090)  
> **Last updated:** 2026-07-23  
> **Goal:** Production-grade **Store** tab at `voice.bizbull.ai` where anyone can browse the Clover menu, build a cart, and place a pickup or delivery order **without** talking to Sierra — **pay later** by default, optional **Pay now** via Clover Hosted Checkout.  
> **Sibling:** [`11-web-order-with-sierra.md`](11-web-order-with-sierra.md) covers the voice tab only.  
> **Payments:** [`15-store-optional-payment.md`](15-store-optional-payment.md) · [`pr/pr_090_store-optional-payment.md`](../../pr/pr_090_store-optional-payment.md)  
> **CRM:** GHL/n8n `order.placed` + `order.paid` (receipt) — [`13-ghl-n8n-order-sync.md`](13-ghl-n8n-order-sync.md) · [`n8n/ORDER_PAID_RECEIPT_SMS.md`](../../n8n/ORDER_PAID_RECEIPT_SMS.md)  
> **POS:** Same Clover submit as voice — [`09-clover-pos.md`](09-clover-pos.md), `restaurant/clover/order_submit.py`.  
> **PR rules:** [`pr/pr_rules.md`](../../pr/pr_rules.md) · ship record [`pr/pr_089_web-store-plan.md`](../../pr/pr_089_web-store-plan.md)

---

## 1. Locked product decisions

| # | Decision | Value |
|---|----------|--------|
| 1 | Channel | Web **Store** tab — no LiveKit / Sierra session for checkout |
| 2 | Fulfillment | **Pickup + delivery**; **pay later** default; optional **Pay now** (PR 090) |
| 3 | Contact | Name + phone always; **address required** when delivery |
| 4 | Architecture | **Thin Store API on VPS** — browser is not trusted for prices / availability / place |
| 5 | CRM | Same n8n → GHL Voice Orders / **Placed** + confirm SMS as voice (**pickup and delivery**) |
| 6 | Auth | **Guest checkout** only in v1 (no accounts) |
| 7 | Voice tab | Unchanged — agent remains cart authority for “Order with Sierra” |
| 8 | Build style | **One PR (089)** — phases S0→S8; push only when asked |

---

## 2. Where we are today

| Piece | State |
|-------|--------|
| Store tab UI | ✅ Full browse → cart → checkout → thank-you (`StoreTab.tsx`) |
| Menu API | `GET /menu` → catalog + optional `image_url` (Clover or demo fill) |
| Store place | `POST /store/checkout` → validate / place → Clover + `notify_order_placed` (`channel=web_store`) |
| Pay now (optional) | `STORE_PAY_NOW_ENABLED=1` → Hosted Checkout URL; webhook → receipt; `order.paid` → n8n (PR 090) |
| GHL / SMS | Confirm on place; receipt SMS after online pay (n8n branch for `order.paid`) |
| Clover submit | `restaurant/clover/order_submit.py` (kill switch `CLOVER_SUBMIT_ORDERS`) |

---

## 3. Architecture

### 3.1 Big picture (left → right)

Customer never talks to Clover or GHL directly. The browser talks only to our Store API.
The API owns validation + place; n8n owns CRM/SMS only.

```
  CUSTOMER                 OUR VPS                         EXTERNAL
  ────────                 ───────                         ────────

  ┌─────────────────┐      ┌──────────────────────┐
  │ voice.bizbull.ai│      │  token_server.py     │
  │                 │      │                      │
  │  Store tab      │      │  GET  /menu ─────────┼──► menu_provider
  │    │            │      │                      │      (Clover cache)
  │    │ browse     │ HTTP │                      │
  │    ▼            │─────►│  POST /store/checkout│
  │  Local cart     │      │         │            │
  │    │            │      │         ▼            │      ┌────────────┐
  │    ▼            │      │   validate + reprice │─────►│ Clover POS │
  │  Checkout form  │      │         │            │      │ (kitchen)  │
  │                 │◄─────│  order_id + summary  │      └────────────┘
  │  Thank-you page │      │         │            │
  └─────────────────┘      │         │ fail-open  │      ┌────────────┐
                           │         ▼            │─────►│ n8n        │
                           │  notify_order_placed │      │    │       │
                           └──────────────────────┘      │    ▼       │
                                                         │ GHL Voice  │
                                                         │ Orders /   │
                                                         │ Placed +   │
                                                         │ confirm SMS│
                                                         └────────────┘

  NO LiveKit / Sierra agent on this path.
```

**Arrow summary**

```
  Browser ──GET /menu──────────────► menu cache ──► Browser (catalog + prices)
  Browser ──POST /store/checkout──► validate ──► Clover (place, fail-closed)
                                      │
                                      └──fail-open──► n8n ──► GHL (SMS / opp)
```

**Why not browser → n8n only?** n8n is excellent for CRM/SMS, but the browser must not be the source of truth for item ids, prices, or kitchen tickets. Spoofed carts would create fake GHL opportunities and wrong Clover tickets.

**Why not reuse the voice agent?** Store must work when LiveKit/agent is down, without paying for a voice session just to tap “Place order.”

### 3.2 Checkout flow (step by step)

```
  1. Customer opens Store tab
           │
           ▼
  2. UI loads menu  ──GET /menu──►  token_server  ──►  menu_provider cache
           │                                              │
           │◄────────────── categories + prices ◄─────────┘
           ▼
  3. Customer adds items to LOCAL cart (qty / spice in UI only)
           │
           ▼
  4. Customer fills checkout (pickup | delivery + name + phone [+ address])
           │
           ▼
  5. UI submits  ──POST /store/checkout──►  Store API
           │
           ├── items empty / bad id / missing spice / no address?
           │         │
           │         ▼
           │    4xx blockers  ──►  UI shows errors (no place)
           │
           └── valid
                     │
                     ▼
              reprice from menu cache (ignore client prices)
                     │
                     ▼
              Clover atomic checkout + create   (if CLOVER_SUBMIT_ORDERS=1)
                     │
                     ├── Clover FAIL ──► 4xx/5xx to UI  (fail-closed; no "confirmed")
                     │
                     └── Clover OK (or log-only place)
                              │
                              ├── notify_order_placed ──► n8n ──► GHL
                              │        (fail-open: CRM error does not undo place)
                              │
                              ▼
                         200 { order_id, summary }
                              │
                              ▼
                         Thank-you page ("pay at pickup / door")
```

### 3.3 Trust boundaries

| Layer | Owns | Must not |
|-------|------|----------|
| Browser | UX cart, forms, local qty | Final prices, availability, place authority |
| `POST /store/checkout` | Validate, totals, place | Start LiveKit / call the voice agent |
| Clover | Kitchen ticket / POS record | CRM messaging |
| n8n / GHL | Contact, opportunity, confirm SMS | Be the sole checkout authority |

```
  TRUSTED FOR MONEY / KITCHEN     UNTRUSTED FOR MONEY / KITCHEN
  ────────────────────────────    ─────────────────────────────
  Store API + menu cache          Browser local cart
  Clover submit                   Client-sent prices
                                  Client-sent "available" flags
```

### 3.4 Fail behavior

| Step | Policy |
|------|--------|
| Menu unavailable | `GET /menu` 503 — Store shows unavailable |
| Validation fail | 4xx with clear blockers (missing spice, bad id, empty cart, no address on delivery) |
| Clover fail | **Fail closed** for place — customer sees error; no fake “order confirmed” |
| n8n / GHL fail | **Fail open** — order still succeeds if Clover (or log-only place) succeeded; CRM errors logged |

---

## 4. API (`POST /store/checkout`)

Implemented on [`token_server.py`](../../token_server.py) (also serves `/menu`).

**Request:**

```json
{
  "items": [
    { "id": "<clover_item_id>", "qty": 2, "modifiers": ["Medium"] }
  ],
  "order_type": "pickup",
  "customer": { "name": "Alex", "phone": "+15875551234" },
  "delivery_address": null,
  "note": "optional allergies / special requests",
  "place": false
}
```

**Server steps:**

1. Load menu cache via `menu_provider`.
2. Reject unknown / unavailable item ids; reprice from cache (ignore client prices).
3. Enforce spice / required modifiers when `has_spice`.
4. Require name + phone; require `delivery_address` when `order_type=delivery`.
5. Compute subtotal / delivery charge / total.
6. `place=false`: return priced summary only.
7. `place=true`: submit via `restaurant/clover/order_submit.py` when `CLOVER_SUBMIT_ORDERS` is on; else log-only place.
8. Call `notify_order_placed(..., channel="web_store")` — **pickup and delivery** both hit the same GHL Placed + confirm SMS path (no second pipeline).
9. Return `{ order_id, summary, status }`.

**Hardening:** CORS POST; per-IP rate limit (`STORE_CHECKOUT_RATE_*`); Caddy `handle /store*` (see `docs/vps-config.md`).

---

## 5. Frontend shape

| Surface | Behavior |
|---------|----------|
| Catalog | Left category list + dish cards from `GET /menu`; search; quiet All/Veg/Non-veg chips |
| Photos | `image_url` from menu (demo Unsplash fill or Clover); cart lines show thumbs |
| Cart (local) | Panel slides in from the right on first add; qty / remove; server revalidates on checkout |
| Modifiers | **Inline spice expand** on the card (no modal) when `has_spice` |
| Checkout | Order type toggle; name; phone; address if delivery; optional note |
| Success | Thank-you with order id / summary; “pay at pickup / door” copy |

UI language: English labels for v1. Same Bizbull menu cache as voice.

---

## 6. Phased delivery (all on PR 089)

Everything stays on branch `pr_089_web-store-plan`. **No push until you say so.**

```
  S0 → S1 → S2 → S3 → S4 → S5 → S6 → S7 → S8  (all ✅ on branch)
```

| Phase | Scope | Done when |
|-------|--------|-----------|
| **S0** | Plan + PR doc + index links | ✅ Docs + ASCII architecture |
| **S1** | Store browse UI | ✅ Categories, items, prices, veg; `GET /menu` |
| **S2** | Client cart + modifiers | ✅ Add, qty, remove, spice when `has_spice` |
| **S3** | Checkout form + validate API | ✅ `POST /store/checkout` validates + priced summary |
| **S4** | Place for real | ✅ Clover + n8n; thank-you + order id |
| **S5** | Production polish | ✅ Rate limit, errors, mobile, Caddy `/store*`, ops docs |
| **S6** | Card grid UI | ✅ Premium dish cards |
| **S7** | Dish photos | ✅ `image_url` on `/menu`; demo fill (`STORE_DEMO_IMAGES`) |
| **S8** | UX polish | ✅ Search; left category nav; diet chips; inline spice; cart slide + thumbs |

### Image path (S7)

| Priority | Source | Notes |
|----------|--------|--------|
| 1 | Clover item `image_url` in menu cache | After merchant uploads in Clover Dashboard + menu sync |
| 2 | Demo Unsplash fill | `restaurant/demo_menu_images.py` (demo only; `STORE_DEMO_IMAGES=0` to disable) |
| 3 | Category / letter placeholder | Frontend fallback when `image_url` is null |

Store UI never hardcodes dish photos — it only renders `image_url` from `/menu` (or cart copy of that URL).

### Confirm SMS (voice + Store)

| Channel | Pickup | Delivery |
|---------|--------|----------|
| Voice (`place_order`) | ✅ | ✅ |
| Web Store (`channel=web_store`) | ✅ | ✅ |

Same n8n → GHL **Opportunity Created** / Voice Orders → confirm SMS. Order type is a field/tag only — it does not skip SMS.

---

## 7. Out of scope (v1)

- LiveKit / Sierra inside Store checkout
- Browser → n8n-only place (no server validation)
- Online card payment (Stripe / Clover Pay)
- Customer accounts / login
- Multi-tenant Store
- Rewriting Order-with-Sierra hybrid cart (voice stays agent-authoritative)
- Delivery zone geofencing / dynamic fees beyond a simple charge
- Store abandoned-cart → GHL G3 (can follow after G3 voice path exists)

---

## 8. Defaults

- Guest only; English UI
- Prices from menu cache (shown in UI; authoritative on server)
- Delivery address required iff delivery
- Allergies / special requests: **optional** free-text note
- Unavailable items: hidden or disabled in catalog

---

## 9. Success criteria

- Guest can place a real pickup or delivery order from Store without a call
- Kitchen / POS path matches voice when Clover submit is enabled
- Confirm SMS + Voice Orders / Placed opportunity appear via existing n8n workflow (**pickup and delivery**)
- Spoofed client prices/ids cannot create a confirmed order
- Voice “Order with Sierra” behavior unchanged

---

## 10. Doc map

| Doc | Role |
|-----|------|
| **This file** | Store product + architecture + S0–S8 |
| [`11-web-order-with-sierra.md`](11-web-order-with-sierra.md) | Voice tab only |
| [`13-ghl-n8n-order-sync.md`](13-ghl-n8n-order-sync.md) | CRM / SMS / opportunities |
| [`09-clover-pos.md`](09-clover-pos.md) | Clover order submit |
| [`06-milestones.md`](06-milestones.md) | Milestone index |
| [`LOCAL_DEV.md`](../LOCAL_DEV.md) | Local Store run (token + web) |
| [`vps-config.md`](../vps-config.md) | Caddy `handle /store*` |
