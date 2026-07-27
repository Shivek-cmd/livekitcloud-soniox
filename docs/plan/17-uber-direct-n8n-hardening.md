# Uber Direct + n8n Production Hardening — Plan

> **Status:** P6 local and quote checks complete — real sandbox delivery blocked by billing/configuration
> **Channel:** Web Store delivery only; pickup and Sierra phone ordering remain unchanged
> **Environment:** Uber Direct sandbox until explicit production approval
> **Depends on:** [`16-store-uber-direct.md`](16-store-uber-direct.md) · [`13-ghl-n8n-order-sync.md`](13-ghl-n8n-order-sync.md)
> **PR:** [`pr/pr_097_uber-direct-n8n-hardening.md`](../../pr/pr_097_uber-direct-n8n-hardening.md)
> **Branch:** `pr_097_uber-direct-n8n-hardening`

---

## 1. Goal

Make Store delivery safe to pilot end to end: the Uber quote, charged fee, kitchen
order, courier destination, customer messages, GHL state, and Uber lifecycle must
all refer to the same order and remain correct across retries and failures.

This is a hardening PR, not a new delivery product. The existing PR 093 quote and
dispatch path stays the foundation.

---

## 2. Current baseline

Already implemented:

- Uber Direct quote creation and short-lived quote storage.
- Structured delivery-address entry in the Store UI.
- Pass-through Uber fee and flat fallback support.
- Courier creation after a successful Clover kitchen order.
- Pay-now fulfillment after Clover Hosted Checkout approval.
- Store success UI with the Uber tracking link.
- Uber delivery webhook endpoint and local status storage.
- Sierra n8n envelopes for `order.placed`, `order.paid`, and
  `delivery.dispatched`.
- Production n8n/GHL `order.placed` path: contact, tags, Placed opportunity, and
  confirmation SMS.

Known gaps:

- Checkout trusts a quote ID without proving that the checkout address is the
  address that was quoted. Uber dispatch reads the quote's address while Clover
  and n8n read the checkout address.
- The repository n8n workflow has no explicit `order.paid` or
  `delivery.dispatched` branch.
- Uber webhook signatures are not verified.
- Uber webhook retries and out-of-order events are not deduplicated or ordered.
- Uber delivery status is stored but not relayed to n8n/GHL.
- A post-kitchen Uber dispatch failure is logged but creates no durable
  `dispatch_required` state or restaurant alert.
- JSON state stores are suitable for a sandbox pilot, but not the long-term
  multi-worker/multi-tenant design.

---

## 3. Locked principles

1. **Correct address first.** A quote may be used only for the normalized
   structured address that produced it.
2. **No silent delivery gap.** If Uber cannot be quoted before placement while
   Direct is enabled, delivery checkout is blocked and pickup remains available.
3. **Kitchen success is not courier success.** If courier creation fails after
   the kitchen order exists, keep the food order, mark it `dispatch_required`,
   alert restaurant staff, and avoid telling the customer that a courier was
   successfully assigned.
4. **Explicit event routing.** n8n routes each event type to one isolated path;
   receipt/tracking/status events must never recreate a Placed opportunity or
   re-fire the original confirmation workflow.
5. **At-least-once safe.** Stable event IDs and durable claims make retries safe
   across Store, Uber, n8n, and GHL.
6. **Trust signed callbacks only.** Uber webhook processing verifies the raw
   request signature before mutating delivery state.
7. **Low-noise customer messaging.** Send meaningful milestones, not an SMS for
   every courier status.
8. **Fail visibly, not silently.** Customer-safe errors, staff alerts, logs, and
   reconciliation state are part of the product behavior.
9. **Sandbox first.** This PR does not enable Uber Direct production mode.
10. **Approval after every phase.** No phase starts until the previous phase is
    reviewed and explicitly approved.

---

## 4. Target event contract

One n8n webhook may receive all Sierra events, but it must route by `event`:

| Event | Purpose | Must not do |
|------|---------|-------------|
| `order.placed` | Existing contact + Placed opportunity + order confirmation | Duplicate an existing order/SMS |
| `order.paid` | Send the Hosted Checkout receipt link | Create another Placed opportunity |
| `delivery.dispatched` | Send the Uber tracking link | Re-fire order confirmation |
| `delivery.status_changed` | Update delivery/GHL state; selected customer messages | Treat every webhook as customer-notifiable |
| `delivery.dispatch_required` | Urgent restaurant follow-up after post-kitchen dispatch failure | Claim that a courier is assigned |
| Unknown | Log and acknowledge safely | Enter an order-processing branch |

