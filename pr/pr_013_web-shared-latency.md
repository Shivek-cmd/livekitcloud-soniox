# PR 013 — Web: shared turn latency with phone (0.8s max endpointing)

## Branch
`pr_013_web-shared-latency`

## What This PR Does

Web calls felt slow to respond because web used a separate, looser turn-handling
profile (`max_delay: 2.0s`, full TurnDetector, softer interruption rules). Phone
already uses Tier A tuning (`max_delay: 0.8s`, `v1-mini`, preemptive TTS).

This PR removes the web-only profile and uses the **same `_turn_handling()`**
for both channels. Web should now commit turns and reply at the same speed as
phone. Phone-only echo handling (AEC warmup, greeting settle) is unchanged.

## Files Modified
### `restaurant/session_config.py`
- Renamed `_phone_turn_handling()` → `_turn_handling()` (shared).
- Removed `_web_turn_handling()` (was `max_delay: 2.0`).
- `build_agent_session()` always uses `_turn_handling()`; STT/TTS still
  differ by channel via `build_stt(is_phone)` / `build_tts(is_phone)`.
### `restaurant/clover/speech_policy.py`
- Added **`kulfi`** to English voice overrides — TTS says **"Mango Kulfi"** not Gurmukhi "amb kulfi".
### `data/clover_voice_labels.json`
- Rebuilt (`voice_line: "Mango Kulfi"`, `speech_mode: english` for kulfi).
### `web/package-lock.json`
- Lockfile added (from W2 `@livekit/components-react` deps).

## What's NOT in This PR
- W3 (menu highlight, modifier picker, tap-add ack).
- New env vars — web now reads the existing `PHONE_ENDPOINTING_*` knobs on the VPS.

## How to Test
```bash
# On voice.bizbull.ai after deploy:
# - Start a web call, say a short order line, stop talking
# - Sierra should reply noticeably faster (≤~0.8s silence vs old ~2s cap)
# - Phone behavior should be unchanged
```

## Post-Merge: VPS (you deploy)
Agent-only change — no Caddy or frontend rebuild required:
```bash
ssh root@89.117.18.192
bash /opt/livekit-sarvam/scripts/vps_deploy.sh
systemctl is-active restaurant-agent
```
