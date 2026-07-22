# PR 089 — Web Store (plan + step-by-step build)

## Branch
`pr_089_web-store-plan`

## What This PR Does
Builds the production **Store** tab at `voice.bizbull.ai` on this single branch:
browse menu → cart → pickup/delivery checkout (pay later), via a **thin Store API**
that revalidates against the menu cache, then reuses Clover submit + n8n/GHL
`order.placed`. Phases **S0→S8** done on branch.

### Locked decisions
- Pickup + delivery; pay later (name, phone, address for delivery)
- Thin Store API (not browser→n8n-only, not voice-agent reuse)
- Guest checkout; same GHL Voice Orders / Placed + confirm SMS as voice (**pickup and delivery**)
- All phases on **PR 089**
- Dish photos from `GET /menu` only (Clover when synced; Unsplash demo fill meanwhile)

## Files Added
### `docs/plan/14-web-store.md`
Store plan + architecture + S0–S8 phasing.

### `pr/pr_089_web-store-plan.md`
This ship record.

### `web/src/lib/menuSort.ts` / `storeCart.ts` / `hooks/useStoreCart.ts` / `categoryTheme.ts`
Browse sort, local cart, category themes.

### `restaurant/store_checkout.py`
Validate + place (Clover + n8n). Channel `web_store`.

### `restaurant/store_rate_limit.py`
In-memory per-IP rate limit for `POST /store/checkout` (S5).

### `restaurant/demo_menu_images.py`
Unsplash demo fill + Clover image extract helpers (S7).

### `tests/test_store_checkout.py` / `tests/test_store_rate_limit.py` / `tests/test_demo_menu_images.py`
Checkout, rate-limit, and image catalog unit tests.

## Files Modified
### Docs
`docs/README.md`, `docs/plan/06-milestones.md`, `docs/plan/11-web-order-with-sierra.md`,
`docs/vps-config.md` (Caddy `handle /store*`), `docs/LOCAL_DEV.md`, `.env.example`.

### Runtime
`token_server.py` — `/store/checkout` + rate limit; CORS POST.
`restaurant/menu_provider.py` — `item_has_spice_by_id`.
`restaurant/clover/menu.py` / `models.py` — `image_url` cache + catalog.
`web/src/components/StoreTab.tsx`, `LiveMenu.tsx`, `api.ts`, `App.css`, `vite.config.ts`.

## Kill switches
| Env | Effect |
|-----|--------|
| `CLOVER_SUBMIT_ORDERS` | Clover kitchen ticket vs `LOG-…` id |
| `N8N_SYNC_ENABLED` | GHL SMS / opp (fail-open) |
| `STORE_CHECKOUT_RATE_LIMIT` / `_WINDOW_SEC` | Checkout rate limit (default 20 / 60s) |
| `STORE_DEMO_IMAGES` | Unsplash fill when Clover image missing (default on) |

## UX notes (S8)
- Quiet All / Veg / Non-veg chips; left category nav; search across menu
- Inline spice expand on card (no modal); cart panel slides in from the right
- Dish thumbs on cart / review / thank-you lines

## How to Test
- Local: token server + `npm run dev` → Store full place flow (pickup **and** delivery); confirm SMS via n8n when enabled
- Cards show photos from `/menu`; cart shows thumbs after first add
- VPS: add Caddy `handle /store*` then reload Caddy + rebuild web + restart `restaurant-token`
- `PYTHONPATH=. uv run --with pytest pytest tests/test_store_checkout.py tests/test_store_rate_limit.py tests/test_demo_menu_images.py -q`

## Post-Merge: VPS
```bash
cd /opt/livekit-sarvam
# after merge to main:
git pull origin main
# ensure Caddy has handle /store* (see docs/vps-config.md)
(cd web && npm install && npm run build)
systemctl restart restaurant-token
systemctl reload caddy
```

## Later (after demo)
Upload real photos in Clover Dashboard → re-run menu sync → Clover URLs replace demo fill automatically.
