# Store Optional Payment — Plan (pay now or pay later)

> **Status:** ☐ Plan only — **no code until each step is approved**  
> **Last updated:** 2026-07-23  
> **Channel:** Web **Store** tab only (`voice.bizbull.ai`) — **not phone / Sierra voice**  
> **Depends on:** PR 089 Store (merged) — [`14-web-store.md`](14-web-store.md)  
> **CRM:** [`13-ghl-n8n-order-sync.md`](13-ghl-n8n-order-sync.md)  
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

### P0 — Plan + branch ✅ (this doc)

- [x] Plan doc + PR doc + branch `pr_090_store-optional-payment`
- [ ] User approves locked decisions (§2)
- **Stop.** No code yet.

### P1 — Checkout UI (pay choice only)

**Do:** Add Pay later / Pay now radios on Store checkout (pickup + delivery).  
Wire preference into `POST /store/checkout` body.  
If `later` → current behavior only (no payment API yet).

**Done when:** UI choice works; pay-later place still succeeds; pay-now can be accepted but may no-op or show “coming soon” until P2.

**Approval:** UI copy + default = pay later.

### P2 — Clover Hosted Checkout (pay now)

**Do:** After successful place, if `payment_preference=now`, create Hosted Checkout session; return `checkout_url`; Store thank-you redirects/opens it.

**Needs:** Clover Ecommerce / Hosted Checkout token on merchant (sandbox first). Env vars documented in `.env.example`.

**Done when:** Sandbox pay-now opens Clover pay page for a real Store order.

**Approval:** Sandbox credentials + kill switch name before coding.

### P3 — Payment success → receipt URL

**Do:** Detect successful payment (webhook preferred; poll fallback). Store `payment_id` + `receipt_url` against `clover_order_id`.

**Done when:** We can log/store receipt URL after a sandbox payment.

**Approval:** Webhook URL / auth approach before coding.

### P4 — Receipt SMS via n8n / GHL

**Do:** New fail-open event (e.g. `order.paid`) with `receipt_url` → n8n → GHL SMS including the link. Confirm SMS at place stays unchanged.

**Done when:** Pay-now sandbox order gets confirm SMS at place + receipt SMS after pay.

**Approval:** SMS copy template before changing GHL workflow.

### P5 — Hardening + docs

**Do:** Kill switches, rate limits, expired link handling, tests, update `14-web-store.md` / VPS notes. Local + VPS test checklist.

**Done when:** Pickup + delivery × pay later + pay now all verified; phone untouched.

**Approval:** Deploy to VPS only when asked.

---

## 6. Kill switches (planned)

| Env | Effect |
|-----|--------|
| `STORE_PAY_NOW_ENABLED` | `0` = hide/disable Pay now (pay later only) |
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

## 9. Open items (resolve in P0 approval)

1. Confirm §2 locked decisions.  
2. Sandbox Hosted Checkout: do we already have Ecommerce token for Bizbull sandbox? (If not, create before P2.)  
3. Receipt SMS: new GHL workflow vs extend existing confirm workflow?

---

## Related

| Doc | Role |
|-----|------|
| [`14-web-store.md`](14-web-store.md) | Store browse/checkout (pay later baseline) |
| [`09-clover-pos.md`](09-clover-pos.md) | Clover orders; payments were deferred |
| [`13-ghl-n8n-order-sync.md`](13-ghl-n8n-order-sync.md) | Confirm SMS today |
| [`pr/pr_090_store-optional-payment.md`](../../pr/pr_090_store-optional-payment.md) | Ship record for this PR |
