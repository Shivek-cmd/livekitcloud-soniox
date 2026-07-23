# PR 090 — Store optional payment (pay now or pay later)

## Branch
`pr_090_store-optional-payment`

## What This PR Does
Adds **optional Pay now** on the web **Store** tab only (not phone).  
Customer chooses **Pay at pickup / on delivery** (default) or **Pay now**.  
Order always goes to Clover + confirm SMS. Pay-now uses Clover Hosted Checkout;  
after payment, receipt URL is stored and `order.paid` is sent to n8n for receipt SMS.

Plan: [`docs/plan/15-store-optional-payment.md`](../docs/plan/15-store-optional-payment.md)

### Locked decisions
- Store only — no voice/phone payment
- Pickup **and** delivery both support pay later + pay now
- Default = pay later
- Never collect cards in our UI
- Kitchen ticket always on successful checkout
- Receipt SMS only after online payment succeeds
- Phases **P0→P5** on this branch

## Current status
| Phase | Scope | Status |
|-------|--------|--------|
| **P0** | Plan + branch + this doc | ✅ |
| **P1** | Store checkout UI: pay choice | ✅ |
| **P2** | Clover Hosted Checkout link | ✅ |
| **P3** | Payment success → receipt URL | ✅ |
| **P4** | Receipt SMS via n8n (`order.paid`) | ✅ Sierra emit; n8n branch manual |
| **P5** | Hardening + docs + checklist | ✅ |

## Files Added
- `docs/plan/15-store-optional-payment.md`
- `pr/pr_090_store-optional-payment.md`
- `restaurant/clover/hosted_checkout.py`
- `restaurant/clover/hco_webhook.py`
- `restaurant/store_pay_now_store.py`
- `tests/test_hosted_checkout.py`
- `tests/test_store_pay_now.py`
- `n8n/ORDER_PAID_RECEIPT_SMS.md`

## Files Modified
- `restaurant/store_checkout.py`, `restaurant/integrations/n8n_webhook.py`, `restaurant/store_rate_limit.py`
- `token_server.py` — preference, config, webhook, payment-status
- `web/src/components/StoreTab.tsx`, `web/src/lib/api.ts`, `web/src/App.css`
- `web/src/App.tsx` — remember last tab (`order` / `store`) in `sessionStorage`
- `tests/test_store_checkout.py`, `tests/test_n8n_webhook.py`
- `.env.example`, `.gitignore`
- `docs/plan/14-web-store.md`, `docs/vps-config.md`, `docs/LOCAL_DEV.md`, `docs/README.md`
- `n8n/README.md`

## What's NOT in This PR
- Phone / Sierra voice payment
- Pre-built n8n workflow JSON for `order.paid` (manual — see guide)
- Forced prepay before kitchen
- Tips / refunds

## How to Test
See plan §10 checklist. Quick unit:
```
PYTHONPATH=. uv run --with pytest pytest tests/test_store_checkout.py tests/test_hosted_checkout.py tests/test_store_pay_now.py tests/test_n8n_webhook.py tests/test_store_rate_limit.py -q
```

## Post-Merge: VPS
```bash
cd /opt/livekit-sarvam
git pull origin main && uv sync
(cd web && npm install && npm run build)
systemctl restart restaurant-token
# set STORE_PAY_NOW_ENABLED + CLOVER_ECOM_PRIVATE_TOKEN + CLOVER_HCO_WEBHOOK_SECRET
# Clover webhook → https://voice.bizbull.ai/store/clover-hco-webhook
# n8n: branch on order.paid (n8n/ORDER_PAID_RECEIPT_SMS.md)
```