Stable event ID forms:

```text
order.placed:{clover_order_id}
order.paid:{payment_id}
delivery.dispatched:{uber_delivery_id}
delivery.status:{uber_event_id}
delivery.dispatch_required:{clover_order_id}
```

---

## 5. Delivery-state model

The Store order and the courier delivery are related but separate:

```text
Store: validated → awaiting_payment → kitchen_placed
                                      ├─ courier_dispatched
                                      └─ dispatch_required

Uber: pending → pickup → pickup_complete → dropoff → delivered
             └─ canceled / failed / returned
```

Recommended customer SMS milestones:

- `delivery.dispatched`: tracking link.
- `pickup_complete` or first `dropoff`: order is on the way.
- `delivered`: delivery confirmation.
- `failed`, `canceled`, or `returned`: staff alert first; customer copy must not
  promise an outcome the restaurant has not confirmed.

GHL “Completed” must not be overloaded:

- Delivery order: Uber `delivered` can close/move the delivery opportunity.
- Pickup order: completion still requires Clover/staff status and remains
  separate from Uber.

---

## 6. Phases

### P0 — Plan, PR document, and branch

- [x] Agree on the production-hardening direction.
- [x] Create this plan.
- [x] Create PR 097 ship record.
- [x] Create branch `pr_097_uber-direct-n8n-hardening`.
- [x] Review and approve P1.

**Stop after branch creation. No application or workflow code in P0.**

### P1 — Quote/address contract

Goal: the priced address, checkout address, Clover address, n8n address, and Uber
dropoff cannot diverge.

- [x] Add the structured delivery address to checkout requests and validated
  summaries.
- [x] Normalize the address server-side.
- [x] Bind each quote to a canonical address fingerprint.
- [x] Reject missing, expired, unverifiable, or address-mismatched quotes when
  Direct is enabled.
- [x] Revalidate again at final Place, including the review-screen delay.
- [x] Never dispatch using an address that differs from the checked-out address.
- [x] Add unit tests for edits after quote, stale/legacy quote, unit/postal
  normalization, and pay-now return.

Implementation notes:

- Fingerprints use normalized street, unit, city, province/state, postal code,
  country, and optional coordinates. Customer name/phone and delivery notes are
  intentionally excluded because they do not change the priced route.
- The server composes the one-line Clover/n8n address from the validated
  structured object; it does not trust the browser's display string.
- When Direct is disabled, the legacy one-line address remains accepted for
  transitional compatibility. When Direct is enabled, a structured destination
  plus a fresh matching quote are mandatory.
- Final Place calls the same validation/repricing path as review, so a quote that
  expires or an address that changes during review is refused.
- Pay-now persists the bound structured destination in its pending fulfillment
  snapshot.

**Approval gate:** review contract and tests before P2.

### P2 — Dispatch idempotency and failure state

Goal: one kitchen order creates at most one Uber delivery, and failures require
visible action.

- [x] Add a client checkout/idempotency key.
- [x] Persist order-to-delivery dispatch claims before/reconciled around Create
  Delivery.
- [x] Reuse a known Uber delivery result before retrying. If Create Delivery
  returns no delivery ID, do not retry automatically; persist the uncertain
  outcome for manual reconciliation because Uber's documented Get Delivery API
  requires the delivery ID.
- [x] Persist the initial created delivery immediately, not only later webhooks.
- [x] Add `dispatch_required` state with reason, attempts, and timestamps.
- [x] Emit `delivery.dispatch_required` to n8n for restaurant escalation.
- [x] Adjust customer confirmation wording so kitchen acceptance is not presented as
  courier assignment.
- [x] Cover pay-later and pay-now paths.

Implementation notes:

- The Store client generates one checkout key per cart/order attempt. The server
  persists the request fingerprint and completed response, so a repeated Place
  request replays the original result and a changed request with the same key is
  rejected.
- Courier dispatch is claimed by stable kitchen order ID before Create Delivery.
  A completed claim is replayed without another Uber POST. A concurrent claim
  reports `dispatch_in_progress`.
- A stale in-progress claim is moved to `dispatch_required` with
  `dispatch_outcome_unknown`; it is never retried automatically.
