# Store Optional Payment — Plan (pay now or pay later)

> **Status:** ✅ **P0–P5 complete** (code) — review / commit / deploy when you ask  
> **Last updated:** 2026-07-23  
> **Channel:** Web **Store** tab only (`voice.bizbull.ai`) — **not phone / Sierra voice**  
> **Depends on:** PR 089 Store (merged) — [`14-web-store.md`](14-web-store.md)  
> **CRM:** [`13-ghl-n8n-order-sync.md`](13-ghl-n8n-order-sync.md) · [`n8n/ORDER_PAID_RECEIPT_SMS.md`](../../n8n/ORDER_PAID_RECEIPT_SMS.md)  
> **POS:** [`09-clover-pos.md`](09-clover-pos.md)  
> **PR:** [`pr/pr_090_store-optional-payment.md`](../../pr/pr_090_store-optional-payment.md)  
> **Branch:** `pr_090_store-optional-payment`

---

## 1. Goal (one sentence)

On Store checkout, customer chooses **Pay at pickup / on delivery** (default) or **Pay now**; order always goes to Clover; pay-now customers get a payment page and later a **receipt link in SMS**.

---

## 2. Locked decisions

| # | Decision | Value |
|---|----------|--------|
| 1 | Scope | **Store only** — no phone / voice payment |
| 2 | Fulfillment | **Pickup and delivery** both support both payment choices |
| 3 | Default | **Pay later** (pay at pickup / when it arrives) |
| 4 | Pay now UX | Redirect (or open) **Clover Hosted Checkout** — never collect card in our app |
| 5 | Kitchen | Order is **always** submitted to Clover when checkout succeeds (pay later or pay now) |
| 6 | Confirm SMS | Same GHL confirm SMS as today (order placed) for both choices |
| 7 | Receipt SMS | **Only after online payment succeeds** — include Clover receipt link |
| 8 | Phone | Out of scope for this plan / PR |
| 9 | Build style | **One PR (090)** — phases below; **stop for approval after each phase** |

---

## 3. Customer flow

```
Browse → cart → pickup/delivery → name/phone/(address)
  → Payment choice:
       ○ Pay at pickup / on delivery   (default)
       ○ Pay now
  → Place order
       → Clover kitchen ticket
       → Confirm SMS (GHL, same as today)
  → If Pay now:
       → Open Clover payment link
       → After paid → Receipt SMS (with receipt link)
  → Thank-you page
```

Same for **pickup** and **delivery**.  
Delivery + pay later = pay when food arrives.  
Delivery + pay now = pay online before/while waiting.

---

## 4. Architecture (target)

```
  Store checkout
       │
       ▼
  POST /store/checkout  (+ payment_preference: later | now)
       │
       ├──► Clover atomic order (always)
       ├──► n8n order.placed → GHL confirm SMS (always)
       │
       └── if pay now
              ├──► Create Clover Hosted Checkout session
              ├──► Return checkout_url to browser
              └── later: payment webhook / poll
                     └──► n8n order.paid (+ receipt_url) → GHL receipt SMS
```

Browser never talks to Clover or GHL directly.

---

## 5. Phases (step by step — approval gate each time)

### P0 — Plan + branch ✅

- [x] Plan doc + PR doc + branch `pr_090_store-optional-payment`
- [x] User approved locked decisions (§2)
- **Stop for next phase.**

### P1 — Checkout UI (pay choice only) ✅

**Done:**
- Store checkout radios: **Pay at pickup / Pay on delivery** (default) vs **Pay now**
- `payment_preference: later | now` on `POST /store/checkout` (validate + place)
- Summary echoes `payment_preference`; `checkout_url` filled in P2 when enabled
- Pay-now place still creates the kitchen order
- Tests: default later, now echoed, aliases, invalid, place keeps preference

### P2 — Clover Hosted Checkout (pay now) ✅

**Done:**
- `restaurant/clover/hosted_checkout.py` — create session via `/invoicingcheckoutservice/v1/checkouts`
- After place, if preference=`now` and `STORE_PAY_NOW_ENABLED=1` → set `checkout_url` + `checkout_session_id`
- Fail-open: HCO failure never undoes a placed order
- Thank-you: auto-open checkout URL + **Pay now** button fallback
- Env in `.env.example`: `STORE_PAY_NOW_ENABLED`, `CLOVER_ECOM_PRIVATE_TOKEN`, redirect URLs
- Tests: body cents/delivery, href parse, enabled/disabled/fail-open

**VPS enable (when ready):** set Ecommerce Hosted Checkout private token + `STORE_PAY_NOW_ENABLED=1`.

### P3 — Payment success → receipt URL ✅

**Done:**
- On HCO create → record pending `checkout_session_id` → `order_id` in `data/store_pay_now.json`
- `POST /store/clover-hco-webhook` — verify `Clover-Signature`, on APPROVED store `payment_id` + `receipt_url`
- `GET /store/payment-status` — Store thank-you polls until paid, then shows **View receipt**
- Fixed API: `payment_preference` now accepted on `StoreCheckoutRequest` (was dropped by Pydantic)
- Env: `CLOVER_HCO_WEBHOOK_SECRET`, `CLOVER_RECEIPT_URL_TEMPLATE`, unsigned-dev flag

