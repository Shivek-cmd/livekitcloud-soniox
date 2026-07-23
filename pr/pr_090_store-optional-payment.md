# PR 090 — Store optional payment (pay now or pay later)

## Branch
`pr_090_store-optional-payment`

## What This PR Does
Adds **optional Pay now** on the web **Store** tab only (not phone).  
Customer chooses **Pay at pickup / on delivery** (default) or **Pay now**.  
Order always goes to Clover + confirm SMS. Pay-now uses Clover Hosted Checkout;  
after payment, receipt link is sent via n8n/GHL SMS.

Plan: [`docs/plan/15-store-optional-payment.md`](../docs/plan/15-store-optional-payment.md)

### Locked decisions
- Store only — no voice/phone payment
- Pickup **and** delivery both support pay later + pay now
- Default = pay later
- Never collect cards in our UI
- Kitchen ticket always on successful checkout
- Receipt SMS only after online payment succeeds
- Build in phases **P0→P5**; **approval required between phases**

## Current status
| Phase | Scope | Status |
|-------|--------|--------|
| **P0** | Plan + branch + this doc | ✅ Done |
| **P1** | Store checkout UI: pay choice | ✅ Done |
| **P2** | Clover Hosted Checkout link | ✅ Done — waiting approval before P3 |
| **P3** | Payment success → receipt URL | ☐ Not started |
| **P4** | Receipt SMS via n8n/GHL | ☐ Not started |
| **P5** | Hardening, tests, docs, deploy notes | ☐ Not started |

## Files Added
### `docs/plan/15-store-optional-payment.md`
Full product + architecture + phased build plan.

### `pr/pr_090_store-optional-payment.md`
This ship record (updated as phases land).

### `restaurant/clover/hosted_checkout.py` (P2)
Create Clover Hosted Checkout session; kill switch `STORE_PAY_NOW_ENABLED`.

### `tests/test_hosted_checkout.py` (P2)
HCO body + create + store pay-now wiring tests.

## Files Modified
### `docs/README.md`
Index link to plan 15.

### `restaurant/store_checkout.py` (P1–P2)
`payment_preference`; after place, create HCO when pay-now enabled.

### `web/src/lib/api.ts` (P1–P2)
Request/summary types for preference + `checkout_url` / `checkout_session_id`.

### `web/src/components/StoreTab.tsx` (P1–P2)
Pay radios; thank-you opens HCO URL + Pay now button.

### `web/src/App.css` (P2)
Pay-now link button styling.

### `tests/test_store_checkout.py` (P1)
Preference default, now, alias, invalid, place keep.

### `.env.example` (P2)
`STORE_PAY_NOW_ENABLED`, `CLOVER_ECOM_PRIVATE_TOKEN`, redirect URLs.

## Files Deleted
None.

## What's NOT in This PR
- Phone / Sierra voice payment
- Payment webhook / receipt SMS (P3–P4)
- Forced prepay before kitchen
- Tips / refunds

## How to Test
**P1–P2**
```
PYTHONPATH=. uv run --with pytest pytest tests/test_store_checkout.py tests/test_hosted_checkout.py -q
```
Local pay-now (sandbox):
1. Set `STORE_PAY_NOW_ENABLED=1` and `CLOVER_ECOM_PRIVATE_TOKEN` (Hosted Checkout private key) in `.env`
2. Token server + `cd web && npm run dev`
3. Store → Pay now → Place → Clover checkout should open (or use the thank-you button)

Pay later: unchanged. If kill switch off, pay-now still places order with no link.

## Post-Merge: VPS Pull Command
`cd /opt/livekit-sarvam && git pull origin main && uv sync`  
(+ rebuild `web/`, restart `restaurant-token`, set `STORE_PAY_NOW_ENABLED=1` + Ecommerce token)
