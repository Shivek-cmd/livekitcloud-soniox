# P4 · Sierra event router setup

The repository workflow now routes Sierra events explicitly and records a
durable event claim before any GHL side effect.

Import:

`n8n/sierra-ghl-connection-stub.json`

Keep the imported workflow inactive until every item below is configured and
the sandbox executions pass.

## 1. Create the event-claim Data Table

Create a Data Table named `sierra_event_claims` with these columns:

| Column | Type |
|---|---|
| `event_id` | String |
| `event` | String |
| `status` | String |
| `received_at` | Date |
| `completed_at` | Date |
| `last_error` | String |

In every node whose name begins with `P4 · Data Table ·`, select that table.
The import contains `REPLACE_WITH_SIERRA_EVENTS_TABLE_ID` deliberately; it is
not a real ID.

Claims use these states:

- `processing`: claimed before a GHL write.
- `completed`: side effect succeeded or the existing `order.placed` no-phone
  compatibility path was intentionally skipped.
- `failed`: GHL contact/message/opportunity evidence was not returned. A later
  retry may claim this event again.
- `dead_letter`: authenticated event with an unsupported event type or invalid
  branch-specific fields. It has no GHL side effect.

Do not manually delete `processing` claims without checking n8n executions and
GHL first. A side effect may have succeeded before the execution stopped.

## 2. Attach webhook authentication

Create an n8n **Header Auth** credential:

| Field | Value |
|---|---|
| Name | `X-Webhook-Secret` |
| Value | Same private value as Sierra `N8N_WEBHOOK_SECRET` |

Attach it to `01 · Receive Order Webhook`. Never put the secret in workflow
JSON.

The workflow must remain inactive if this credential is missing. Sierra already
sends the header when `N8N_WEBHOOK_SECRET` is configured.

## 3. Configure the staff alert privately

Create the n8n variable:

`BIZBULL_STAFF_ALERT_PHONE`

Set it to the E.164 phone number of the staff member responsible for recovering
failed courier dispatches. The value is not committed to this repository.

### Self-hosted Community fallback

Some Community instances show **Upgrade to unlock variables**. In that case,
open `P4 · Normalize Envelope` in the private imported workflow and replace:

```javascript
const staffPhone = String($vars.BIZBULL_STAFF_ALERT_PHONE || '').trim();
```

with a private E.164 literal:

```javascript
const staffPhone = '+1XXXXXXXXXX';
```

Do not put the real phone number in repository JSON, screenshots, PR text, or
chat. Do not export the privately configured workflow over the credential-free
repository file.

## 4. Attach the GHL credential

Attach the existing `GHL Private Integration` Header Auth credential to every
GHL HTTP Request node, including the new P4 nodes.

The PIT must retain the existing contact/opportunity/tag scopes and add:

- `conversations/message.write`

The new message paths use:

- `POST /conversations/messages`
- `type: SMS`
- the contact ID returned by `POST /contacts/upsert`

## 5. Branch contract

| Event | Side effects |
|---|---|
| `order.placed` | Existing contact, tags, Placed opportunity, existing confirmation automation |
| `order.paid` | Customer upsert and receipt SMS only |
| `delivery.dispatched` | Customer upsert and tracking SMS only |
| `delivery.dispatch_required` | Staff-contact upsert and urgent staff SMS only |
| Unknown | Durable dead letter and HTTP 202; no GHL request |

Receipt, tracking, and staff-alert branches never enter the Placed opportunity
nodes.

## 6. Sandbox verification

Use the fixtures in `n8n/fixtures/p4-events.json`. Send the
`X-Webhook-Secret` header on every request.

For each supported event:

1. Send it once and verify the expected single side effect.
2. Send the identical `event_id` again.
3. Verify the response contains `duplicate: true`.
4. Verify no second SMS, tag cycle, or opportunity was created.

Also verify:

- Missing/incorrect secret is rejected before execution.
- Missing `event_id` returns HTTP 400 and creates no Data Table row.
- Unknown event returns HTTP 202, creates a `dead_letter` row, and makes no GHL
  request.
- A simulated GHL failure records `failed` and returns HTTP 502.
- `order.paid` and `delivery.dispatched` do not create or move opportunities.

P4 evidence recorded on 2026-07-28:

- Actual HTTP auth rejected an incorrect secret with `403` before execution.
- Executions `2167`–`2170` covered invalid, dead-letter, duplicate, and
  no-phone completion paths.
- Executions `2171`–`2173` completed the staff-alert, receipt, and tracking
  branches; each expected SMS was received.
- Execution `2176` preserved the order contact/tag/opportunity path and its
  existing confirmation SMS.
- Execution `2174` is not authentication evidence: n8n MCP manual execution
  injects trigger data and bypasses HTTP credential validation.

## 7. Cutover and rollback

Before activation, export the currently active workflow as a dated backup.
Rotate the temporary webhook secret, update both the n8n Header Auth credential
and Sierra `N8N_WEBHOOK_SECRET`, and review n8n execution-data retention because
incoming webhook headers and payloads can appear in saved execution data. Then
deactivate the old workflow and activate only this configured workflow on
`sierra-ghl-sync`.

Rollback: deactivate this workflow and reactivate the dated backup. Do not run
two active workflows on the same production webhook path.
