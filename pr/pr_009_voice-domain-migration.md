# PR 009 — Web domain migration: sarvam.bizbull.ai → voice.bizbull.ai

## Branch
`pr_009_voice-domain-migration`

## What This PR Does

Migrates the live web voice app from **`sarvam.bizbull.ai`** to **`voice.bizbull.ai`**.
This is a **domain migration only** — the web app (React `web/`) is unchanged in behavior.

The only code change is making the frontend token endpoint **relative** (`/token`) instead of
hardcoding `https://sarvam.bizbull.ai/token`, so the app is domain-agnostic and works on
`voice.bizbull.ai` (or any future domain) with no rebuild-time domain coupling.

The Caddy reverse-proxy change (repointing `voice.bizbull.ai` and removing `sarvam.bizbull.ai`)
is applied **manually on the VPS** — the Caddyfile is not tracked in this repo. See
"Post-Merge: VPS" below.

## Context (current VPS state, verified)

| Domain | Before | After |
|--------|--------|-------|
| `sarvam.bizbull.ai` | Our web app (`web/dist` + `/token`→:8001) | **Removed from Caddy** (stops responding) |
| `voice.bizbull.ai` | `reverse_proxy localhost:8090` (Apache / getsetvisa) | **Our web app** (`web/dist` + `/token`→:8001) |

- DNS for both domains already resolves to the VPS — **no DNS change needed**.
- Apache (port 8090) and `getsetvisa.com` are **left untouched**; we only remove the
  `voice.bizbull.ai` mapping that pointed at it.

## Files Modified

### `web/src/App.tsx`
- `TOKEN_URL` changed from `https://sarvam.bizbull.ai/token` to relative `/token`.
  Frontend now calls the token server on whatever origin it is served from (same-origin,
  no CORS), so the domain is no longer baked into the build.

### `scripts/vps_deploy.sh`
- Added a web build step (`npm install && npm run build` in `web/`) before service restart, so future
  deploys rebuild `web/dist` automatically. `web/dist` is not tracked in git and is served by
  Caddy from `/opt/livekit-sarvam/web/dist`.

## Files Added
None.

## Files Deleted
None.

## What's NOT in This PR

- No change to the web app UI / behavior.
- No DNS changes (both domains already point at the VPS).
- No change to Apache / getsetvisa / port 8090.
- The Caddyfile edit itself (manual on VPS — not repo-tracked).
- Tier B voice fixes (echo filter, menu search) — parked.

## How to Test

Local build sanity:
```bash
cd web && npm install && npm run build   # dist builds, no hardcoded sarvam domain
grep -r "sarvam.bizbull.ai" web/dist || echo "OK: no sarvam domain in build"
```

After deploy (VPS):
```bash
curl -s -o /dev/null -w '%{http_code}\n' https://voice.bizbull.ai/         # 200, our app
curl -s https://voice.bizbull.ai/health                                    # token server health
# Open https://voice.bizbull.ai → Start Call → agent answers in Punjabi
```

## Post-Merge: VPS

1. Back up Caddyfile: `cp /etc/caddy/Caddyfile /etc/caddy/Caddyfile.bak.$(date +%F)`
2. Edit `/etc/caddy/Caddyfile`:
   - Replace the `voice.bizbull.ai { reverse_proxy localhost:8090 }` body with our app block:
     ```
     voice.bizbull.ai {
       handle /token* { reverse_proxy localhost:8001 }
       handle /health { reverse_proxy localhost:8001 }
       handle {
         root * /opt/livekit-sarvam/web/dist
         file_server
         try_files {path} /index.html
       }
     }
     ```
   - Remove the entire `sarvam.bizbull.ai { ... }` block.
   - Keep the `www.voice.bizbull.ai` → `voice.bizbull.ai` redirect.
3. Validate + reload:
   ```bash
   caddy validate --config /etc/caddy/Caddyfile
   systemctl reload caddy
   ```
4. Deploy app (rebuilds dist):
   ```bash
   bash /opt/livekit-sarvam/scripts/vps_deploy.sh
   ```
