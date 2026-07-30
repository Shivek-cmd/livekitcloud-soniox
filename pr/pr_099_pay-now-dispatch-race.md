# PR 099 - Wait for Pay-now Courier Confirmation

## Branch

`pr_099_pay-now-dispatch-race`

## Problem

After Clover redirected a successful Pay-now delivery into a new tab, the Store
could receive the kitchen order ID just before Uber Direct finished dispatching.
The tab immediately showed the final success screen and stopped polling, so the
tracking button appeared only after a manual refresh. The original Store tab
could still show tracking because its polling completed slightly later.

## Fix

- For a delivery backed by an Uber quote, keep polling until dispatch reaches
  either `dispatched` or `dispatch_required`.
- Show an accurate paid-and-arranging-courier state during that short interval.
- Hide the stale checkout and cancel controls after the kitchen order exists.
- Restore an in-progress redirected tab into polling instead of prematurely
  treating it as final.
- Leave pickup and non-Uber Pay-now behavior unchanged.

## Safety

- No changes to Clover payment approval, kitchen submission, Uber dispatch,
  n8n, GHL, SMS, or backend persistence.
- The existing polling limit remains in place.
- Production deployment requires separate approval.

## Verification

- `npm run build` in `web`
  - TypeScript and Vite production build passed
  - Existing large-chunk advisory remains
- `python -m pytest tests/test_store_pay_now.py tests/test_store_checkout.py`
  - 40 passed
- `git diff --check`
