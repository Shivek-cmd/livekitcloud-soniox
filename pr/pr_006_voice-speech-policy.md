# PR 006 — Voice speech policy (Option B)

Production speech layer for natural Canadian Punjabi-English restaurant calls.

## Problem

Sierra was forced to speak every dish in full Gurmukhi (`speak_as`), which sounded unnatural and
sometimes wrong on phone calls (e.g. Fish Pakora → machhi/ਮੱਛੀ, Chole Bhature → full Gurmukhi
instead of the English name customers actually use).

## Solution

Central **speech policy** — not prompt-only tape:

| Field | Purpose |
|-------|---------|
| `voice_line` | Exact text Sierra says for the dish name |
| `speech_mode` | `english` \| `mixed` \| `gurmukhi` — hints for sentence wrapping |
| `speak_as` | Kept for STT aliases / legacy; not default TTS output |

### Category rules (defaults)

- **Combos, tandoor, non-veg mains** → English menu names
- **Fish/meat starters** → English (Fish Pakora, Chicken Tikka)
- **Veg mains, veg starters, drinks** → mixed (English dish name in Punjabi sentence)
- **Traditional desserts** (Gulab Jamun, Kheer, etc.) → Gurmukhi
- **Modifiers / spice** → always English

### Key overrides

- `fish_pakora` → "Fish Pakora"
- `chole_bhature_combo` → "Chole Bhature Combo"

## Files

| File | Change |
|------|--------|
| `restaurant/clover/speech_policy.py` | Policy engine |
| `restaurant/clover/voice_labels.py` | Build/merge label entries |
| `restaurant/clover/models.py` | `voice_line`, `speech_mode` on cache types |
| `restaurant/clover/menu.py` | Sync/load/save/search |
| `restaurant/menu_provider.py` | Tool output uses `voice_line` |
| `restaurant/orders.py` | Cart summary uses `voice_line` |
| `agent.py` | Natural voice prompt section |
| `scripts/rebuild_voice_labels.py` | Re-apply policy to existing JSON |
| `data/clover_voice_labels.json` | Regenerated with new fields |

## Deploy (VPS)

```bash
cd /opt/livekit-sarvam
git pull
python scripts/rebuild_voice_labels.py   # if JSON not yet updated on branch
python scripts/clover_sync_menu.py
sudo systemctl restart restaurant-agent
```

## Test plan

- [ ] Call and order **Fish Pakora** — Sierra says "Fish Pakora", not machhi
- [ ] Order **Chole Bhature Combo** — English name in natural Punjabi sentence
- [ ] **Gulab Jamun** / **Kheer** — Gurmukhi voice_line still works
- [ ] Phone readback — English digits only
- [ ] Spice/modifiers — mild, medium, spicy in English
- [ ] `get_order_summary` — voice_line names in cart readback
