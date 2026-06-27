# PR 006 — Voice speech policy + phone call quality

Production speech layer for natural Canadian Punjabi-English restaurant calls, plus phone echo and prompt fixes.

## Problem

1. Sierra forced every dish into full Gurmukhi (`speak_as`) — unnatural on Canadian calls (Fish Pakora → machhi).
2. Unprompted prices and Punjabi spice questions ("mirchi kithe tak").
3. Outbound/mobile calls: greeting echo caused dead air (STT heard Sierra's own TTS).

## Solution

### Speech policy (Option B)

| Field | Purpose |
|-------|---------|
| `voice_line` | Exact text Sierra says for the dish name |
| `speech_mode` | `english` \| `mixed` \| `gurmukhi` |
| `speak_as` | STT aliases only — not default TTS |

### Phone echo recovery

- Greeting tail echo detection (`Help you today`, etc.)
- Reprompt: "ਹਾਂ ਜੀ — go ahead, I'm listening."
- No blanket STT mute; tuned endpointing + false-interruption recovery

### Price / spice rules

- Price in tool output marked INTERNAL — only say if customer asks or Step E total
- Spice: English only — "Mild, medium, or spicy?"

## Files

| File | Change |
|------|--------|
| `restaurant/clover/speech_policy.py` | Policy engine |
| `restaurant/clover/voice_labels.py` | Build/merge label entries |
| `restaurant/clover/models.py` | `voice_line`, internal price in describe() |
| `restaurant/clover/menu.py` | Sync/load/save/search |
| `restaurant/menu_provider.py` | Tool output, no prices in search |
| `restaurant/orders.py` | `voice_line` cart; no price in add_to_order return |
| `restaurant/phone_echo.py` | Greeting tail + echo detection |
| `agent.py` | Natural voice, price/spice rules, phone session tuning |
| `scripts/rebuild_voice_labels.py` | Re-apply policy to JSON |
| `data/clover_voice_labels.json` | Regenerated |

## Deploy (VPS)

```bash
cd /opt/livekit-sarvam
git pull origin main
PYTHONPATH=/opt/livekit-sarvam uv run python scripts/rebuild_voice_labels.py
PYTHONPATH=/opt/livekit-sarvam uv run python scripts/clover_sync_menu.py
systemctl restart restaurant-agent
```

## Test plan

- [ ] Fish Pakora — says "Fish Pakora", not machhi
- [ ] Chole Bhature Combo — English name in Punjabi sentence
- [ ] Gulab Jamun / Kheer — Gurmukhi voice_line OK
- [ ] No price until customer asks
- [ ] Spice — "Mild, medium, or spicy?" in English
- [ ] Phone: greeting → brief pause → responds after you speak (earpiece)
- [ ] Phone digits read back in English at Step D
