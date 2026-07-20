# PR 085 — Gap 6: grounded `get_recommendations` tool

## Branch
`pr_085_get-recommendations`

## What This PR Does
Closes **Gap 6**: the LLM has zero menu content in context — real dishes only
enter via tool calls — so a caller asking "what's good?" could be answered from
the model's imagination. This PR adds a dedicated `get_recommendations` tool the
LLM must call for suggestions; it returns real menu items with veg/non-veg tags.
Recommendations may ONLY come from tool results, never memory (PR-030 lesson).

## Files Modified
### `restaurant/menu_provider.py`
- `recommendation_options(preference, category, *, limit=4) -> list[dict]`
  (`name`, `voice_line`, `veg`): filters `available`; preference ∈ {veg, non-veg,
  any} (normalizes "vegetarian"/"non veg"/…); optional category via
  `resolve_browse_target` + `category_name` substring fallback; deterministic
  selection (preference's mains category first, then Tandoor & Grill, Combos,
  Starters, rest; cache order within category). Static-menu fallback.
- `_format_recommendations_tool_result`: `Name → say "voice_line" (veg|non-veg)`
  lines + "suggest at most TWO in ONE casual sentence …"; empty → "No matching
  items — offer to search the menu instead." Module `get_recommendations()` wraps
  options+formatter (same shape as `search_menu`/`browse_menu`).

### `restaurant/agent/core.py`
- `@function_tool get_recommendations(preference="any", category="")` — thin
  recorded pass-through; `_record_tool` + `recommendations_empty` recorder event.

### `restaurant/agent/prompt.py` + `restaurant/agent/persona.py`
- `_tool_contract` line for the tool; extends the NEVER rule ("recommend dishes
  without get_recommendations/search_menu"); mirrored in legacy. Undecided persona
  example gets `[tools: get_recommendations(preference="any") first …]`.

## Tests
- New `tests/test_recommendations.py` (15): veg preference excludes `veg=False`
  and vice versa; availability filtering; category filter; limit honored; formatter
  contains "at most TWO" + veg tags; static fallback.
- `tests/test_agent_tools.py` (+2): agent-level tool returns formatted string +
  `recommendations_empty` event. `tests/test_prompt.py` (+2 non-negotiables).
- Full suite: **425 passed**. Live-repro (`USE_CLOVER_MENU=1`):
  `get_recommendations("non-veg")` → Butter Prawn Masala + Lamb Biryani spoken,
  Chicken Biryani + Punjabi Fish Curry as extras; `("veg","starters")` → 4 veg
  starters; unknown category → "No matching items …".

## Deviations from Plan
- Formatter tail carries the extras' full `Name → say "voice_line" (tag)` lines
  (not just a bare `+N more`) — returning 4 items is only useful if the LLM can
  speak the extras without another tool call; spoken-limit 2 lines come first.
- Category filter uses bidirectional substring on normalized names so the resolved
  Clover name ("Starters & Snacks") also matches static short keys ("starters");
  FAMILY targets fall through to the plain substring fallback.
- "any" preference priority = Vegetarian Mains, then Non-Veg Mains, then the shared tail.

## Notes
Last of the gap-fix batch, lowest risk. Live-verify ("what's good?" → tool call in
log before the suggestion turn; every suggested name in the cache) deferred to the
post-all-steps live call.

## How to Test
```
PYTHONPATH=. uv run --with pytest pytest tests -q
```
