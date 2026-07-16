# PR 072 — GHL Opportunity on Place (G2b)

## Branch
`pr_072_ghl-opportunity-on-place`

## What This PR Does
Extends the live n8n → GHL sync so each `order.placed` also creates (or moves) a **Voice Orders** opportunity into stage **Placed**, without changing confirm SMS (still tag-based). Pipeline, stages, and opportunity custom fields are created in GHL; IDs are locked in plan §7.2.

## Files Added
### `pr/pr_072_ghl-opportunity-on-place.md`
This ship record.

## Files Modified
### `n8n/sierra-ghl-connection-stub.json`
After contact upsert + tag re-arm: prepare opp payload → search open Abandoned for same contact/session → create Placed opp or move Abandoned→Placed. Fail-open (`neverError`) on opp HTTP nodes. Confirm SMS path unchanged.

### `n8n/README.md`
G2b status, re-import credential list (includes new opp nodes), expect opportunity in GHL, redact PIT to placeholder.

### `docs/plan/13-ghl-n8n-order-sync.md`
§7.2 pipeline/stage/field IDs; G2b marked in progress → done when imported/verified; production table + workflows updated.

### `docs/README.md`, `docs/vps-config.md`
Index / ops notes aligned with G2b.

## Files Deleted
None.

## What's NOT in This PR
- Sierra Python changes (G1 payload already has `event_id` / `session_id` / order fields)
- Abandoned emit from Sierra (G3)
- Clover completed → stage Completed (G4)
- HMAC / idempotency (G5)

## Verified (2026-07-17)
- Multi-order PowerShell tests → multiple Voice Orders / Placed opps
- Confirm SMS via GHL **Opportunity Created** + In Pipeline Voice Orders (Option B)
- Tag `order-placed` no longer used as SMS trigger

## How to Test
1. In n8n: deactivate old workflow → Import `n8n/sierra-ghl-connection-stub.json`
2. Attach **GHL Private Integration** on **all** GHL HTTP nodes (upsert, remove tag, add tags, search abandoned, create opp, update opp)
3. Active ON
4. PowerShell test from `n8n/README.md`
5. GHL: Opportunities → **Voice Orders** → **Placed**; confirm SMS workflow = Opportunity Created

## Post-Merge: VPS Pull Command
No agent restart required for G2b (n8n-only). Optional:
`cd /opt/livekit-sarvam && git pull origin main`
