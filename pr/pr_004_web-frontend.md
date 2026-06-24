# PR 004 — Web Frontend

## Summary
Minimal React web app for customers to call the voice agent from the browser.
Connects to LiveKit via WebRTC, enables microphone, and plays agent audio.

## Files Added
- `web/package.json` — Vite + React + livekit-client
- `web/tsconfig.json`
- `web/vite.config.ts`
- `web/index.html`
- `web/src/main.tsx`
- `web/src/App.tsx` — main UI: idle / connecting / connected / error states
- `web/src/index.css` — global styles
- `web/src/App.css` — component styles (saffron/orange Punjabi theme)

## Features
- "Start Call" button → fetches token from sarvam.bizbull.ai/token
- Connects to LiveKit room, enables mic
- Shows agent speaking / listening indicator with animated sound waves
- Mic mute/unmute toggle
- End call button
- Error state with retry
- Responsive (mobile-first)

## VPS Deploy Commands
Run once after merging:

```bash
# Install Node if not present
node -v || (curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && apt-get install -y nodejs)

# Build
cd /opt/livekit-sarvam/web && npm install && npm run build

# Update Caddyfile: replace sarvam.bizbull.ai block
```

Update `sarvam.bizbull.ai` block in `/etc/caddy/Caddyfile` to:
```
sarvam.bizbull.ai {
  handle /token* {
    reverse_proxy localhost:8001
  }
  handle /health {
    reverse_proxy localhost:8001
  }
  handle {
    root * /opt/livekit-sarvam/web/dist
    file_server
    try_files {path} /index.html
  }
}
```

```bash
systemctl reload caddy
```

Then open https://sarvam.bizbull.ai in browser to test.
