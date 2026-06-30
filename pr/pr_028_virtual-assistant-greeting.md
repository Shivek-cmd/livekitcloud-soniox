# PR 028 — Virtual assistant opening greeting

## Status
✅ **Merged to `main`** — PR #61

## Branch
`pr_028_virtual-assistant-greeting`

## What This PR Does
Updates the phone + web opening greeting to introduce Sierra as a **virtual assistant** (no restaurant name in the intro). Keeps trilingual capability and a short line for low phone echo risk.

**New greeting:**
> Hi! I'm Sierra, your virtual assistant. I speak English, Hindi, and Punjabi. How can I help you?

## Files Modified

### `restaurant/conversation.py`
- `OPENING_GREETING` — new copy

### `restaurant/phone_echo.py`
- Greeting tail echo phrases for new intro (`virtual assistant`, etc.)

### `tests/test_language.py`
- Assert new greeting strings

### `docs/HANDOFF.md`
- Greeting quote sync

## Test Plan
- [ ] `uv run pytest tests/test_language.py -q`
- [ ] Web: open `voice.bizbull.ai` — hear new greeting
- [ ] Phone: inbound call — greeting plays, no echo dead-air after hang-up greeting
