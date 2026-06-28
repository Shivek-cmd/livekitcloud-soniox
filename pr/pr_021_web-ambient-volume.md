# PR 021 — Web ambient volume 0.6

## Branch
`pr_021_web-ambient-volume`

## What This PR Does
Raises default web background ambient volume from `0.25` to **`0.6`** (`restaurant/ambient_audio.py`). Still overridable via `WEB_AMBIENT_VOLUME` in `.env`.

## Post-Merge: VPS
```bash
bash /opt/livekit-sarvam/scripts/vps_deploy.sh
```