- Uber timeouts, rate limits, server errors, and unexpected transport failures
  without a returned delivery ID are treated as uncertain outcomes. This is a
  deliberate safety boundary: the documented Uber lookup requires the delivery
  ID, so retrying by external order ID could create a duplicate courier.
- Successful Create Delivery responses are persisted immediately with the
  tracking URL. Explicit rejections and uncertain outcomes persist the reason,
  attempt count, timestamps, and whether the outcome is uncertain.
- Both pay-later and pay-now fulfillment emit the courier outcome before the
  final `order.placed` notification. The envelope carries the delivery
  fulfillment state, and post-kitchen failures emit the stable
  `delivery.dispatch_required:{clover_order_id}` event.
- The repository now emits the staff-alert event, but the live n8n routing and
  alert destination are intentionally deferred to P4.
- Callers that do not yet send a checkout key retain legacy behavior for
  transitional compatibility; the Store web client always sends one.

**Approval gate:** review retry/failure behavior before P3.

### P3 — Uber webhook security and lifecycle correctness

Goal: accept authentic callbacks once and apply them in the correct order.

- [x] Configure `UBER_DIRECT_WEBHOOK_SECRET`.
- [x] Verify `x-uber-signature` / `x-postmates-signature` with HMAC-SHA256 over raw
  request bytes.
- [x] Store and deduplicate Uber `event_id`.
- [x] Record event time and reject/ignore stale state regressions.
- [x] Parse both supported Uber webhook shapes deliberately.
- [x] Use Get Delivery/resource lookup for reconciliation where appropriate.
- [x] Persist status, tracking URL, cancellation/return reason, and external order ID.
- [x] Add tests for valid/invalid signatures, duplicate events, out-of-order events,
  canceled/returned deliveries, and malformed payloads.

Implementation notes:

- The endpoint fails closed when `UBER_DIRECT_WEBHOOK_SECRET` is absent and
  rejects a missing or invalid signature before JSON parsing or state mutation.
  Signatures are compared in constant time against the exact raw request bytes,
  preserving escaped Unicode and other byte-level JSON differences.
- Both documented signature headers are accepted:
  `x-uber-signature` and `x-postmates-signature`.
- Parsing is limited to the modern `event.delivery_status` shape and the legacy
  `dapi.status_changed` shape. Unknown event kinds, missing IDs/times, and
  unknown statuses are acknowledged as client errors without mutating delivery
  state.
- Every authenticated event ID is stored durably. Retries return a successful
  duplicate result without applying the event again.
- Event timestamps and a lifecycle rank prevent older events, backward status
  movement, and transitions out of terminal states. The documented
  `canceled → returned` transition remains allowed.
- Modern webhook data is used directly. Legacy `resource_href` reconciliation is
  best effort and is restricted to HTTPS on `api.uber.com` under the documented
  `/v1/eats/deliveries/orders/` path, preventing an arbitrary server-side URL
  fetch.
- The modern Get Delivery helper addresses only a known Uber delivery ID at
  `/v1/customers/{customer_id}/deliveries/{delivery_id}`.
- Accepted events update both the delivery record and its stable external
  kitchen-order mapping with status, tracking URL, event ID/time,
  cancellation/undeliverable fields, related deliveries, and raw evidence.
- P3 persists lifecycle changes locally only. Emitting
  `delivery.status_changed` to n8n/GHL remains P5, after the P4 router is safe.

**Approval gate:** security and state transition review before P4.

### P4 — n8n router, auth, and idempotency

Goal: production n8n processes each event exactly for its intended side effects.

- [x] Confirm the repository `sierra-ghl-sync` workflow is the user-designated
  active source before editing; treat it as the
  operational source until reconciled with the repository JSON.
- [x] Add an explicit event router.
- [x] Validate Sierra's `X-Webhook-Secret` before GHL actions.
- [x] Implement durable `event_id` deduplication.
- [x] Add isolated `order.paid` receipt-SMS path.
- [x] Add isolated `delivery.dispatched` tracking-SMS path.
- [x] Add isolated `delivery.dispatch_required` restaurant-alert path.
- [x] Preserve the existing `order.placed` behavior.
- [x] Add an unknown-event and dead-letter/error path.
- [x] Export the updated workflow back into the repository without credentials.
- [x] Import/configure the workflow in n8n and inspect sandbox executions.

Implementation notes:

- `01 · Receive Order Webhook` now requires an n8n Header Auth credential named
  `X-Webhook-Secret`. Its private value must match Sierra
  `N8N_WEBHOOK_SECRET`; no secret is stored in workflow JSON.
