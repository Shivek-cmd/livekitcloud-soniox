# PR 011 — Web W1: shell (tabs + 3-panel layout + live menu + captions)

## Branch
`pr_011_web-w1-shell`

## What This PR Does

First implementation phase (**W1**) of the "Order with Sierra" plan
(`docs/plan/11-web-order-with-sierra.md`). Rebuilds the web app from a single "Start Call"
button into the production shell:

- **Tab switcher**: `Order with Sierra` | `Store` (Store is a "coming soon" placeholder).
- **Responsive 3-panel layout** (desktop 3-column / tablet 2-col / mobile stacked):
  1. **Sierra panel** — agent state indicator (listening / thinking / speaking), audio-reactive
     visualizer, **live captions**, and call controls. (Avatar video slot is wired but unused
     until W4.)
  2. **Live menu panel** — renders the full Clover catalog with **prices**, veg/non-veg, and
     sold-out state, fetched from a new `GET /menu` endpoint.
  3. **Order panel** — placeholder; live cart sync arrives in **W2**.
- Adopts **`@livekit/components-react`** (`LiveKitRoom`, `useVoiceAssistant`, `BarVisualizer`,
  `VoiceAssistantControlBar`, `RoomAudioRenderer`, `VideoTrack`) for state/captions/controls and
  forward-compatibility with the avatar (W4).

No cart sync, no avatar, no tap-to-add yet (W2–W4). The agent backend behavior is unchanged.

## Files Added
### `restaurant/` — none (only edits)
### `web/src/lib/api.ts`
Endpoint constants (`/token`, `/menu`), menu/token types, `fetchToken()`, `fetchMenu()`.
### `web/src/components/OrderWithSierra.tsx`
Owns the LiveKit connection (`LiveKitRoom`, `connect` toggled by Start) and the 3-panel grid.
### `web/src/components/SierraPanel.tsx`
Agent state + `BarVisualizer` (or avatar `VideoTrack` when present), live captions from
`useVoiceAssistant().agentTranscriptions`, Start button / `VoiceAssistantControlBar`.
### `web/src/components/LiveMenu.tsx`
Fetches `/menu`, renders categories → items (price, veg dot, sold-out).
### `web/src/components/OrderPanel.tsx`
W1 placeholder for the live cart (W2).
### `web/src/components/StoreTab.tsx`
"Coming soon" placeholder for the Store tab.

## Files Modified
### `token_server.py`
Adds `GET /menu` → returns the full catalog via `menu_provider.catalog()` (503 if unavailable).
### `restaurant/menu_provider.py`
Adds `catalog()` returning the cache's grouped catalog (or `None`).
### `restaurant/clover/menu.py`
Adds `MenuCache.catalog()` — menu grouped by category, JSON-serializable.
### `web/src/App.tsx`
Replaced single-button app with the tabbed shell.
### `web/src/App.css`
New stylesheet for shell + responsive 3-panel layout (reuses existing theme vars).
### `web/package.json`
Adds `@livekit/components-react`, `@livekit/components-styles`; widens `livekit-client` range.

## What's NOT in This PR
- Live order/cart sync (W2), menu highlight + modifier picker (W3), avatar (W4), hardening (W5),
  web prompt variant (W6).
- Store tab functionality, online payment, Clover order submit (8c).

## How to Test
```bash
cd web && npm install && npm run build   # builds clean
# Locally: npm run dev, open the app
# - Two tabs render; "Order with Sierra" shows 3 panels
# - Menu panel lists Clover items with prices (needs token server /menu reachable)
# - Start Call connects; state + captions update while talking to Sierra
```

## Post-Merge: VPS

`GET /menu` is served by the token server (port 8001). **Caddy must route `/menu` to 8001**
(same as `/token`). Add to the `voice.bizbull.ai` block:

```
  handle /menu* {
    reverse_proxy localhost:8001
  }
```

Then deploy (rebuilds web + restarts services):
```bash
bash /opt/livekit-sarvam/scripts/vps_deploy.sh
systemctl reload caddy
```
