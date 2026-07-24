# PR 093 — Store Uber Direct (courier for delivery)

## Branch
`pr_093_store-uber-direct`

## What This PR Does
Adds **Uber Direct** courier fulfillment for **Store delivery** orders only
(test/sandbox first). Customer still checks out on Bizbull Store; Uber only
dispatches a courier. Pickup, phone/Sierra voice, and pay-now (PR 090) are
unchanged.

Plan: [`docs/plan/16-store-uber-direct.md`](../docs/plan/16-store-uber-direct.md)

### Locked decisions (see plan §2)
- Store only; sandbox first; Sierra = integration partner (restaurant owns Uber bill)
- This PR: **Bizbull** via `.env`; config tenant-shaped for later
- Fee v1: **A pass-through**; fallback = tenant `delivery_charge`
- Prep **25 min**; tracking SMS **in this PR**
- Pickup: Sherwood Park address in `.env`
- One PR — **P0→P5**; approval after each phase

## Current status
| Phase | Scope | Status |
|-------|--------|--------|
| **P0** | Plan + branch + this doc | ✅ |
| **P1** | Uber client + `POST /store/delivery-quote` | ✅ |
| **P2** | Structured delivery address UI | ✅ |
| **P3** | Quote → checkout pricing | ✅ |
| **P4** | Create delivery after kitchen place + tracking UI | ✅ |
| **P5** | Webhooks + tracking SMS + hardening + docs | ✅ |

## Files Added
- `docs/plan/16-store-uber-direct.md`
- `pr/pr_093_store-uber-direct.md`
- `restaurant/uber_direct/` — config, address, client, service, quote_store, delivery_store, webhook
- `tests/test_uber_direct.py`
- `web/src/lib/storeDeliveryAddress.ts`
- `n8n/DELIVERY_DISPATCHED_TRACKING_SMS.md`

## Files Modified
- `docs/README.md` — index link to plan 16
- `token_server.py` — quote, webhook, delivery-status, config flags, `uber_quote_id`
- `restaurant/store_checkout.py` — quote fee + Uber dispatch + n8n tracking event
- `restaurant/integrations/n8n_webhook.py` — `delivery.dispatched`
- `.env.example` / `.gitignore`
- `web/src/components/StoreTab.tsx`, `web/src/App.css`, `web/src/lib/api.ts`
- `tests/test_store_checkout.py`

## What's NOT in This PR
- Phone / Sierra voice dispatch
- Uber Eats marketplace
- Production go-live
- Implementation code (starts only after you approve P1)

## How to Test
N/A until P1+. See plan §11.

## Post-Merge: VPS Pull Command
`cd /opt/livekit-sarvam && git pull origin main && uv sync`
(only after merge + you enable env — default kill switch off)
