# PR 005 — Clover-aware prompt + phone echo fix

> **Note (2026-06-27):** Phone `AgentSession` tuning from this PR (1s endpointing, no preemptive,
> STT-only, no barge-in) was **superseded by PR 008** (`restaurant/session_config.py`).
> Echo filter (`phone_echo.py`) and prompt menu-tool rules remain active.

## Branch
`pr_005_clover-prompt-and-phone-echo`

## What This PR Does

1. **Rewrites Sierra system prompt** for Clover menu integration (Phase 8b).
2. **Phone echo fix** — filter STT loops on outbound/mobile test calls.

### Prompt changes
- Removes static 20-item menu list from prompt (was conflicting with Clover 61-item cache).
- Adds **MENU TOOLS** section: tool-first rules, speak_as, combos, modifiers, spicy queries.
- Rewrites **Step A** — per-item modifiers from `check_menu_item`, not category-based spice rules.
- Step E totals labeled as estimates until Phase 8c Clover checkout.
- Uses `RESTAURANT_NAME_EN`, `RESTAURANT_NAME`, `OPENING_HOURS` from config.

### Phone echo fix
- `restaurant/phone_echo.py` — detect acoustic echo of agent TTS as user speech.
- `on_user_turn_completed` raises `StopResponse` for echo turns on phone channel.
- Phone session: no barge-in, AEC warmup, slower endpointing, post-greeting pause.

## Files Changed

### `agent.py`
Prompt rewrite + phone echo integration + phone `AgentSession` tuning.

### `restaurant/phone_echo.py` (new)
Echo detection helper.

## What's NOT in This PR
- Phase 8c — Clover order submit
- Soniox STT context with menu aliases

## How to Test

```bash
USE_CLOVER_MENU=1 python agent.py dev   # web
python scripts/test_call.py +91XXXXXXXXXX   # phone — use earpiece

# On call, verify:
# - "What paneer dishes?" → search_menu_items, Gurmukhi speak_as names
# - Order combo → asks for required modifier choices
# - No self-talk echo loop on phone
```

## Post-Merge: VPS
```bash
cd /opt/livekit-sarvam && git pull origin main
systemctl restart restaurant-agent
```