- Every valid envelope is looked up and claimed in a private
  `sierra_event_claims` Data Table before routing. Completed, processing, and
  dead-letter claims are acknowledged as duplicates without repeating GHL side
  effects. Failed claims may be retried.
- The table stores only event control data (`event_id`, event, state,
  timestamps, and last error), not customer payloads.
- Event routing is graph-isolated:
  - `order.placed` alone enters the existing contact/tag/Placed-opportunity
    path.
  - `order.paid` upserts the customer and sends the receipt SMS only.
  - `delivery.dispatched` upserts the customer and sends tracking SMS only.
  - `delivery.dispatch_required` upserts the private staff-alert contact and
    sends an urgent operations SMS only.
- The portable repository workflow reads the staff number from the private n8n
  variable `BIZBULL_STAFF_ALERT_PHONE`. The self-hosted Community instance used
  for P4 locks custom variables, so its private imported draft uses a local
  E.164 literal in `P4 · Normalize Envelope`. That value must never be exported
  or committed.
- Unknown events and invalid receipt/tracking payloads become durable
  `dead_letter` rows, return HTTP 202, and cannot reach any GHL node.
- Malformed envelopes return 400 before a claim. GHL side-effect failures are
  stored as `failed` and return 502 so they remain visibly retryable.
- Setup, credential scopes, table schema, sandbox checks, cutover, and rollback
  are documented in `n8n/P4_ROUTER_SETUP.md`.
- Repository contract tests validate node/edge integrity, authentication
  placement, claim-before-route ordering, branch isolation, dead-letter
  isolation, GHL SMS endpoints, private staff configuration, and fixtures.

Operational evidence collected on the inactive imported draft:

- Workflow `Bizbull · Sierra Events → GHL Router-updated` remained inactive;
  the existing production workflow remained active and unchanged.
- Actual HTTP Header Auth rejected an incorrect secret with `403` before
  execution and accepted the configured secret. Manual MCP runs bypass trigger
  authentication, so execution `2174` is recorded only as test-harness
  evidence, not as an authentication result.
- Executions `2167`–`2170` verified malformed-envelope isolation,
  dead-lettering, duplicate suppression, and the no-phone completion path
  without GHL side effects.
- Executions `2171`–`2173` verified the staff dispatch alert, payment receipt,
  and courier tracking branches end to end, including receipt of each SMS.
- Execution `2176` verified the preserved `order.placed` contact fields, tag
  cycle, Placed opportunity, durable completion, and existing confirmation SMS.
- Test claims and GHL artifacts were intentionally retained as audit evidence.
- The temporary webhook secret used during setup must be rotated in both n8n
  and Sierra before activation because it was used in visible test evidence.

**Approval gate:** inspect the workflow diff and sandbox executions before P5.

### P5 — Delivery status → n8n/GHL

Goal: selected Uber lifecycle milestones update operations without SMS spam.

- [x] P5a: persist the customer/order notification context with a successful
  Uber dispatch.
- [x] P5a: emit a stable `delivery.status:{uber_event_id}` envelope only after
  an authenticated, accepted status transition.
- [x] P5a: persist n8n notification attempts and retry a pending notification
  on an Uber webhook retry without reapplying delivery state.
- [x] P5a: suppress a second “on the way” milestone when `pickup_complete` is
  followed by `dropoff`; use `dropoff` as the fallback if pickup completion was
  not observed.
- [x] P5b: add the isolated `delivery.status_changed` n8n/GHL branch to
  the repository workflow.
- [x] Match the delivered order opportunity by its stored Clover order ID.
- [x] Update the existing GHL contact order-status field for every accepted
  lifecycle status; do not add noisy status tags.
- [x] Move only a matched delivered opportunity to the Completed stage.
- [x] Send only the approved `on_the_way` and `delivered` customer messages.
- [x] Alert staff on failed/canceled/returned deliveries without sending an
  automatic customer promise or moving the opportunity to Lost.
- [x] Keep pickup completion separate from delivery completion.
- [x] P5c: configure the P5 branch in the existing inactive n8n draft and run
  controlled node-level tests.
- [x] P5d: record evidence and complete the P5 review.

P5a implementation notes:

- New deliveries store a minimal `notification_context` containing customer
  identity, Clover order ID, Store session, order type, and total. This avoids
  depending on a later cross-file lookup when Uber callbacks arrive.