**You configure in Clover Dashboard:** Webhook URL → `https://voice.bizbull.ai/store/clover-hco-webhook` + copy signing secret.

**Approval:** waiting before P4 (receipt SMS via n8n/GHL).

### P4 — Receipt SMS via n8n / GHL ✅ (Sierra emit)

**Done (code):**
- On HCO APPROVED → `notify_order_paid` → same n8n URL as `order.placed`
- Envelope includes `receipt_url`, `payment_id`, phone, `event_id=order.paid:{payment_id}`
- Idempotent mark `n8n_paid_notified_at` so webhook retries do not re-POST
- Fail-open; confirm SMS path untouched
- Guide: `n8n/ORDER_PAID_RECEIPT_SMS.md` (you add n8n/GHL branch + SMS copy)

**Still on you:** n8n IF `event == order.paid` → send SMS with receipt link (see guide).

### P5 — Hardening + docs ✅

**Done:**
- `GET /store/config` → UI hides **Pay now** when kill switch off
- HCO expiry echoed (`checkout_expires_at_ms`); thank-you copy for ~15 min expiry + poll timeout fallback
- Webhook rate limit (`STORE_HCO_WEBHOOK_RATE_LIMIT`, default 120/60s)
- Docs: `14-web-store.md`, `vps-config.md`, `LOCAL_DEV.md`, this plan, PR 090
- Test checklist below

---

## 10. Test checklist (local + VPS)

### Unit
```
PYTHONPATH=. uv run --with pytest pytest tests/test_store_checkout.py tests/test_hosted_checkout.py tests/test_store_pay_now.py tests/test_n8n_webhook.py tests/test_store_rate_limit.py -q
```

### Local manual
1. Token server + `cd web && npm run dev`
2. **Pay later** pickup + delivery → place → confirm SMS if n8n on
3. With `STORE_PAY_NOW_ENABLED=0` → Pay now button **hidden**
4. With `STORE_PAY_NOW_ENABLED=1` + Ecommerce token → Pay now → Clover page opens
5. Complete sandbox pay → thank-you shows **View receipt** (needs webhook; local may use webhook.site + forward, or unsigned only in dev)

### VPS (when you deploy)
1. Pull branch / merge → rebuild `web/` → restart `restaurant-token`
2. Confirm Caddy `handle /store*`
3. Set env (see §6) — **never** `CLOVER_HCO_WEBHOOK_ALLOW_UNSIGNED=1`
4. Clover Dashboard webhook → `https://voice.bizbull.ai/store/clover-hco-webhook` + secret
5. n8n branch for `order.paid` (see `n8n/ORDER_PAID_RECEIPT_SMS.md`)
6. Live: pickup pay-later, delivery pay-later, pickup pay-now, delivery pay-now

### Phone
Unchanged — no pay-now on Sierra voice.

---

## 6. Kill switches / env

| Env | Effect |
|-----|--------|
| `STORE_PAY_NOW_ENABLED` | `0` (default) = no HCO link created (pay-now still places order) |
| `CLOVER_ECOM_PRIVATE_TOKEN` | Hosted Checkout private key (falls back to `CLOVER_API_TOKEN`) |
| `CLOVER_HCO_WEBHOOK_SECRET` | HMAC secret from Clover HCO webhook settings |
| `CLOVER_HCO_WEBHOOK_ALLOW_UNSIGNED` | Dev only — accept webhooks without signature |
| `CLOVER_RECEIPT_URL_TEMPLATE` | Default `https://www.clover.com/r/{payment_id}` |
| `STORE_HCO_WEBHOOK_RATE_LIMIT` | Default 120 posts / window |
| Existing `CLOVER_SUBMIT_ORDERS` | Kitchen ticket vs log-only id |
| Existing `N8N_SYNC_ENABLED` | Confirm / receipt SMS fail-open |

---

## 7. Out of scope

- Phone / Sierra voice pay now
- Collecting card numbers in Store UI
- Forcing prepay before kitchen
- Tips, refunds, partial payments (later)
- Changing voice confirm SMS

---

## 8. How we work on this PR

1. Doc first (done) → branch matches name (done).
2. **One phase at a time.** After each phase: show what changed → wait for approval → next phase.
3. No push / no GitHub PR / no VPS deploy unless you ask.
4. Never commit `.env` secrets.

---

## 9. Open items (ops — you provide when testing)

1. Clover Ecommerce Hosted Checkout **private token**  
2. Clover HCO **webhook URL** + **signing secret**  
3. n8n/GHL branch for `order.paid` receipt SMS  
4. Confirm receipt URL template works for sandbox vs prod (`CLOVER_RECEIPT_URL_TEMPLATE`)

---

## Related

| Doc | Role |
|-----|------|
| [`14-web-store.md`](14-web-store.md) | Store browse/checkout (pay later baseline) |
| [`09-clover-pos.md`](09-clover-pos.md) | Clover orders; payments were deferred |
| [`13-ghl-n8n-order-sync.md`](13-ghl-n8n-order-sync.md) | Confirm SMS today |
| [`pr/pr_090_store-optional-payment.md`](../../pr/pr_090_store-optional-payment.md) | Ship record for this PR |
