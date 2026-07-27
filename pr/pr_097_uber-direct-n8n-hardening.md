# PR 097 — Uber Direct + n8n production hardening

## Branch

`pr_097_uber-direct-n8n-hardening`

## What This PR Does

Hardens the existing Store Uber Direct and n8n/GHL integration for a safe
sandbox pilot and later production-readiness review. The work binds Uber quotes
to the checked-out delivery address, makes courier dispatch idempotent and
operationally visible on failure, verifies and orders Uber webhook events, and
adds explicit authenticated/idempotent n8n routes for payment receipts, courier
tracking, dispatch failures, and selected delivery lifecycle updates.

Plan:
[`docs/plan/17-uber-direct-n8n-hardening.md`](../docs/plan/17-uber-direct-n8n-hardening.md)

## Current Status

| Phase | Scope | Status |
|------|-------|--------|
| **P0** | Plan + PR doc + branch | Complete |
| **P1** | Quote/address contract | Complete |
| **P2** | Dispatch idempotency + failure state | Complete |
| **P3** | Uber webhook security + lifecycle correctness | Complete |
| **P4** | n8n router + auth + idempotency | Complete and approved |
| **P5** | Delivery status → n8n/GHL | Complete in inactive draft; controlled routes verified |
| **P6** | Sandbox end-to-end + reconciliation | Local/quote checks complete; real delivery blocked by billing/config |
| **P7** | Production-readiness review | Not started |

P4 is approved after inactive-draft sandbox verification. P5a implements the
repository-side durable lifecycle relay, P5b adds the isolated repository
n8n/GHL status branch, and P5c/P5d configure and verify that branch in the
hosted inactive draft. Production remains unchanged.

## Files Added

### `docs/plan/17-uber-direct-n8n-hardening.md`

Defines the locked safety principles, event and delivery-state contracts,
phased implementation, approval gates, test strategy, operational inputs, and
production boundary.

### `docs/UBER_DIRECT_RECONCILIATION.md`

Adds the manual safety and cross-system reconciliation checklist for uncertain
Create Delivery outcomes and deliveries stuck in non-terminal states.

### `pr/pr_097_uber-direct-n8n-hardening.md`

This ship record. It will be updated after every approved phase so its file list,
decisions, tests, and deployment notes remain accurate.

### `restaurant/store_checkout_store.py`

Adds a durable JSON-backed checkout idempotency store. It atomically claims a
checkout key, rejects key reuse with a different request fingerprint, and
replays the completed Place response without another kitchen-order attempt.

### `tests/test_store_checkout_store.py`

Covers checkout claim, completion, replay, and conflicting key reuse.

### `tests/test_uber_dispatch_store.py`

Covers dispatch claim/success/replay, stale uncertain claims, and explicit
durable failure state.

### `tests/test_uber_webhook.py`

Covers raw-byte signature verification, endpoint rejection before mutation,
modern and legacy payload parsing, malformed/unknown events, durable
deduplication, out-of-order and terminal-state protection, canceled-to-returned
handling, reconciliation fields, Get Delivery, and the legacy resource URL
allowlist. P5a adds pending-relay retry, stored notification evidence, and
single-milestone coverage.

### `n8n/P4_ROUTER_SETUP.md`

Defines the private Header Auth credential, event-claim Data Table schema,
staff-alert variable and Community-instance fallback, GHL scope, branch
contract, duplicate/unknown/failure sandbox checks, cutover, and rollback.

### `n8n/fixtures/p4-events.json`

Provides credential-free fixtures for order placed, order paid, courier
dispatched, dispatch required, and unknown-event executions.

### `tests/test_n8n_p4_workflow.py`

Validates workflow JSON integrity, authentication-before-routing,
claim-before-side-effect ordering, event-branch isolation, dead-letter
isolation, GHL message API configuration, private staff configuration, and
fixture coverage.

## Files Modified

### `restaurant/uber_direct/address.py`

Adds normalized, stable address identity helpers and a SHA-256 destination
fingerprint. Harmless case, whitespace, and Canadian postal formatting changes
produce the same identity; a real destination change does not.

### `restaurant/uber_direct/quote_store.py`

Stores the destination fingerprint with every new Uber quote. Pre-P1/legacy
quotes without a binding are intentionally unverifiable and must be refreshed.

### `restaurant/uber_direct/service.py`

Records the quote fingerprint and dispatches from the validated checkout
summary, never from the quote store's informational address copy. Dispatch
performs a second fingerprint check before calling Uber. It now claims each
kitchen order before Create Delivery, replays completed claims, immediately
persists successful delivery creation, and records explicit or uncertain
`dispatch_required` outcomes without an unsafe retry. P5a also persists the
minimal Store customer/order context required for later lifecycle messages.

### `restaurant/uber_direct/delivery_store.py`