- Accepted lifecycle records store the previous status and one selected
  milestone: `on_the_way`, `delivered`, `staff_alert`, or none.
- The Uber event is durably applied before n8n is called. If an enabled n8n
  relay fails, the endpoint returns HTTP 502 after recording the failed attempt;
  Uber can retry the same event, and the duplicate path retries only the pending
  n8n notification.
- Once n8n acknowledges the event, `n8n_notified_at` prevents another relay.
  The P4 Data Table provides the second idempotency boundary if a downstream
  response is lost.
- P5a is repository-only. It must not be deployed before the P5b n8n route is
  configured, or the currently active router would dead-letter status events.
- Verification: 48 focused relay tests and 42 checkout/payment regression tests
  passed. The full suite finished with 605 passed and the same two pre-existing
  hosted-checkout expectation failures documented before P5a.

P5b implementation notes:

- The new route is inserted after the existing P4 event routes and before the
  unsupported-event dead letter. P4 order/payment/dispatch behavior is
  unchanged.
- Accepted lifecycle events first upsert `delivery.<uber_status>` into the
  existing GHL order-status contact field.
- `pickup_complete` and the approved direct-`dropoff` fallback send the single
  tracking SMS. `delivered` searches the configured pipeline, matches the
  Clover order custom field, moves only that opportunity to Completed, then
  sends the delivery confirmation.
- Missing delivered opportunities are retryable side-effect failures; the
  workflow never guesses which opportunity to move.
- Failure states upsert the private staff contact and send an urgent staff SMS.
  They do not send customer SMS or move an opportunity to Lost.
- Six repository fixtures cover CRM-only, on-the-way, direct-dropoff fallback,
  delivered, staff-alert, and invalid/dead-letter behavior.
- Repository graph/JavaScript validation passed with 75 unique nodes, 19 P5
  nodes, valid edges, and the workflow still inactive. The P4/P5/backend focused
  suite passed: 49 tests.
- P5b did not edit the hosted n8n draft, activate a workflow, deploy the backend,
  or change credentials.

P5c/P5d operational evidence:

- The P5 branch was configured and tested only in the existing inactive draft.
  The production workflow remained active and unchanged.
- Execution `2178` dead-lettered an invalid lifecycle status without a GHL or
  SMS side effect; `2179` stopped its replay at the duplicate guard.
- Execution `2180` completed the CRM-only pickup route without sending SMS.
- Execution `2182` completed the on-the-way route after SMS DND was disabled;
  the customer confirmed receipt of the approved tracking message.
- Execution `2183` completed the canceled-delivery staff route; the configured
  staff recipient confirmed receipt, and no customer SMS was sent.
- Execution `2184` created a dedicated test opportunity in the Placed stage for
  the delivered-route test.
- Execution `2185` safely failed before moving an opportunity because GHL search
  returned the Clover custom field as `fieldValueString`. The resolver was
  updated to support that response shape.
- Execution `2186` matched only the dedicated Clover-order opportunity, moved
  it to Completed, sent the approved delivery-confirmation SMS, and completed
  the event. The customer confirmed receipt.
- An earlier claim attempt (`2177`) exposed that an empty Data Table
  `completed_at` mapping is serialized as `{}` by the hosted node. The unused
  mapping was removed before the successful tests.
- Repository regression checks now cover both hosted compatibility fixes.
  The final P4/P5 structural suite passed: 16 tests. `git diff --check` passed.
- Test contacts, claims, messages, and the dedicated opportunity are retained
  as controlled audit evidence.

**Approval gate:** review P5 evidence before starting P6. The draft remains
inactive; activation, deployment, commit, and push require separate approval.

### P6 — Sandbox end-to-end and reconciliation

Goal: prove the complete system under success, retry, and failure.

- [x] Confirm Uber sandbox OAuth credentials and pickup address/phone.
- [ ] Complete Uber organization billing/tax setup, add pickup coordinates, and
  configure the Uber webhook signing key.
- [x] Obtain a real Uber sandbox quote to a nearby public business address.
- [x] Test pickup unchanged locally, including the Uber `not_delivery` guard.
- [x] Test delivery pay-later and pay-now behavior with controlled local
  integration doubles.
- [ ] Run real sandbox delivery pay-later and pay-now after billing/configuration
  is complete.
- [x] Test address edit after quote and quote expiry.
- [x] Test Uber quote outage and Create Delivery explicit/uncertain failures.
- [x] Test duplicate and out-of-order webhooks.
- [x] Cover canceled, failed, returned, and delivered route policies locally;
  P5 hosted evidence already confirms canceled and delivered side effects.
