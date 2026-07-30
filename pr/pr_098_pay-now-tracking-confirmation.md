# PR 098 — Pay-now Tracking Confirmation

## Branch

`pr_098_pay-now-tracking-confirmation`

## Problem

After a successful Pay-now delivery, the backend persisted the Uber delivery ID,
dispatch state, and tracking URL. The payment-status API returned only payment,
kitchen, and ETA fields, so the Store success screen could not show “courier
arranged” or the tracking link.

## Fix

- Return the safe Uber dispatch outcome fields from `/store/payment-status`.
- Merge those fields into the pending Pay-now checkout summary when payment
  completes.
- Refresh the same fields when restoring an already-placed Pay-now order.
- Keep internal payment and dispatch records private.
- Add a regression test for the public payment-status view.

## Safety

- No changes to payment approval, kitchen submission, courier creation,
  idempotency, n8n, GHL, or SMS behavior.
- Pay-later confirmation behavior is unchanged.
- Production deployment requires separate approval.

## Verification

- `python -m pytest tests/test_store_pay_now.py tests/test_store_checkout.py`
  - 40 passed
- `npm run build` in `web`
  - TypeScript and Vite production build passed
  - Existing large-chunk advisory remains
- `git diff --check`
