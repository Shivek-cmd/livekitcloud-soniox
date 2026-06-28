# PR 015 — Production conversation layer (Tier B + W6)

## Branch
`pr_015_conversation-production`

## What This PR Does

Production-grade conversation handling so Sierra feels like two humans talking, not a
fragile prompt-only bot. Implements Tier B **B-3–B-7**, **B-9**, and web **W6** in one
cohesive layer:

1. **B-9 — Shortened system prompt** — static persona/tools in `restaurant/prompts.py`;
   long order-flow Steps A–E removed from the prompt (moved to code).
2. **B-3/B-4 — Order flow in code** — `restaurant/order_flow.py` tracks phase from cart +
   caller signals; injects per-turn `[TURN GUIDANCE]` so the LLM asks one sensible question.
3. **B-5/B-6/B-7 — Templates & guards** — `restaurant/conversation.py` detects intent
   (price / availability / add), supplies price/spice/recovery templates, blocks mid-call
   re-greetings in assistant output.
4. **W6 — Web prompt variant** — channel-aware prompt: prices on screen, tap-add awareness,
   "as you can see on your order panel" language.

Also: phone echo recovery after any dropped turn (extends B-6) so reprompt lines don't
cause dead air.

## Files Added

### `restaurant/prompts.py`
Compact phone + web system prompts (`build_system_prompt(is_phone=…)`).

### `restaurant/conversation.py`
Intent detection, price/spice/recovery templates, assistant speech sanitization.

### `restaurant/order_flow.py`
Order phase state machine + `build_turn_guidance()` for per-turn system injection.

### `tests/test_conversation.py`
Unit tests for intent detection, phase logic, price templates, re-greet guard.

## Files Modified

### `agent.py`
- Uses `build_system_prompt()` instead of inline 280-line prompt.
- `OrderFlowController` + per-turn guidance via `turn_ctx.add_message(role="system", …)`.
- Tool hooks update flow state; `check_menu_item` records last discussed item.
- Sanitize assistant speech on `conversation_item_added` (B-6).
- Echo recovery reprompt after any ignored echo turn (not only greeting tail).

### `restaurant/menu_provider.py`
- `item_has_spice_level()`, `resolve_item_in_text()` for template/guard helpers.

### `docs/plan/10-voice-quality-tier-b.md`
Mark B-3–B-7, B-9 as in progress / partial via PR 015.

### `pr/README.md`
Index PR 015.

## What's NOT in This PR
- B-1 full echo filter rewrite (separate follow-up if needed after live testing).
- B-2 menu search category aliases.
- B-8/B-10 performance (prompt already shorter via B-9).
- W3 menu highlight, 8c Clover submit.

## How to Test

```bash
# Unit tests
uv run pytest tests/test_conversation.py -v

# Web: voice.bizbull.ai — order by voice; Sierra should reference screen/prices freely
# Phone: call +15878175156
#   - Ask "do you have gajar halwa?" → yes/no only, NO quantity yet
#   - Ask price → "That's about X dollars ji." one line only
#   - After echo/reprompt → should recover, not dead air
journalctl -u restaurant-agent -f | grep -E 'USER:|SIERRA:|TURN_GUIDANCE|Ignoring'
```

## Post-Merge: VPS

```bash
bash /opt/livekit-sarvam/scripts/vps_deploy.sh
systemctl restart restaurant-agent
```
