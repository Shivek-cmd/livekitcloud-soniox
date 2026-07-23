# PR 091 — Fix Store pay-now receipt URL (order id + sandbox host)

## Branch
`pr_091_sandbox-receipt-order-id`

## What This PR Does
Clover’s public receipt page `/r/{id}` expects a **Clover order id**, not a payment id.
Sandbox also rejects production `www.clover.com` links.

After Hosted Checkout webhook APPROVED, we look up `payment → order.id` and build:
`https://sandbox.dev.clover.com/r/{order_id}` (or `www.clover.com` when not sandbox).

**Also on this branch:** Pay now is **pay-first**. Choosing Pay now opens Hosted Checkout
without placing a kitchen ticket or showing “thank you / order placed”. After payment
succeeds, the webhook places the kitchen order + confirm SMS, then receipt SMS.

**Pay return UX:** Pending pay-now is saved in `localStorage`. Clover success/failure
redirects to `?tab=store&store_pay=1|0` so the return tab opens **Store** and restores
awaiting/thank-you (not a blank Order-with-Sierra page).

## Files Modified (pay-first)
### `restaurant/store_checkout.py`
Pay-now returns `awaiting_payment`; `fulfill_store_order_after_payment` places after pay.

### `restaurant/store_pay_now_store.py`
Stores `place_summary`; claim/mark kitchen place after APPROVED.

### `token_server.py`
Webhook APPROVED → fulfill kitchen → `order.paid`.

### `web/src/components/StoreTab.tsx`
`awaiting_payment` pane until paid; thank-you only after kitchen order id.

## Files Added
### `pr/pr_091_sandbox-receipt-order-id.md`
This ship record.

## Files Modified
### `restaurant/store_pay_now_store.py`
Receipt URL helpers use `{order_id}` by default; host follows `CLOVER_BASE_URL`.

### `restaurant/clover/hco_webhook.py` / payment lookup helper
Resolve payment → order id via REST (or inline in store module).

### `token_server.py`
On APPROVED, resolve receipt order id before recording paid + n8n notify.

### `tests/test_store_pay_now.py`
Cover order-id receipt URLs + template placeholders.

### `.env.example`, `docs/vps-config.md`
Document `{order_id}` template.

## What's NOT in This PR
- n8n receipt SMS workflow changes
- Marking kitchen POS order paid

## How to Test
```
PYTHONPATH=. uv run --with pytest pytest tests/test_store_pay_now.py -q
```
Smoke: Store Pay now → open receipt link → should load (sandbox: `/r/{HCO order id}`).

## Post-Merge: VPS
```bash
cd /opt/livekit-sarvam
git pull origin main && uv sync
systemctl restart restaurant-token
# Optional: set template explicitly
# CLOVER_RECEIPT_URL_TEMPLATE=https://sandbox.dev.clover.com/r/{order_id}
```
