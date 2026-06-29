# PR 021 — Web ambient volume 0.6 + custom restaurant loop

## Branch
`pr_021_web-ambient-volume`

## Status
✅ Volume **0.6** merged to `main` (GitHub PR #46–#47).  
⬜ **Follow-up on this branch:** commit `data/audio/restaurant_ambience.mp3` so deploy pulls custom loop (no manual SCP).

## What This PR Does

1. **Volume (merged)** — default web ambient volume `0.25` → **`0.6`** in `restaurant/ambient_audio.py` (override via `WEB_AMBIENT_VOLUME`).
2. **Custom loop (this commit)** — ships `data/audio/restaurant_ambience.mp3` (~4.7 MB). Web sessions use this file instead of LiveKit builtin `OFFICE_AMBIENCE`. Phone unchanged.

## Files Added

### `data/audio/restaurant_ambience.mp3`
Custom seamless restaurant ambience loop. Loaded automatically at repo path `data/audio/restaurant_ambience.mp3` (or `WEB_AMBIENT_AUDIO_PATH`).

## Files Modified

### `restaurant/ambient_audio.py` (already on `main`)
Default volume `0.6`.

## What's NOT in This PR
- Phone ambient (still web-only).
- `WEB_AMBIENT_THINKING` keyboard cue (opt-in, unchanged).

## Env vars (optional)

```
WEB_AMBIENT_ENABLED=1
WEB_AMBIENT_VOLUME=0.6
WEB_AMBIENT_FADE_IN=1.0
# WEB_AMBIENT_AUDIO_PATH=   # only if overriding default path
```

## How to Test

1. Deploy or run agent locally with the mp3 present under `data/audio/`.
2. Open `https://voice.bizbull.ai` → Order with Sierra → Start Call.
3. Hear custom restaurant loop (not generic office hum).
4. Logs: `journalctl -u restaurant-agent -f | grep -i ambient` → `source=restaurant_ambience.mp3`.
5. Phone `+15878175156` — still no ambient.

```bash
uv run python -m pytest tests/test_ambient_audio.py -v
```

## Post-Merge: VPS

```bash
bash /opt/livekit-sarvam/scripts/vps_deploy.sh
# Pulls restaurant_ambience.mp3 from git — no manual scp needed
systemctl restart restaurant-agent   # if deploy script did not restart agent
journalctl -u restaurant-agent -n 20 | grep -i ambient
```
