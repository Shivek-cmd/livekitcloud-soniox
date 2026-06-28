#!/usr/bin/env bash
# Pull latest main on VPS and restart services. Run ON the VPS after setup_vps_git.sh.
set -euo pipefail

REPO_DIR="${REPO_DIR:-/opt/livekit-sarvam}"
UV="${UV:-/root/.local/bin/uv}"

cd "$REPO_DIR"
git fetch origin main
git checkout main
git reset --hard origin/main

"$UV" sync
PYTHONPATH="$REPO_DIR" "$UV" run python scripts/rebuild_voice_labels.py
PYTHONPATH="$REPO_DIR" "$UV" run python scripts/clover_sync_menu.py

# Rebuild the web frontend (served by Caddy from web/dist; not tracked in git)
if [ -f "$REPO_DIR/web/package.json" ]; then
  (cd "$REPO_DIR/web" && npm install && npm run build)
fi

systemctl restart restaurant-agent restaurant-token
systemctl is-active restaurant-agent restaurant-token

echo "Deployed $(git rev-parse --short HEAD)"