Adds durable order-to-delivery dispatch claims and `dispatch_required` records,
including reasons, attempts, timestamps, uncertainty, delivery IDs, and
tracking URLs. It now also stores authenticated event IDs, accepts each event
once, prevents stale lifecycle regression, and updates the external kitchen
order mapping with the accepted Uber state. P5a adds selected milestones and
retry evidence for each n8n lifecycle relay.

### `restaurant/uber_direct/webhook.py`

Replaces best-effort field extraction with exact raw-body HMAC-SHA256
verification and deliberate parsing of `event.delivery_status` and
`dapi.status_changed`. It normalizes documented legacy statuses and extracts
event time, tracking, external order, cancellation, undeliverable, and related
delivery fields.

### `restaurant/uber_direct/client.py`

Adds modern Get Delivery by known delivery ID and a legacy `resource_href`
reader restricted to Uber's HTTPS API host and documented delivery-order path.

### `restaurant/uber_direct/config.py`

Adds the webhook signing-key accessor.

### `n8n/sierra-ghl-connection-stub.json`

Upgrades the active-source workflow into an authenticated event router with
durable Data Table claims. It preserves the existing `order.placed` path and
adds isolated receipt, tracking, staff-alert, duplicate, invalid, failed, and
dead-letter paths. Instance credentials, table ID, and staff phone remain
private setup values.

### `n8n/README.md`

Documents the P4 router behavior and safe import sequence.

### `n8n/ORDER_PAID_RECEIPT_SMS.md`

Marks the receipt branch implemented and links to the P4 setup/runbook.

### `n8n/DELIVERY_DISPATCHED_TRACKING_SMS.md`

Marks the tracking branch implemented and links to the P4 setup/runbook.

### `restaurant/store_checkout.py`

Validates the structured delivery destination, creates the server-owned
one-line Clover/n8n address, persists the normalized destination in the summary,
and requires a fresh matching Uber quote when Direct is enabled. Missing,
expired, legacy/unverifiable, and address-mismatched quotes fail closed.
It also applies checkout idempotency around Place, covers both pay-later and
pay-now fulfillment, persists the dispatch result into the checkout response,
and emits courier outcome events before the final order notification.

### `restaurant/integrations/n8n_webhook.py`

Adds the stable `delivery.dispatch_required:{clover_order_id}` envelope and
notification helper. `order.placed` now carries delivery fulfillment status and
dispatch reason so downstream customer copy can distinguish kitchen acceptance
from courier assignment. P5a adds the stable
`delivery.status:{uber_event_id}` lifecycle envelope and notifier.

### `token_server.py`

Adds `delivery_dropoff` to the Store checkout request using the same structured
model as quote creation, plus the client checkout idempotency key. The Uber
webhook endpoint now authenticates the exact raw request before parsing,
reconciles legacy resource payloads on a best-effort basis, and atomically
applies or deduplicates lifecycle events. P5a records notification attempts,
returns 502 when an enabled downstream relay remains pending, and retries that
relay on a duplicate Uber webhook without reapplying delivery state.

### `web/src/lib/api.ts`

Adds the structured checkout/dropoff wire types, checkout key, and dispatch
outcome fields.

### `web/src/components/StoreTab.tsx`

Sends the current structured destination during both review validation and final
Place, so the server rechecks the contract after the review-screen delay. It
uses one checkout key per order attempt and shows explicit
restaurant-arranging-delivery copy when the kitchen order exists but no courier
is confirmed.

### `tests/test_uber_direct.py`

Covers stable/different address fingerprints and proves dispatch uses the
checked-out destination rather than the quote's stored address copy. It also
proves successful dispatch replay performs one Uber POST and uncertain outcomes
are not retried. P5a verifies the persisted delivery notification context.

### `tests/test_store_checkout.py`

Covers normalized matching, missing quote, expired quote, changed address,
unverifiable legacy quote, normalized server-owned display address, and pay-now
preservation of the bound destination.
It also covers checkout replay/conflict behavior, pay-now replay, and pay-later
post-kitchen dispatch escalation.

### `tests/test_n8n_webhook.py`

Covers the dispatch-required event contract and restaurant alert delivery
without requiring a customer phone number. P5a covers lifecycle envelope
identity, milestone metadata, and issue events without a customer phone.

### `.env.example`

Documents the optional checkout-idempotency store path and that the
per-webhook Uber signing key is mandatory for callback processing.

### `.gitignore`

Ignores runtime checkout and dispatch state files and their temporary files.

### `docs/plan/17-uber-direct-n8n-hardening.md`

Marks P1 complete and records the implemented contract/compatibility decisions.

### `pr/pr_097_uber-direct-n8n-hardening.md`

Records the P1 files, behavior, and verification evidence.

## Files Deleted

None.

## P5a Backend Relay

