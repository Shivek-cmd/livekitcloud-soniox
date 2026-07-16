# PR 071 — n8n order.placed webhook (Sierra → GHL)

## Branch
`pr_071_n8n-order-placed-webhook`

## What This PR Does
Wires Sierra’s successful `place_order` path to the production n8n webhook
so live phone/web orders upsert GHL contacts, set Phase 0 fields/tags, and
re-arm confirm SMS — without PowerShell. Fail-open: n8n errors never block
goodbye or hang-up. Kill switch: `N8N_SYNC_ENABLED` (default **off** until
flipped on VPS).

Note: PR **070** was already used (`pr_070_phase-1-hygiene-observability` / #110).

## Files Added
### `pr/pr_071_n8n-order-placed-webhook.md`
This PR doc.

### `restaurant/integrations/__init__.py`
Package marker.

### `restaurant/integrations/n8n_webhook.py`
Env helpers, normalized `order.placed` envelope (G0 contract), async POST with
timeout; never raises into the agent.

### `tests/test_n8n_webhook.py`
Enable/url/secret, envelope shape, phone E.164, mocked HTTP, disabled path.

### `docs/plan/13-ghl-n8n-order-sync.md` + `n8n/`
G0 plan + importable n8n workflow (already built/tested; committed with G1).

## Files Modified
### `restaurant/agent/core.py`
After successful place, await `notify_order_placed` (fail-open) before goodbye.

### `.env.example`
`N8N_SYNC_ENABLED`, `N8N_WEBHOOK_ORDERS_URL`, `N8N_WEBHOOK_SECRET`.

### `docs/README.md`, `docs/vps-config.md`, `docs/plan/13-ghl-n8n-order-sync.md`
Index + ops notes; G1 marked implemented.

### `tests/test_agent_place_order.py`
Assert n8n notify is invoked on successful place; not on blocker/failure.

## Files Deleted
None.

## What's NOT in This PR
- `order.place_failed` / abandoned session (G3)
- Clover completed webhooks (G4)
- Enabling `N8N_SYNC_ENABLED=1` on VPS (ops after merge)

## How to Test
```
uv run --with pytest python -m pytest tests/test_n8n_webhook.py tests/test_agent_place_order.py -q
```
Local smoke: set `N8N_SYNC_ENABLED=1` and prod webhook URL in `.env`, place a
test order → n8n execution + GHL contact/SMS.

## Post-Merge: VPS Pull Command
```
cd /opt/livekit-sarvam && git pull origin main && uv sync
# Add to .env:
# N8N_SYNC_ENABLED=1
# N8N_WEBHOOK_ORDERS_URL=https://n8n.bizbull.ai/webhook/sierra-ghl-sync
systemctl restart restaurant-agent
```
