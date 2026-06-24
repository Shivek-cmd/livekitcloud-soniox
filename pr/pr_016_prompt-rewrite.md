# PR 016 — Prompt: complete rewrite — tool-linked flow, ingredients, edge cases

## Branch
`pr_016_prompt-rewrite`

## What This PR Does
Full rewrite of SYSTEM_PROMPT. Every conversational step is now explicitly linked to the
correct tool call at the correct moment. Fixes all 14 issues identified in the prompt audit:
missing quantity step, tools never triggered, spice saved before add_to_order, set_customer_info
called only after both name+phone, get_order_summary called before confirmation, inline
ingredient descriptions, reservation fallback, transfer lines fixed for TTS, NEVER DO tightened.

## Key changes

### agent.py — SYSTEM_PROMPT
- Order flow restructured as STEP A/B/C/D/E — each step names the exact tool to call and when
- Quantity question added (was missing entirely)
- Spice collected BEFORE calling add_to_order so it goes into the note
- Confirmation comes from tool return value, not from LLM memory
- set_customer_info called only after both name AND phone collected
- get_order_summary called before reading the final confirmation
- Inline ingredient descriptions for every dish (replaces get_menu_text() which had no ingredients)
- Reservation unavailability handled: agent offers nearest open slot
- Transfer to human lines written in pure Gurmukhi / pure Hindi (no mixed romanization for TTS)
- NEVER DO list rewritten with actionable guardrails tied to specific tools
- Greeting updated to match session.say() text — no double-greeting

## Files Modified
- `agent.py` — SYSTEM_PROMPT only

## What's NOT in This PR
- Ingredient data is hardcoded in prompt (not in menu.py) — menu.py change is a separate PR
- Restaurant address is a placeholder — fill in the real address before going live
- `get_menu_text()` still exists but is no longer called from the prompt

## How to Test
```bash
# Phone: dial +15878175156 or run test call
uv run python scripts/test_call.py +919413752688

# Test these flows:
# 1. "2 butter chicken" → agent should ask spice, then confirm "2x Butter Chicken medium"
# 2. "paneer tikka" without quantity → agent should ask "How many?"
# 3. Ask "what's in the dal makhani?" → agent should describe ingredients
# 4. Order in Hindi → agent replies in Hindi throughout
# 5. "I want to talk to someone" → immediate transfer
# 6. Unclear twice in a row → auto-transfer
# 7. Delivery order → agent asks address, calls set_delivery_address
```

## Post-Merge: VPS Pull Command
```bash
cd /opt/livekit-sarvam && git pull origin main
systemctl restart restaurant-agent
```
