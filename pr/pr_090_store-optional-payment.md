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
| **P0** | Plan + branch + this doc | ✅ Done — waiting approval to start P1 |
| **P1** | Store checkout UI: pay choice | ☐ Not started |
| **P2** | Clover Hosted Checkout link | ☐ Not started |
| **P3** | Payment success → receipt URL | ☐ Not started |
| **P4** | Receipt SMS via n8n/GHL | ☐ Not started |
| **P5** | Hardening, tests, docs, deploy notes | ☐ Not started |

## Files Added
### `docs/plan/15-store-optional-payment.md`
Full product + architecture + phased build plan.

### `pr/pr_090_store-optional-payment.md`
This ship record (updated as phases land).

## Files Modified
### `docs/README.md`
Index link to plan 15.

## Files Deleted
None.

## What's NOT in This PR
- Phone / Sierra voice payment
- Any payment code until P0 is approved and each later phase is approved
- Forced prepay before kitchen
- Tips / refunds

## How to Test
N/A at P0 (docs only).

After P1+: see phase checklists in `docs/plan/15-store-optional-payment.md`.

## Post-Merge: VPS Pull Command
`cd /opt/livekit-sarvam && git pull origin main && uv sync`  
(+ rebuild `web/`, restart `restaurant-token`, set Hosted Checkout env when P2+ ships)
