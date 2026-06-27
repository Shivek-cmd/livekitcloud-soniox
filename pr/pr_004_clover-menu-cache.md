# PR 004 — Clover menu cache + tenant store (Phase 8b)

## Branch
`pr_004_clover-menu-cache`

## What This PR Does
Connects Sierra to **Clover as menu source of truth** for the single Bizbull demo tenant.
No order submission to Clover yet (Phase 8c).

1. **Tenant store** — SQLite with one Bizbull row (Clover creds, order type IDs, paths).
2. **Menu sync** — Pull Clover inventory → merge voice labels → write local cache file.
3. **Agent integration** — `USE_CLOVER_MENU=1` reads cache for lookup, search, and cart add.

Static `restaurant/menu.py` remains fallback when flag is off.

## Files Added

### `restaurant/tenants/store.py`
SQLite CRUD for tenant config (single row for demo).

### `restaurant/tenants/config.py`
`get_default_tenant()` — returns Bizbull tenant (only tenant for now).

### `restaurant/clover/models.py`
Cached menu item / modifier datatypes.

### `restaurant/clover/menu.py`
Sync from Clover API, load cache, fuzzy find + category search.

### `restaurant/menu_provider.py`
Facade: `find_item`, `search_menu`, `check_item` — Clover cache or static menu.

### `scripts/clover_init_tenant.py`
Bootstrap Bizbull tenant row from `.env` + sandbox order type IDs.

### `scripts/clover_sync_menu.py`
Sync menu cache for default tenant.

## Files Modified

### `agent.py`
Load menu cache when `USE_CLOVER_MENU=1`; add `search_menu_items` tool.

### `restaurant/orders.py`
Support dollar prices with cents (Clover `$8.99` items).

### `.env.example`
Add `USE_CLOVER_MENU`, `TENANT_DB_PATH`, order type ID vars.

### `.gitignore`
Ignore `data/tenants.db` and generated `data/menu_cache_*.json`.

## What's NOT in This PR
- Submit order to Clover (Phase 8c)
- Webhooks / 86'd items (Phase 8d)
- Multi-tenant phone routing (Phase 8f)
- OAuth production tokens

## How to Test

```bash
# 1. CLOVER_* in .env (sandbox)

# 2. Bootstrap tenant (once)
python scripts/clover_init_tenant.py

# 3. Sync menu from Clover
python scripts/clover_sync_menu.py

# 4. Enable Clover menu for agent
# USE_CLOVER_MENU=1 in .env

# 5. Run agent — ask:
#    "Do you have chole bhature combo?"
#    "What paneer dishes do you have?"
#    Add item → correct price in cart summary
```

**Exit criteria:** Sierra answers menu questions from Clover cache (61 items), not static `menu.py`.
