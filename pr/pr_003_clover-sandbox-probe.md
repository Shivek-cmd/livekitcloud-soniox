# PR 003 — Clover sandbox probe + menu seed (Phase 8a)

## Branch
`pr_003_clover-sandbox-probe`

## What This PR Does
First Clover integration PR — **sandbox only**, no agent changes. Adds scripts to:

1. **`clover_sandbox_cleanup.py`** — wipe existing sandbox orders + inventory items (fresh start).
2. **`clover_sandbox_seed.py`** — seed a production-style **Indian-Canadian restaurant menu** (61 items, 9 categories, 10 modifier groups, combos/platters).
3. **`clover_sandbox_probe.py`** — verify API auth, list menu, atomic checkout/create test order.

Uses production-style config via env vars (`CLOVER_BASE_URL`, `CLOVER_MID`, `CLOVER_API_TOKEN`).
Same code path works on local dev and VPS (`.env` not committed).

## Menu seed (Bizbull Restaurant)

| Category | Count | Notes |
|---|---|---|
| Starters & Snacks | 7 | tikka, pakora, chaat |
| Tandoor & Grill | 5 | half/full chicken, kebab, chops |
| Vegetarian Mains | 9 | dal, saag, paneer, chole |
| Non-Veg Mains | 8 | butter chicken, biryani, curries |
| Breads & Rice | 8 | naan, roti, paratha, rice |
| Combos & Platters | 8 | thali, student/couple/family/party trays |
| Drinks | 7 | lassi (size modifier), chai, shakes |
| Desserts | 5 | gulab jamun, kheer, halwa |
| Extras & Sides | 4 | raita, pickle, papad, gravy |

**Modifier groups:** spice level, bread choice, rice side, lassi size, combo drink, add extras, protein size, bhatura count, choose curry (veg/non-veg combos).

**Voice labels:** `data/clover_voice_labels.json` — Gurmukhi `speak_as` + STT `aliases` per item/modifier (not stored in Clover).

## Files Added

### `restaurant/clover/client.py`
Minimal REST client (env-based, paginated fetch).

### `restaurant/clover/seed_menu.py`
Declarative menu catalog (categories, items, modifier specs).

### `scripts/clover_sandbox_cleanup.py`
Lists and deletes sandbox orders and inventory items. Requires `--confirm`.

### `scripts/clover_sandbox_seed.py`
Creates Clover categories, modifier groups, items, associations; writes voice labels JSON.

### `scripts/clover_sandbox_probe.py`
Merchant info, item count, optional `--checkout` / `--create-order`.

### `data/clover_voice_labels.json`
Generated voice cache seed (Gurmukhi + aliases for Phase 8b).

## Files Modified

### `.env.example`
Add `CLOVER_*` placeholder vars for sandbox.

## What's NOT in This PR
- Agent / Sierra voice changes
- Runtime menu cache loader (Phase 8b)
- SQLite tenant store (Phase 8b)
- OAuth, webhooks, production URLs

## How to Test

```bash
# 1. Set CLOVER_* in .env (sandbox test merchant only)

# 2. Fresh sandbox (destructive — skips paid orders)
python scripts/clover_sandbox_cleanup.py --confirm

# 3. Seed menu (61 items)
python scripts/clover_sandbox_seed.py --confirm

# 4. Probe + test order
python scripts/clover_sandbox_probe.py
python scripts/clover_sandbox_probe.py --checkout --create-order
```

Verify test order in sandbox Merchant Dashboard → Orders.

**Verified locally:** 61 items seeded; atomic checkout + order create succeeded.

## Post-Merge: VPS
```bash
cd /opt/livekit-sarvam && git pull origin main && uv sync
# Add CLOVER_* to /opt/livekit-sarvam/.env manually
python scripts/clover_sandbox_seed.py --confirm   # if sandbox empty
```