- [ ] Verify the complete real-delivery chain across n8n executions, GHL
  opportunity changes, staff/customer SMS, Store UI, and logs.
- [x] Add a reconciliation/ops checklist for deliveries stuck in non-terminal
  states: [`docs/UBER_DIRECT_RECONCILIATION.md`](../UBER_DIRECT_RECONCILIATION.md).

P6 evidence and current boundary:

- OAuth authentication passed against Uber sandbox without exposing the token.
- A quote-only request succeeded for a nearby public business destination:
  CAD 10.49, 54-minute estimate. No delivery/courier was created.
- Quote binding/expiry safeguards passed: 5 tests.
- Pickup regression and outbound Uber guard passed: 9 tests plus the direct
  `not_delivery` assertion.
- Controlled pay-later dispatch/replay/failure coverage passed: 6 tests.
- Pay-now coverage passed: 10 tests. A new regression proves approved-payment
  fulfillment submits the kitchen order, dispatches Uber, and emits downstream
  notifications exactly once.
- Quote-outage safeguards passed: 4 tests.
- Webhook authentication, deduplication, ordering, and relay retry passed:
  11 tests.
- Explicit failed/returned n8n fixtures now join canceled under the staff-alert
  policy without customer promises.
- The final combined P4-P6 focused suite passed: 107 tests.
  `git diff --check` passed.
- Real delivery creation is not attempted while Uber billing/tax setup is
  incomplete. The local configuration also lacks pickup coordinates, an Uber
  webhook signing secret, and the n8n webhook secret. The n8n draft remains
  inactive and production remains unchanged.

**Approval gate:** sandbox evidence review before P7.

### P7 — Production-readiness review

Goal: decide whether to enable production; this phase does not flip the switch.

- Review rate limits, secrets, alert ownership, retry policy, quiet hours, and
  customer copy.
- Confirm manual dispatch fallback and who responds to alerts.
- Confirm monitoring and rollback/kill-switch procedure.
- Decide whether JSON persistence is acceptable for the pilot or must move to
  Supabase/Postgres first.
- Produce a production enablement checklist.

**Final stop:** production enablement requires a separate explicit approval.

---

## 7. Testing strategy

### Unit/contract

- Quote fingerprint and structured-address matching.
- Checkout and dispatch idempotency.
- Post-kitchen dispatch failure state.
- Uber signature verification and event parsing.
- Duplicate/out-of-order lifecycle transitions.
- Stable n8n envelopes and event IDs.

### Workflow

- One n8n execution fixture per event.
- Duplicate event produces no second SMS/opportunity.
- Unknown event has no GHL side effect.
- Missing/invalid webhook secret has no GHL side effect.

### Sandbox

- Full delivery pay-later and pay-now.
- Success, timeout/retry, cancellation, return, and failure.
- Correct address and fee visible in Store, Clover, Uber, n8n, and GHL.

---

## 8. Operational inputs

Needed before P6:

- Live n8n workflow export.
- Uber Direct customer/client credentials in sandbox.
- Uber webhook signing key.
- Real Bizbull pickup phone.
- Pickup latitude/longitude.
- Confirmation that the Uber organization billing/tax setup is complete.
- GHL destination for urgent `dispatch_required` alerts.
- Named staff owner for manual courier recovery.

Secrets stay in environment/credential stores and are never committed.

---

## 9. Out of scope

- Uber Eats marketplace.
- Phone/Sierra voice courier dispatch.
- Production enablement.
- Multi-restaurant onboarding UI.
- General G3 abandoned-cart automation.
- Pickup completion automation without a Clover/staff source.
- Proof-of-delivery pictures/signatures/PIN in the first hardening pass.
- Replacing the existing Store or Clover checkout architecture.

---

## 10. Working agreement

1. Follow [`pr/pr_rules.md`](../../pr/pr_rules.md).
2. Work only on `pr_097_uber-direct-n8n-hardening`.
3. Complete one phase at a time.
4. After each phase: update this plan and the PR doc, show tests/evidence, then
   stop for explicit approval.
5. Do not push, open/merge a GitHub PR, deploy, change live n8n, or enable Uber
   production unless explicitly requested.
6. Never commit `.env`, Uber credentials, webhook keys, GHL PITs, or production
   workflow credentials.
