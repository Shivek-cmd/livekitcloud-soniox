# PR 023 — Phone background speech hardening

## Branch
`pr_023_phone-background-speech`

## Status
✅ **Merged** — GitHub PR #52–53 → `main` (2026-06-29).

## What This PR Does

Production fix when **background voices, TV, or music** near the caller steal Sierra's attention on phone:

1. **Krisp BVC telephony** — `livekit-plugins-noise-cancellation`; SIP callers get `BVCTelephony()`, web gets `BVC()`. Env: `PHONE_BVC_ENABLED=1` (default).
2. **Stricter phone interruptions** — `min_words=2`, `min_duration=0.55s` so brief background blips don't barge-in (web unchanged).
3. **Transcript filter** — `restaurant/phone_background.py` drops low-signal GENERAL/UNCLEAR turns; after 3 drops, one reprompt: *"Sorry, I didn't catch that — could you repeat please?"*
4. **SIP trunk Krisp** — `setup_sip.py` defaults `KRISP_ENABLED=1` when creating trunk.

**Revert without code rollback:** set `PHONE_BVC_ENABLED=0` and `PHONE_BACKGROUND_FILTER_ENABLED=0` in `.env`, restart agent.

## Files Added

### `restaurant/phone_background.py`
Heuristic filter for background chatter (not agent echo — that stays in `phone_echo.py`).

### `tests/test_phone_background.py`
Unit tests for filter bypass/drop cases.

## Files Modified

### `pyproject.toml` / `uv.lock`
Add `livekit-plugins-noise-cancellation`.

### `restaurant/session_config.py`
`build_room_options()` with BVC selector; phone-specific interruption defaults; `phone_bvc_enabled()`, `phone_background_filter_enabled()`.

### `agent.py`
Wire BVC room options, background filter in `on_user_turn_completed`, one-shot background reprompt.

### `restaurant/conversation.py`
`background_repeat_phrase()`.

### `scripts/setup_sip.py`
Default `KRISP_ENABLED=1`.

### `docs/vps-config.md`
PR 023 env vars and revert instructions.

## What's NOT in This PR

- Soniox speaker diarization
- Noisy-call transfer to human
- Web turn-tuning changes (web keeps prior interruption settings)
- Prompt-only "ignore background" (transcript filter + BVC instead)

## Env vars (VPS `.env`)

```
PHONE_BVC_ENABLED=1
PHONE_BACKGROUND_FILTER_ENABLED=1
PHONE_INTERRUPTION_MIN_WORDS=2
PHONE_INTERRUPTION_MIN_DURATION=0.55
```

## How to Test

1. Deploy → restart `restaurant-agent`.
2. **Inbound** call `+15878175156` (preferred over outbound India).
3. Normal order with quiet line — no regression on pickup, add item, read-back.
4. Play TV/music near mic — Sierra should ignore fragments or ask repeat once, not take wrong order.
5. Logs:
   ```bash
   journalctl -u restaurant-agent -f | grep -iE 'BVC|background|Ignoring phone'
   ```

```bash
uv run python -m pytest tests/test_phone_background.py tests/test_phone_echo.py -v
```

## Post-Merge: VPS

```bash
bash /opt/livekit-sarvam/scripts/vps_deploy.sh
```

If audio breaks: `PHONE_BVC_ENABLED=0` + `PHONE_BACKGROUND_FILTER_ENABLED=0` → `systemctl restart restaurant-agent`.

## Verification checklist

- [ ] Logs show `BVC telephony selected for SIP participant` on phone call
- [ ] Real pickup/order still works (not dropped as background)
- [ ] Background "thank you" / "mm hmm" not acted on as order
- [ ] After 3 dropped noise turns → one repeat prompt max
- [ ] Web call still works (BVC for WebRTC if enabled)

## Follow-up (same branch)

- Shared phone + web endpointing default **`PHONE_ENDPOINTING_MAX=0.5`**, **`PHONE_ENDPOINTING_MIN=0.2`** (was 0.8s phone / 2.0s web).
