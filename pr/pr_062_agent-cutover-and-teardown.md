# PR 062 — Agent Cutover and Teardown (hybrid rebuild, stage 3 of 4)

## Branch
`pr_062_agent-cutover-and-teardown`

## What This PR Does
Third stage of the conversation-architecture rebuild planned in `refactor.md`
("LLM talks, code owns the cart"). Cuts the deployed entrypoint over to the
new hybrid brain built in PR 061 and deletes the two old conversation systems
it replaces:

- Root `agent.py` (1500 lines: 13 old tools + the regex checkout ladder)
  becomes a thin shim over `restaurant.agent.worker.run()` — the filename and
  `agent_name="restaurant-agent"` are preserved, so systemd
  (`python agent.py start`) and `scripts/setup_sip.py` are unchanged.
- `restaurant/conversation.py`, `order_flow.py`, `order_parse.py`,
  `prompts.py` (the old intent-regex/ladder system) and `restaurant/engine/`
  (the never-wired phase machine) are deleted, along with their tests.
- `llm_warmup.py` re-points to `restaurant.agent.prompt.build_system_prompt`.
- The allergy note recorded by `record_allergies` is now threaded into the
  Clover order note (deferred from PR 061).
- Keeper tests that imported the deleted modules are rewritten against the
  surviving surfaces.

After this PR the hybrid agent IS the deployed agent. Rollout stays gated:
`CLOVER_SUBMIT_ORDERS=0` (shadow mode) until real recorded calls are reviewed
in admin analytics (refactor.md §6).

## Files Modified
### `agent.py`
Rewritten from 1500 lines to a ~10-line shim: re-exports `entrypoint` and
delegates to `restaurant.agent.worker.run()`. Systemd unit and SIP dispatch
untouched.

### `restaurant/llm_warmup.py`
Import re-pointed: `restaurant.prompts` → `restaurant.agent.prompt`
(signature `build_system_prompt(*, is_phone)` unchanged, so nothing else
moves).

### `restaurant/clover/order_submit.py`
`build_order_cart_body` / `submit_cart_to_clover` gain an optional
`allergy_note: str | None` kwarg appended to the Clover order note as
`ALLERGY: <note>` (truncation to 500 chars unchanged).

### `restaurant/agent/core.py`
`place_order` passes `state.allergy_note` to `submit_cart_to_clover`.

### `tests/test_agent_place_order.py`
Fake `submit_cart_to_clover` signatures gained the new `allergy_note` kwarg;
the off-event-loop test now also asserts a "no" allergies answer threads
`allergy_note=None`.

### `tests/test_clover_order_submit.py`
`test_build_order_cart_expands_quantity` also asserts `allergy_note` lands in
the order note as `ALLERGY: <note>` (and is absent when not passed).

### `tests/test_menu_match.py`
Dropped the `order_parse` multi-item parsing tests (`parse_order_lines` /
`can_auto_add_lines` die with the auto-add path — the LLM now adds one
validated item per tool call). The live-transcript regression anchor is
preserved as per-query `find_item` checks for both dishes. All matcher /
disambiguation / abstain / kill-switch tests kept unchanged.

### `tests/test_menu_browse.py`
Dropped the `conversation.py` browse-intent helpers
(`extract_browse_query`, `is_category_browse_query`, `format_browse_reply` —
intent regexes die with the old system; the LLM decides when to browse). All
`menu_provider.browse_menu*` / `menu_browse.resolve_browse_target` tests kept.

### `tests/test_customer_info.py`
Intent-resolution cases (`resolve_intent`, `is_done_ordering`) dropped with
`conversation.py`; `sanitize_assistant_speech` case re-pointed at
`restaurant.agent.replies`. All name/phone parsing and English-phone-speech
tests kept.

### `tests/test_phone_echo.py`
Rewritten against the PR 060 signatures (plain-string intent, no
`UserIntent` / `OrderFlowController`): echo/bypass/recovery-phrase cases kept
with literal intent values; ladder-specific case dropped.

### `tests/test_phone_background.py`
Same intent-string rewrite; all background-filter regression cases kept
(including the PR 053 live-call regressions).

### `tests/test_text_match.py`
Keeps the Indic word-boundary unit tests (`text_match` is a keeper) and the
background-filter regressions with literal intent strings; the
`detect_intent` three-script matrix and `_extract_qty` cases die with
`conversation.py` / `order_parse.py` (quantity words now live in
`stt_noise.parse_standalone_quantity`, covered by test_stt_noise).

## Files Deleted
- `restaurant/conversation.py` (1039 lines)
- `restaurant/order_flow.py` (540 lines)
- `restaurant/order_parse.py`
- `restaurant/prompts.py`
- `restaurant/engine/` (entire package: core, extractor, renderer, resolver,
  live, README)
- `tests/test_conversation.py`
- `tests/test_order_flow.py`
- `tests/test_order_parse.py`
- `tests/test_engine.py`
- `tests/test_engine_renderer.py`
- `tests/test_engine_resolver.py`
- `tests/test_item_availability.py` (tested `conversation.py` availability
  intents; availability itself is enforced in `_resolve_menu_item`, covered
  by `tests/test_agent_tools.py`)
- `tests/test_language.py` (ported to `tests/test_agent_language.py` in
  PR 061; ladder-guidance cases die with `order_flow.py`)

## What's NOT in This PR
- The `channels/` / `analytics/` package reorg — PR 063.
- Flipping `CLOVER_SUBMIT_ORDERS=1` — only after shadow-mode call review
  (refactor.md §6 rollout doctrine).
- Any change to `clover/` matching, `menu_provider`, web, admin, or deploy
  units beyond the order-note kwarg above.

## How to Test
```
uv run python -m pytest tests/ -q
```
Only pre-existing failures allowed: ambient_audio ×2 (environment-dependent,
inherited baseline). Everything else green.

Console smoke (shadow mode):
```
USE_CLOVER_MENU=1 CLOVER_SUBMIT_ORDERS=0 uv run python agent.py console
```
Scripted call per refactor.md §6: ambiguous "fish" must ask, spice refusal →
answer, late add forces re-readback, 9-digit phone re-asked, allergies
recorded, readback → place → shadow log payload correct.

## Post-Merge: VPS Pull Command
`cd /opt/livekit-sarvam && git pull origin main && uv sync`
Then restart in shadow mode and review calls before enabling submit:
`systemctl restart restaurant-agent` (env keeps `CLOVER_SUBMIT_ORDERS=0`).
