# PR 061 — Hybrid Agent Brain (hybrid rebuild, stage 2 of 4)

## Branch
`pr_061_hybrid-agent-brain`

## What This PR Does
Second stage of the conversation-architecture rebuild planned in `refactor.md`
("LLM talks, code owns the cart"). Builds the complete new agent brain —
`restaurant/agent/core.py` (RestaurantAgent + validating/resolving tools),
`prompt.py` (salvaged persona + new FLOW section), `worker.py` (entrypoint) —
plus its full unit-test suite. **Nothing is wired**: root `agent.py` still runs
the old deployed agent, no files are deleted, and no deployed behavior changes.
Cutover (shim + deletions + e2e) is PR 062.

Design invariants (from `refactor.md` §2):
- The LLM can never write an arbitrary item, price, or quantity into the cart —
  every item tool routes through `_resolve_menu_item`, which abstains
  (AMBIGUOUS with real options / NOT FOUND / unavailable) instead of guessing,
  and adds use the resolved menu payload only.
- Items with a "Spice Level" group refuse to add without a validated spice
  level; other required modifier groups refuse without a note.
- Readback text is generated only from the code cart
  (`get_order_readback`), never from the LLM's memory, and is revision-gated:
  any cart mutation (voice tool or web-RPC tap) after the readback forces a
  re-readback before `place_order` will run.
- `place_order` is hard-gated by `gates.place_order_blockers` (items, order
  type, address, valid name, 10-digit phone, allergies asked, fresh confirmed
  readback). Clover submit runs via `asyncio.to_thread` (the old agent blocked
  the event loop) and a Clover failure produces a spoken failure path — never
  a false "order's in".

## Files Added
### `restaurant/agent/core.py`
`RestaurantAgent(Agent)` — holds `.cart: OrderCart`, `.state:
OrderSessionState`, `.is_phone`, bind methods (session / recorder / web_sync /
job_context). Constructible without a session, so every tool is directly
unit-testable. 17 `@function_tool` methods per plan §2.2: `add_item`,
`set_item_quantity` (exact set, never additive), `remove_item`,
`set_item_spice`, `check_menu_item`, `search_menu`, `record_allergies`,
`set_order_type`, `set_delivery_address`, `set_customer_contact` (name/phone
validated, 11-with-leading-1 accepted), `get_order_readback` (the only source
of readback text), `confirm_readback` (refuses on stale revision),
`place_order` (blockers verbatim; to_thread Clover submit; shadow gate;
goodbye + auto-hangup; ORDER COMPLETE sentinel), `transfer_to_human`,
`check_table_availability`, `book_reservation`, `get_order_summary`.
`on_user_turn_completed` is channel hygiene ONLY (echo → background → STT
noise → sticky language → recorder) — no intent regexes, no auto-add, no
checkout ladder, no turn-guidance injection.

### `restaurant/agent/prompt.py`
`build_system_prompt(*, is_phone)` — persona / LANGUAGE / phone no-price /
web-channel blocks salvaged from `prompts.py` (hard-won live-call lessons),
all `[TURN GUIDANCE]` machinery dropped, new ORDER FLOW + TRUST TOOL RESULTS
section, tool list rewritten for the new tool names. Signature kept so
`llm_warmup.py` needs only an import change at cutover.

### `restaurant/agent/worker.py`
`entrypoint(ctx)` carried 1:1 from old `agent.py:1349-1500`: connect +
wait_for_participant, `is_phone` detection, SIP caller phone, SessionRecorder
start + idempotent analytics flush (now
`finalize(cart, preferred_language=agent.state.preferred_language.value)`),
TurnLatencyTracker, LLM warmup, ambient audio, WebSync on web, recorder
transcript hooks with the slim `sanitize_assistant_speech`, opening greeting,
phone greeting settle + echo reprompt. Plus `run()` with
`agent_name="restaurant-agent"` for the PR 062 root shim.

### `tests/test_agent_tools.py`
Add happy path (resolved payload, no LLM price); AMBIGUOUS → options + cart
unchanged; NOT FOUND; unavailable; spice refusal → retry with spice succeeds;
required-group refusal; qty clamp 1–20; exact-set quantity; remove; spice
correction rewrites note; contact rejects 9-digit / junk name, accepts 10 and
11-with-leading-1; order type / address validation; readback refuses while
incomplete; readback→mutate→confirm refused→re-readback→confirm OK.

### `tests/test_agent_place_order.py`
Monkeypatched `submit_cart_to_clover`: to_thread path (submit called off the
event loop), shadow-mode gate (no submit when disabled), goodbye + hangup
scheduling, ORDER COMPLETE sentinel, Clover error → spoken failure (no false
success, cart not marked placed), blockers returned verbatim, idempotent
double-call.

### `tests/test_agent_replies.py`
Ported formatter cases (add/update/remove tool replies, order status,
readback with/without price/name, goodbye, sanitizer greeting/meta/price
stripping) against `restaurant.agent.replies`.

### `tests/test_agent_language.py`
Ported `detect_customer_language` / `update_preferred_language` cases against
`restaurant.agent.language`.

## Files Modified
### `restaurant/agent/gates.py`
`place_order_blockers` split: new `readback_blockers(cart, state)` returns the
completeness blockers (everything except readback confirmation) so
`get_order_readback` can refuse with the same texts; `place_order_blockers` =
`readback_blockers` + the readback-confirmation check. No behavior change.

### `restaurant/agent/replies.py`
Adds `echo_recovery_phrase` and `background_repeat_phrase` (salvaged verbatim
from `conversation.py`) — needed by the hygiene-only turn hook so the new
brain never imports `conversation.py`.

## Files Deleted
None (deletions happen at cutover, PR 062).

## What's NOT in This PR
- Wiring: root `agent.py` untouched — the old agent remains the deployed
  entrypoint; `llm_warmup.py` still imports `restaurant.prompts`.
- Deletions of `conversation.py` / `order_flow.py` / `order_parse.py` /
  `prompts.py` / `engine/` — PR 062.
- Threading the allergy note into the Clover order note (needs a one-line
  `order_submit.py` change; deferred to PR 062 cutover). The note is stored in
  `state.allergy_note`, logged, and recorded in analytics events.
- The `channels/` / `analytics/` package reorg — PR 063.

## How to Test
```
uv run python -m pytest tests/ -q
```
Baseline inherited from PR 060: 7 pre-existing failures (ambient_audio ×2,
conversation ×1, menu_match ×1, order_parse ×3). This PR adds none, and adds
59 new tests across the four new test files (all green; 313 passed total).

## Post-Merge: VPS Pull Command
`cd /opt/livekit-sarvam && git pull origin main && uv sync`
(No deployed behavior change — the new brain is unwired until PR 062.)
