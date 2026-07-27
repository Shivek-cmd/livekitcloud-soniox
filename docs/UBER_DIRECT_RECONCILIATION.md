# Uber Direct Delivery Reconciliation

Use this checklist when a delivery is stuck in a non-terminal state, courier
creation has an uncertain outcome, or Sierra, Uber, n8n, and GHL disagree.

## Safety Rules

- Do not call Create Delivery again when the original outcome is uncertain.
- Do not move a GHL opportunity by customer name or phone alone. Match the
  stored Clover order ID.
- Do not promise a customer that another courier is coming until Uber confirms
  the delivery state or staff creates a replacement manually.
- Keep `STORE_UBER_DIRECT_ENABLED=0` during investigation if multiple orders
  could be affected.

## Identify the Order

- Record the Clover order ID, Store session/checkout key, Uber delivery ID,
  latest Uber event ID, customer phone, and tracking URL.
- Check the persisted order and delivery records. Note the dispatch state,
  status, attempt count, last event time, and n8n notification fields.
- Treat `dispatch_required`, a stale `creating` claim, or Create Delivery
  timeout without a delivery ID as manual-review conditions.

## Reconcile Each System

- Uber dashboard/API: confirm whether a delivery exists and record its current
  status, tracking URL, courier outcome, and any cancellation or undeliverable
  reason.
- Application logs/store: confirm whether Create Delivery was attempted and
  whether the outcome was successful, explicit failure, or uncertain.
- n8n: find the stable event ID, inspect the execution result, and confirm the
  Data Table claim is `completed`, `failed`, or absent.
- GHL: confirm the contact delivery-status field, the matching Clover-order
  opportunity stage, and the expected SMS/staff-alert evidence.
- Clover/Store: confirm the kitchen order and payment state independently from
  courier state.

## Resolve

- Uber delivery exists: store the confirmed delivery ID/status/tracking URL and
  allow only the pending lifecycle notification to retry.
- Uber confirms no delivery exists after an uncertain Create Delivery: staff
  may create one replacement courier and record the new delivery ID.
- Terminal `delivered`: move only the Clover-ID-matched opportunity to
  Completed and verify the confirmation message once.
- Terminal `canceled`, `failed`, or `returned`: alert staff; do not
  automatically mark the opportunity Lost or send a customer promise.
- n8n side effect failed: retry the same stable event ID. Do not create a new
  event ID to bypass idempotency.

## Close the Incident

- Record who reconciled it, UTC timestamps, the final Uber status, whether a
  replacement courier was created, and the final n8n/GHL result.
- Confirm no duplicate courier, customer SMS, staff SMS, or opportunity move
  occurred.
- Rotate any secret exposed during troubleshooting and remove temporary test
  configuration before production review.
