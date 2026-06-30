# PR 024 — Natural concise confirmations + multi-item adds

## Branch
`pr_024_natural-concise-multi-item`

## Status
✅ **Merged** — GitHub PR #54–55 → `main` (2026-06-29).

## What This PR Does

Fixes two live-call issues when a caller says e.g. *"add one rasmalai and one kheer"*:

1. **Human confirmations** — Sierra confirms like a cashier (*"Yes — one Rasmalai and one Kheer. Anything else?"*), not *"I can add… six ninety-nine… two pieces… what is the second item?"*
2. **Multi-item same turn** — parses `"one X and one Y"`, adds both items in code when safe (no required modifiers), speaks once.

Also in this PR:

3. **Web ambient quieter** — default `WEB_AMBIENT_VOLUME` `0.4` → **`0.2`**.
4. **Soft drink TTS** — `speak_as` / `voice_line` `ਸੋਫਟ ਪੀਅ` → **`ਸਾਫਟ ਡਰਿੰਕ`**.

(Post-merge: phone ambient lowered to **0.2** in PR 025.)

## Files Added

### `restaurant/order_parse.py`
Splits utterances on `and` / `aur` / `te` / comma; extracts qty + menu match per segment. `can_auto_add_lines()` gates the fast-path (2+ items, no required modifiers).

### `tests/test_order_parse.py`
Unit tests for multi-item parsing and confirmation templates.

## Files Modified

### `restaurant/conversation.py`
- `confirm_items_added()` — cashier-style confirm by language
- `format_add_tool_reply()` — `SAY EXACTLY:` tool returns (no cart/menu language)

### `restaurant/orders.py`
- `add_item()` / `remove_item()` use concise tool replies

### `restaurant/order_flow.py`
- ADD_ITEM guidance: multi-item list + `SAY EXACTLY`; ban check-before-add on clear adds

### `restaurant/prompts.py`
- Ban cart/menu/"I can add"/portion counts on unprompted adds; phone no price on add

### `agent.py`
- Auto-add fast-path for 2+ parsed items (phone + web)
- `bind_session()` for direct confirm speech
- `add_to_order` docstring: add directly when name is clear

### `restaurant/conversation.py` (`sanitize_assistant_speech`)
- Strip mid-call "I can add" / "added to cart" slips

### `restaurant/ambient_audio.py`
- Web default volume `0.4` → `0.2`

### `docs/vps-config.md`
- Document `WEB_AMBIENT_VOLUME=0.2`

### `restaurant/clover/seed_menu.py` + `data/clover_voice_labels.json`
- Soft drink Gurmukhi label: `ਸਾਫਟ ਡਰਿੰਕ`

## What's NOT in This PR
- 4+ item complex orders with per-item modifiers
- Clover order submit (Phase 8c)
- Full menu search rewrite (B-2)

## How to Test

```bash
uv run pytest tests/test_order_parse.py tests/test_conversation.py -v
# Phone/web: "add one gulab jamun and one kheer" → both in cart, one short confirm, no price
```

## Post-Merge: VPS

```bash
bash /opt/livekit-sarvam/scripts/vps_deploy.sh
```
