# PR 020 — Web background ambient audio

## Branch
`pr_020_web-background-ambient`

## What This PR Does

Adds **LiveKit `BackgroundAudioPlayer`** for **web calls only** — a quiet looping ambient track on a separate audio track so Sierra sounds like she’s in a busy environment.

- **Phone:** unchanged (no ambient — echo/STT risk).
- **Web:** ambient starts after `session.start()`, stops on job shutdown.
- **Default:** enabled (`WEB_AMBIENT_ENABLED=1`), volume `0.6`, 1s fade-in.
- **Audio source:** `data/audio/restaurant_ambience.mp3` if present; else LiveKit builtin `OFFICE_AMBIENCE` for testing until you add a custom loop.

## Files Added

### `restaurant/ambient_audio.py`
Web-only player builder + start/stop helpers; env-driven volume and path.

### `data/audio/.gitkeep`
Placeholder for `restaurant_ambience.mp3` (add your own loop — not committed).

### `tests/test_ambient_audio.py`
Config unit tests.

## Files Modified

### `agent.py`
Start/stop web ambient around the agent session; shutdown callback cleans up.

### `docs/vps-config.md`
Web ambient env vars.

### `pr/README.md`
Index PR 020.

## What's NOT in This PR
- Phone ambient (deferred — test web first).
- Custom restaurant MP3 asset (you add `data/audio/restaurant_ambience.mp3` on VPS or set `WEB_AMBIENT_AUDIO_PATH`).
- Thinking/keyboard sounds (opt-in via `WEB_AMBIENT_THINKING=1`).

## Env vars (optional)

```
WEB_AMBIENT_ENABLED=1          # 0 to disable web ambient
WEB_AMBIENT_VOLUME=0.6         # 0.0–1.0
WEB_AMBIENT_FADE_IN=1.0        # seconds
WEB_AMBIENT_AUDIO_PATH=        # override path to mp3/wav
WEB_AMBIENT_THINKING=0         # 1 = keyboard cue during tool/LLM think
```

## How to Test

1. Open `https://voice.bizbull.ai` → Order with Sierra → Start Call.
2. Hear faint background loop behind Sierra (builtin office ambience until custom file added).
3. End call — ambient stops.
4. Call phone `+15878175156` — **no** ambient track.
5. `WEB_AMBIENT_ENABLED=0` → web call with no ambient.

```bash
uv run python -c "from tests.test_ambient_audio import *; test_web_ambient_enabled_default(type('m',(),{'delenv':staticmethod(lambda *a,**k:None),'setenv':staticmethod(lambda *a,**k:None)})()); ..."
# or: uv run python -m pytest tests/test_ambient_audio.py -v
journalctl -u restaurant-agent -f | grep -i ambient
```

## Post-Merge: VPS

```bash
bash /opt/livekit-sarvam/scripts/vps_deploy.sh
# Optional: upload custom loop
# scp restaurant_ambience.mp3 root@89.117.18.192:/opt/livekit-sarvam/data/audio/
systemctl restart restaurant-agent
```
