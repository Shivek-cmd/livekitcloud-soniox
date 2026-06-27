#!/usr/bin/env bash
# Configure VPS git pull via SSH deploy key (run ON the VPS as root).
set -euo pipefail

REPO_DIR="${REPO_DIR:-/opt/livekit-sarvam}"
REPO_URL="${REPO_URL:-git@github.com:Shivek-cmd/livekitcloud-soniox.git}"

cd "$REPO_DIR"

if [[ ! -f /root/.ssh/id_ed25519 ]]; then
  ssh-keygen -t ed25519 -f /root/.ssh/id_ed25519 -N "" -C "vps-livekit-sarvam-deploy"
fi

echo "Add this deploy key to GitHub (repo Settings → Deploy keys → Read-only):"
cat /root/.ssh/id_ed25519.pub
echo

git remote set-url origin "$REPO_URL"

# Use dedicated key for GitHub
mkdir -p /root/.ssh
if ! grep -q 'Host github.com' /root/.ssh/config 2>/dev/null; then
  cat >> /root/.ssh/config <<'EOF'

Host github.com
  IdentityFile /root/.ssh/id_ed25519
  IdentitiesOnly yes
EOF
  chmod 600 /root/.ssh/config
fi

echo "Testing git fetch (after deploy key is added on GitHub)..."
GIT_SSH_COMMAND="ssh -o StrictHostKeyChecking=accept-new" git fetch origin main

echo "OK — git pull will work. Deploy with:"
echo "  cd $REPO_DIR && git pull origin main && systemctl restart restaurant-agent"
