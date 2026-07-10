# PR 059 — Web UI: Soniox theme, menu pills, Sierra avatar

## Branch
`pr_059_web-ui-soniox-theme`

## What This PR Does

Revamps the customer web app (`voice.bizbull.ai` / `web/`) to match the Soniox voice-bot demo look and improve menu browsing: Soniox dark/light color tokens with a header theme toggle (light default), category pills with left/right scroll arrows and veg/non-veg filters, sensible category order (starters → mains → dessert → drinks → sides), browse-only menu (no Add — cart qty stays on Your Order), English-only chrome (tab title, call button, brand subtitle), and the Soniox-style SVG Sierra avatar (talking mouth / listening bars). Also adds a Vite dev proxy for `/token`, `/menu`, `/health` and a local runbook in `docs/LOCAL_DEV.md`.

## Files Added

### `pr/pr_059_web-ui-soniox-theme.md`
This PR doc.

### `docs/LOCAL_DEV.md`
Local three-process runbook (token server, web, agent), Windows `uv` trampoline note, VPS env capture steps.

### `docs/DEVELOPER_ONBOARDING.md`
Developer onboarding / architecture reference; local section points at `LOCAL_DEV.md`.

## Files Modified

### `web/src/index.css`
Soniox CSS variables (dark default tokens + `[data-theme="light"]`); aliases for older App.css names.

### `web/src/App.css`
Theme toggle styles; menu pills / arrows / diet filters; Sierra avatar rings and animations; surfaces use Soniox tokens.

### `web/src/App.tsx`
Light/dark toggle in header (persisted in `localStorage`); English brand subtitle.

### `web/src/components/LiveMenu.tsx`
Category pills + scroll arrows; All/Veg/Non-veg filter; category sort order; removed Add button (browse-only).

### `web/src/components/SierraPanel.tsx`
Replaced orb/BarVisualizer with Soniox SVG avatar; English Start Call / Connecting labels.

### `web/src/components/OrderPanel.tsx`
Empty-state copy no longer mentions tapping Add; English thank-you line.

### `web/index.html`
English-only title/meta; `lang="en"`; default `data-theme="light"`.

### `web/vite.config.ts`
Dev proxy: `/token`, `/menu`, `/health` → `http://127.0.0.1:8001`.

### `docs/README.md`
Link to `LOCAL_DEV.md`.

### `pr/README.md`
Index entry for PR 059.

## Files Deleted
None.

## What's NOT in This PR

- No agent / order-flow / Clover backend changes
- No admin UI changes
- No `.env` secrets
- No GitHub PR merge / VPS deploy (push branch only until requested)
- Store tab still a stub (full catalog browse deferred)

## How to Test

```powershell
# Terminal 1 — token server
uv run python -m uvicorn token_server:app --host 0.0.0.0 --port 8001 --reload

# Terminal 2 — web
cd web
npm run dev
```

1. Open http://localhost:5173 — light theme by default; toggle dark/light in header.
2. Menu: category pills ordered starters-first; arrows scroll hidden pills; Veg/Non-veg filters work; no Add buttons.
3. Sierra panel shows SVG avatar; Start Call is English-only.
4. Chrome tab title is `Bizbull Restaurant` (no Gurmukhi).
5. `/menu` loads via Vite proxy (no “Couldn’t load the menu” when token server is up).

## Post-Merge: VPS Pull Command
`cd /opt/livekit-sarvam && git pull origin main && (cd web && npm ci && npm run build) && systemctl reload caddy || true`