- New Uber deliveries retain the minimal context required to identify the
  customer and matching Clover/GHL order during later callbacks.
- Accepted statuses emit `delivery.status_changed` with stable event identity.
- `pickup_complete` emits the single `on_the_way` milestone. `dropoff` emits it
  only when pickup completion was not previously observed.
- `delivered` selects the delivery-confirmation milestone.
- `canceled`, `failed`, and `returned` select a staff alert and no automatic
  customer promise.
- A failed enabled n8n call is recorded after state application and returns 502.
  The same Uber event retries the pending notification without applying the
  status twice.
- P5a was not deployed and the inactive n8n draft was not changed.

## P5b Repository n8n Lifecycle Branch

- The inactive repository workflow now routes `delivery.status_changed` after
  all existing P4 events and before the unsupported-event dead letter.
- Every accepted lifecycle event upserts `delivery.<status>` to the existing
  contact order-status field.
- CRM-only statuses send no SMS.
- `on_the_way` sends one customer tracking SMS.
- `delivered` matches the opportunity by Clover order ID, moves only the match
  to Completed, and sends the customer delivery confirmation.
- `canceled`, `failed`, and `returned` alert the private staff contact; they do
  not promise an outcome to the customer or move the opportunity to Lost.
- A missing delivered opportunity returns a retryable side-effect failure
  instead of moving an arbitrary record.
- The hosted inactive n8n draft, active production workflow, credentials, and
  backend deployment were not changed.

## P5c/P5d Inactive-Draft Verification

- Configured the P5 lifecycle branch in the existing inactive hosted draft.
- Verified invalid-status dead-letter and replay deduplication with no GHL/SMS
  side effects.
- Verified CRM-only pickup completion without SMS.
- Verified the on-the-way customer tracking SMS and confirmed receipt.
- Verified canceled-delivery staff alerting and confirmed receipt without a
  customer SMS.
- Verified delivered-opportunity lookup by Clover order ID, movement of only
  the dedicated test opportunity to Completed, and customer delivery SMS
  receipt.
- Removed the unused Data Table `completed_at` claim mapping because the hosted
  node serializes an empty value as `{}`.
- Extended the delivered resolver to read GHL custom-field values returned as
  `fieldValueString`.
- The draft remained inactive, and the existing production workflow remained
  active and unchanged.

## P6 Sandbox Progress

- Uber sandbox OAuth authentication passed without exposing the access token.
- A quote-only request to a nearby public business address succeeded at
  CAD 10.49 with a 54-minute estimate; no courier was created.
- Pickup behavior, quote binding/expiry, pay-later dispatch safety, pay-now
  fulfillment, quote outage, webhook signatures, duplicate/out-of-order
  handling, and n8n relay retry were verified locally.
- Added a pay-now regression proving approved-payment fulfillment submits the
  kitchen order, dispatches Uber, and notifies downstream exactly once.
- Added explicit failed and returned lifecycle fixtures; both use the same
  staff-alert/no-customer-promise policy already hosted-tested with canceled.
- Added the Uber Direct reconciliation checklist.
- Real pay-later/pay-now delivery creation and complete cross-system evidence
  remain blocked until Uber billing/tax setup, pickup coordinates, the Uber
  webhook signing key, and n8n webhook secret are configured.
- The n8n draft remains inactive and production remains unchanged.

## What's NOT in This PR

- Uber Eats marketplace.
- Phone/Sierra voice delivery dispatch.
- General abandoned-cart automation.
- Multi-restaurant Uber onboarding UI.
- Production enablement or credential changes.
- Unapproved changes to live n8n, GHL, VPS, or Uber configuration.

## How to Test

P4 focused:

```powershell
$env:PYTHONPATH = "."
.\.venv\Scripts\python.exe -m pytest `
  tests/test_n8n_p4_workflow.py `
  tests/test_n8n_webhook.py `
  tests/test_store_checkout.py -q
```

Result: **51 passed**.

Full suite:

```powershell
$env:PYTHONPATH = "."
.\.venv\Scripts\python.exe -m pytest tests -q
```

Result: **601 passed, 2 failed**. The two failures are the pre-existing
`tests/test_hosted_checkout.py::test_place_pay_now_disabled_no_url` and
`test_place_pay_now_hco_failure_still_places`, already documented on PR 096 as
failing on main and unrelated to P4.

Web:

```powershell
cd web
npm run build
```

Result: TypeScript and Vite production build passed. Vite reports the existing
large-chunk advisory only.

Python bytecode compilation and `git diff --check` also passed.

P5a focused backend relay:

```powershell
$env:PYTHONPATH = "."
.\.venv\Scripts\python.exe -m pytest `
  tests/test_uber_webhook.py `
  tests/test_n8n_webhook.py `
  tests/test_uber_direct.py -q
```

Result: **48 passed**.

P5a checkout/payment regression:

