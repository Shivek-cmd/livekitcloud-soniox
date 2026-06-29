# PR 022 — Phone ambient audio + volume 0.5

## Branch
`pr_022_phone-ambient-audio`

## Status
⬜ **Open** — doc first; implement on this branch.

## What This PR Does

1. **Phone ambient** — same `restaurant_ambience.mp3` loop on **inbound phone calls** (Twilio SIP), using LiveKit `BackgroundAudioPlayer` (same mechanism as web PR 020).
2. **Web volume tune** — default `WEB_AMBIENT_VOLUME` **0.6 → 0.5** (still overridable in `.env`).
3. **Refactor** — one shared ambient builder for web + phone; separate on/off and volume per channel.

PR 020 deferred phone because of echo/STT risk. This PR enables phone with **lower default volume**, separate kill-switch, and live-call verification on inbound CA number.

## Design

### Same sound, two channels

| Setting | Web default | Phone default |
|---------|-------------|---------------|
| Enabled | `WEB_AMBIENT_ENABLED=1` | `PHONE_AMBIENT_ENABLED=1` |
| Volume | `WEB_AMBIENT_VOLUME=0.5` | `PHONE_AMBIENT_VOLUME=0.35` |
| Fade-in | `WEB_AMBIENT_FADE_IN=1.0` | `PHONE_AMBIENT_FADE_IN=1.0` |
| Audio file | `data/audio/restaurant_ambience.mp3` (shared) | same |

Phone volume defaults **lower than web** — PSTN compression and echo risk. Tune after live tests.

Shared optional override: `AMBIENT_AUDIO_PATH` (fallback: existing `WEB_AMBIENT_AUDIO_PATH`, then default mp3 path).

### Code changes (planned)

#### `restaurant/ambient_audio.py`
- Rename module docstring: web + phone ambient (not web-only).
- `build_ambient_player(*, is_phone: bool) -> BackgroundAudioPlayer | None` — shared mp3 path + channel env.
- Keep `build_web_ambient_player()` as thin wrapper for tests (optional).
- `phone_ambient_enabled()`, `web_ambient_enabled()` — separate toggles.
- `_DEFAULT_VOLUME = 0.5` for web; `_DEFAULT_PHONE_VOLUME = 0.35`.

#### `agent.py`
- Remove `if not is_phone:` gate around ambient start.
- Always attempt ambient when channel toggle is on:
  ```python
  background_audio = build_ambient_player(is_phone=is_phone)
  if background_audio is not None:
      await start_ambient(...)
  ```
- Log channel in ambient lines: `Web ambient started` / `Phone ambient started`.

#### `tests/test_ambient_audio.py`
- Phone enabled/disabled defaults.
- Phone uses lower default volume env.
- Web default volume 0.5.

#### `docs/vps-config.md`
- Document `PHONE_AMBIENT_*` env vars.
- Update web volume example to `0.5`.

## Files Modified (when implemented)

- `restaurant/ambient_audio.py`
- `agent.py`
- `tests/test_ambient_audio.py`
- `docs/vps-config.md`
- `pr/README.md`

## What's NOT in This PR

- Different audio file for phone vs web (same mp3 only).
- Thinking/keyboard sounds on phone.
- Echo-filter changes (monitor only; follow-up PR if `phone_echo.py` false positives increase).
- Outbound test-call tuning (India PSTN has more echo — validate on **inbound** `+15878175156`).

## Risks & mitigation

| Risk | Mitigation |
|------|------------|
| STT picks up ambient as user speech | Lower `PHONE_AMBIENT_VOLUME`; disable with `PHONE_AMBIENT_ENABLED=0` |
| Echo / barge-in loop | Krisp NC on trunk; test inbound CA; rollback env flag |
| Caller can't hear ambient on PSTN | LiveKit mixes agent published tracks — verify on real call; may need volume bump |

## How to Test

1. **Web regression** — `voice.bizbull.ai` → Start Call → hear loop at ~0.5 volume; logs `Web ambient ready`.
2. **Phone** — call `+15878175156` → faint restaurant loop behind Sierra; logs `Phone ambient ready`.
3. **Disable phone only** — `PHONE_AMBIENT_ENABLED=0` → web still on, phone silent ambient.
4. **Disable all** — both flags `0` → no ambient either channel.

```bash
uv run python -m pytest tests/test_ambient_audio.py -v
journalctl -u restaurant-agent -f | grep -i ambient
```

## Env vars (VPS `.env`)

```
WEB_AMBIENT_ENABLED=1
WEB_AMBIENT_VOLUME=0.5
WEB_AMBIENT_FADE_IN=1.0

PHONE_AMBIENT_ENABLED=1
PHONE_AMBIENT_VOLUME=0.35
PHONE_AMBIENT_FADE_IN=1.0

# Optional shared path (else data/audio/restaurant_ambience.mp3)
# AMBIENT_AUDIO_PATH=/opt/livekit-sarvam/data/audio/restaurant_ambience.mp3
```

Restart after change: `systemctl restart restaurant-agent`

## Post-Merge: VPS

```bash
bash /opt/livekit-sarvam/scripts/vps_deploy.sh
```

Then test inbound phone + web. If echo worsens, set `PHONE_AMBIENT_ENABLED=0` without redeploy.

## Verification checklist

- [ ] Web: custom mp3, volume ~0.5
- [ ] Phone inbound: same mp3 audible (subtle)
- [ ] `PHONE_AMBIENT_ENABLED=0` turns off phone only
- [ ] No new echo reprompt loops in `journalctl` (5+ min test call)
- [ ] Order flow still completes (add item → place order log)
