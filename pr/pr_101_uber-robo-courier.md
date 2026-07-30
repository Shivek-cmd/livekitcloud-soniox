# PR 101 - Sandbox Uber Robo Courier

## Branch

`pr_101_uber-robo-courier`

## Purpose

Allow one sandbox web-store delivery to exercise the full Uber lifecycle
automatically: courier assignment, pickup, dropoff, signed Uber webhooks,
n8n/GHL routing, customer SMS, and opportunity completion.

## Implementation

- Add `UBER_DIRECT_ROBO_COURIER_ENABLED`, default off.
- Require both the explicit flag and `UBER_DIRECT_ENV=sandbox`.
- Add Uber `test_specifications.robo_courier_specification.mode=auto` only when
  both safeguards pass.
- Omit the normal pickup-ready timestamp in Robo Courier mode so the automated
  sandbox lifecycle starts immediately and finishes in roughly three minutes.
- Preserve the normal pickup-ready timestamp for every non-Robo request.
- Document configuration and production safety.

## Production safety

- Production requests never include `test_specifications`, even if the feature
  flag is accidentally enabled.
- The setting is disabled by default.
- No changes to payment, kitchen submission, webhook authentication, n8n, GHL,
  or SMS behavior.

## Verification

- `python -m pytest tests/test_uber_direct.py`
  - 21 passed
- `python -m pytest tests/test_uber_webhook.py tests/test_store_checkout.py tests/test_store_pay_now.py`
  - 56 passed
- Production-guard coverage confirms `UBER_DIRECT_ENV=production` never adds
  Robo Courier `test_specifications`, even when the flag is enabled.
- `git diff --check`