```powershell
$env:PYTHONPATH = "."
.\.venv\Scripts\python.exe -m pytest `
  tests/test_store_checkout.py `
  tests/test_store_pay_now.py `
  tests/test_store_checkout_store.py `
  tests/test_uber_dispatch_store.py -q
```

Result: **42 passed**.

P5a full suite result: **605 passed, 2 failed**. The failures remain the
pre-existing hosted-checkout expectations listed above; no new regression was
introduced.

P5b repository workflow checks:

```powershell
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider `
  tests/test_n8n_p4_workflow.py `
  tests/test_n8n_p5_workflow.py `
  tests/test_n8n_webhook.py `
  tests/test_uber_webhook.py
```

Result: **49 passed**. A separate graph/JavaScript validation confirmed 75
unique nodes, 19 P5 nodes, valid connection targets, syntactically valid Code
nodes, and `active: false`.

P5c/P5d hosted-compatibility regression:

```powershell
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider `
  tests/test_n8n_p4_workflow.py `
  tests/test_n8n_p5_workflow.py
```

Result: **16 passed**. `git diff --check` also passed.

P6 focused regression:

```powershell
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider `
  tests/test_n8n_p4_workflow.py `
  tests/test_n8n_p5_workflow.py `
  tests/test_n8n_webhook.py `
  tests/test_uber_webhook.py `
  tests/test_uber_direct.py `
  tests/test_uber_dispatch_store.py `
  tests/test_store_checkout_store.py `
  tests/test_store_pay_now.py `
  tests/test_store_checkout.py
```

Result: **107 passed**. `git diff --check` passed.

## P5 Operational Evidence

The P5 route was tested only in the inactive draft. Controlled evidence:

| Execution | Result |
|---|---|
| `2177` | Empty `completed_at` claim mapping failed safely before GHL/SMS; mapping removed |
| `2178` | Invalid status dead-lettered with no GHL/SMS side effect |
| `2179` | Replay of the invalid event stopped at duplicate detection |
| `2180` | CRM-only pickup route completed without SMS |
| `2181` | On-the-way route reached GHL SMS but was blocked by customer SMS DND; event failed safely |
| `2182` | Corrected on-the-way route completed; customer confirmed tracking SMS |
| `2183` | Canceled route completed; staff confirmed urgent SMS and no customer SMS was sent |
| `2184` | Dedicated Placed test opportunity created for delivered-route verification |
| `2185` | Delivered route failed safely when the resolver missed GHL `fieldValueString`; no opportunity move/SMS |
| `2186` | Dedicated opportunity matched and moved to Completed; customer confirmed delivery SMS |

Test claims and GHL artifacts were intentionally retained as audit evidence.

## P4 Operational Evidence

The repository workflow was imported as the inactive draft
`Bizbull · Sierra Events → GHL Router-updated`. The existing production workflow
remained active and unchanged throughout testing.

| Evidence | Result |
|---|---|
| Actual HTTP request with incorrect webhook secret | `403 Forbidden`; no workflow execution or side effect |
| Actual HTTP request with configured webhook secret | Accepted by the Webhook node |
| `2167` | Invalid envelope stopped before Data Table and GHL |
| `2168` | Unsupported event stored as `dead_letter`; no GHL request |
| `2169` | Duplicate dead-letter event stopped before another write or GHL request |
| `2170` | `order.placed` without phone used the compatibility skip and completed |
| `2171` | Staff contact upsert + dispatch-required SMS received; claim completed |
| `2172` | Customer upsert + receipt SMS received; no opportunity path |
| `2173` | Customer upsert + tracking SMS received; no opportunity path |
| `2174` | MCP manual wrong-secret probe bypassed trigger auth and dead-lettered; not auth evidence |
| `2175` | Correct-secret node-listener execution accepted at the Webhook node |
| `2176` | Existing order path updated fields/tags, created Placed opportunity, and sent confirmation SMS |

The self-hosted Community instance locks `$vars`. Its private imported draft
therefore uses a workflow-local E.164 staff number, while the credential-free
repository JSON retains `BIZBULL_STAFF_ALERT_PHONE`. Test claims and GHL
artifacts were intentionally retained as audit evidence.

## P4 Operational Boundary

- The updated workflow is configured and tested but remains inactive.
- The old workflow remains the sole active owner of `sierra-ghl-sync`.
- Uber lifecycle events are persisted locally but are not emitted to n8n/GHL
  until P5.
- The temporary webhook secret must be rotated in both n8n and Sierra before
  activation because it appeared in test evidence.
- No production cutover, Uber production flag, deployment, commit, or push was
  performed.

## Post-Merge: VPS Pull Command

Not approved yet. Production deployment and `STORE_UBER_DIRECT_ENABLED` remain
outside this PR until the P7 production-readiness review receives separate
explicit approval.
