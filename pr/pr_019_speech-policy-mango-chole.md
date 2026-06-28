# PR 019 — Speech policy: Mango drinks + Chole/Bhature

## Branch
`pr_019_speech-policy-mango-chole`

## Status
✅ **Merged** — GitHub PR #44 → `main` at `2bf30d2` (2026-06-29).

## What This PR Does

Fixes five menu item TTS pronunciations in `speech_policy.py` and regenerates `data/clover_voice_labels.json`:

| Item | Was | Now |
|------|-----|-----|
| Mango Shake | Gurmukhi `ਅੰਬ ਸ਼ੇਕ` (TTS: "Amb Shake") | English **Mango Shake** |
| Mango Lassi | Gurmukhi `ਅੰਬ ਲੱਸੀ` (TTS: "Amb Lassi") | English **Mango Lassi** |
| Chole | English `Chole` | Gurmukhi **ਛੋਲੇ** |
| Bhatura (single) | English `Bhatura` | Gurmukhi **ਭਟੂਰਾ** |
| Chole Bhature Combo | English `Chole Bhature Combo` | Gurmukhi **ਛੋਲੇ ਭਟੂਰੇ ਕੰਬੋ** |

### `tests/test_speech_policy.py`
- Unit tests for the five voice_line changes.

## Files Modified

### `restaurant/clover/speech_policy.py`
- Add `mango_shake`, `mango_lassi` to `ENGLISH_VOICE_KEYS` + overrides.
- Remove `chole`, `bhatura_single`, `chole_bhature_combo` from English overrides (default Gurmukhi via `speak_as`).

### `data/clover_voice_labels.json`
- Rebuilt via `scripts/rebuild_voice_labels.py` (5 items updated).

## What's NOT in This PR
- Other menu speech audit items (naan, biryani, combos, etc.).
- Availability-turn guidance fix (separate follow-up if needed).

## How to Test

```bash
uv run python scripts/rebuild_voice_labels.py --dry-run
uv run pytest tests/test_speech_policy.py -v
# Phone/web: ask for mango shake, mango lassi, chole bhature — verify TTS names
```

## Post-Merge: VPS

```bash
bash /opt/livekit-sarvam/scripts/vps_deploy.sh
```
