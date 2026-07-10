# PR 060 — Salvage and Decouple (hybrid rebuild, stage 1 of 4)

## Branch
`pr_060_salvage-and-decouple`

## What This PR Does
First stage of the conversation-architecture rebuild planned in `refactor.md`
("LLM talks, code owns the cart"). Zero behavior change for the deployed agent.
Salvages the hard-won pieces of `restaurant/conversation.py` (greeting/language
detection, tool-reply formatters, readback templates, speech sanitizer) into the
new `restaurant/agent/` package, and severs every import that other keeper
modules have into `conversation.py` / `order_parse.py`, so those files can be
deleted at cutover (PR 062). Also adds the cart `revision` counter and the new
`gates.py` (place-order blockers + readback-staleness state) that the new brain
(PR 061) builds on, and deletes the env-gated-off fillers feature.

Note: the plan in `refactor.md` numbered these PRs 059–062, but 059 was taken
by the web-UI theme PR (#96). The rebuild stages are therefore 060–063.

## Files Added
### `restaurant/agent/__init__.py`
Package marker for the new agent brain.

### `restaurant/agent/language.py`
Moved verbatim from `conversation.py`: `OPENING_GREETING`, `CustomerLanguage`,
`detect_customer_language`, `update_preferred_language`.

### `restaurant/agent/replies.py`
Moved verbatim from `conversation.py`: `confirm_items_added`,
`format_add_tool_reply`, `format_remove_tool_reply`, `format_update_tool_reply`,
`_cart_items_str`, `format_order_status`, `format_order_readback`,
`order_placed_goodbye`, `recovery_phrase`, `sanitize_assistant_speech` (with its
guard regexes), plus the private helpers they need (`_qty_word`,
`_format_dollars`, `CONFIRM_CLOSE`).

### `restaurant/agent/gates.py`
New (per plan §2.1): `SPICE_GROUP` ("Spice Level" magic string defined once),
`OrderSessionState` (allergies flag, readback revision/confirmed, sticky
language), `place_order_blockers(cart, state)` pure gate function, and
`invalidate_readback(state)`. Pure and LLM-free; not yet wired to anything.

### `tests/test_agent_gates.py`
Blocker matrix (each precondition individually missing), readback-staleness
flow (mutation after readback forces re-confirm), and revision bumps on every
cart mutation path including the by-id web-RPC paths.

## Files Modified
### `restaurant/conversation.py`
The moved names are re-imported from `restaurant.agent.language` /
`restaurant.agent.replies` as aliases — every existing importer (deployed
`agent.py`, `order_flow.py`, engine, tests) sees identical names and behavior.

### `restaurant/orders.py`
Formatter imports now top-level from `restaurant.agent.replies` (were lazy
imports from `conversation`); `customer_info` import made top-level; new
`revision: int` counter on `OrderCart`, bumped by every mutating method
(`add_item`, `remove_item`, `update_item_quantity`, `set_quantity_by_id`,
`remove_by_id`) so web-RPC mutations invalidate a spoken readback for free.

### `restaurant/customer_info.py`
All three lazy circular imports into `conversation` severed: private copies of
the pickup/delivery/qty-item regexes; menu-item hint now calls
`menu_provider.resolve_item_in_text` directly (that is exactly what
`conversation.menu_item_hint_in_text` did).

### `restaurant/stt_noise.py`
Absorbs `looks_like_order_phrasing` (with a private copy of the add/order-verb
regex) from `conversation`, and `_QTY_WORDS` / `_extract_qty` from
`order_parse` — no longer imports either module.

### `restaurant/order_parse.py`
`_QTY_WORDS`/`_QTY_RE`/`_extract_qty` now imported from `stt_noise` (dependency
direction reversed; file is deleted wholesale in PR 062).

### `restaurant/phone_echo.py` / `restaurant/phone_background.py`
`UserIntent` coupling dropped: the `intent` parameters are now plain
`str | None` intent values ("pickup", "general", …). `agent.py` call sites pass
`intent.value`.

### `restaurant/menu_provider.py`
The one lazy import of `conversation.is_availability_question` inlined as a
private helper with private copies of the regexes it needs.

### `restaurant/session_recorder.py`
`finalize(cart, flow)` → `finalize(cart, *, preferred_language: str | None = None)`
— drops the dependency on the old flow controller's state object.

### `agent.py`
Call-site updates only: `finalize(...)` keyword form, `intent.value` passed to
the echo/background filters, and the fillers feature removed (import,
`_recent_fillers`, `_speak_filler`, `_maybe_speak_filler` and its one call).
Fillers were env-gated OFF in prod (`FILLERS_ENABLED`); restore path is
git history of `restaurant/fillers.py` (deleted at `main@6a55ae6`).

## Files Deleted
- `restaurant/fillers.py` (env-gated off in prod; hard-coupled to
  `UserIntent`/`OrderPhase` which die at cutover)
- `tests/test_fillers.py`

## What's NOT in This PR
- The new brain (`restaurant/agent/core.py`, `prompt.py`, `worker.py`) — PR 061.
- Any deletion of `conversation.py` / `order_flow.py` / `order_parse.py` /
  `prompts.py` / `engine/` — PR 062 (cutover).
- The `channels/` / `analytics/` package reorg — PR 063.
- No behavior change anywhere: the deployed agent's conversation logic is
  untouched (fillers were disabled in prod).

## How to Test
```
uv run python -m pytest tests/ -q
```
Baseline on main before this PR: 7 pre-existing failures (ambient_audio ×2,
conversation ×1, menu_match ×1, order_parse ×3). This PR must not add to them,
and adds `tests/test_agent_gates.py` (new, green).

## Post-Merge: VPS Pull Command
`cd /opt/livekit-sarvam && git pull origin main && uv sync`
