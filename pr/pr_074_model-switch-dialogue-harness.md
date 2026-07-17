# PR 074 — Model Switch (gpt-4.1-mini) + Dialogue Eval Harness + Baseline

## Branch
`pr_074_model-switch-dialogue-harness`

## What This PR Does
Step 1 of the Human Conversation Rebuild (refactor.md). Switches the LLM to
`gpt-4.1-mini` (env-overridable via `OPENAI_LLM_MODEL`) and builds the
measurement tool BEFORE any behavior changes: a dev-only dialogue harness that
drives the real `RestaurantAgent` tools through a scripted customer
conversation using real OpenAI calls (no audio, no LiveKit session), plus 8
scenario scripts and a committed baseline run against the current prompt so
every later step (PRs 075–080) has a before/after.

## Files Added
### `scripts/dialogue_harness.py`
Dev-only harness. Instantiates `RestaurantAgent` without a session (the agent
is null-safe headless: `_sync_web`/`_record_tool` no-op, `place_order` has a
no-session branch). Runs a manual OpenAI tool-loop at temperature 0 over each
scenario's scripted customer turns: tool schemas come from the agent's real
`function_tool`s via `livekit.agents.llm.utils.build_legacy_openai_schema`,
and every tool call is executed against the real agent (real menu resolution,
real gates, real cart). Mirrors the runtime turn hook's language tracking +
`real_user_turns` (channel filters are audio-path concerns and don't apply).
Emits per scenario: full transcript, tool log, final `cart.to_state_dict()`,
and machine assertion results. Non-flag invariant checked on every scenario:
if the order was placed, the readback must have been confirmed at the final
cart revision (gates respected).

Turn selection is script-first with a small reactive layer, because the agent
asks optional clarifying questions non-deterministically (even at temperature
0) and a purely fixed script drifts one question off: a built-in rule answers
"Yes." when the agent reads the phone number back as a question (≥6 English
digit words + "?"), and scenarios may declare `reactive` rules
(`{"when": regex, "say": ..., "max_uses": N}`) that answer a matching agent
question without consuming the scripted queue. Injected turns are marked
`(reactive)` in transcripts and capped at 6 per scenario.

Usage: `uv run python scripts/dialogue_harness.py [--scenario NAME] [--out DIR] [--model MODEL]`
Menu source follows `.env` (`USE_CLOVER_MENU=1` + committed
`data/menu_cache_bizbull.json`), same as production.

### `tests/scenarios/*.json` (8 scenarios)
Scripted customer turns + expected outcomes (`expect` block: `placed`,
`items` name/qty/note_contains, `order_type`, `customer_name`,
`customer_phone`, `allergies_recorded`, `min_readbacks`, `transcript_any`):
- `english_pickup.json` — plain English pickup order, two items
- `punjabi_order.json` — Gurmukhi-script order end to end
- `hindi_order.json` — Devanagari-script order end to end
- `quantity_correction.json` — "I said one, not two" → set_item_quantity, not additive
- `ambiguous_fish.json` — "fish" must trigger disambiguation, never a guess
- `delivery_split_phone.json` — delivery + address; phone digits spoken across two turns
- `change_after_readback.json` — cart change after readback must force a fresh readback
- `price_ask_phone.json` — phone channel: price only stated because the customer asked

### `docs/eval/baseline/`
Baseline harness run against the CURRENT prompt (pre-rebuild) on
gpt-4.1-mini: one `.json` (machine record) + one `.md` (readable transcript)
per scenario, plus `summary.md`. 8/8 green (twice in a row). Later steps diff
against these.

Baseline findings the transcripts document (fixes belong to later steps, not
this PR):
- **Price refused even when asked (phone):** the customer explicitly asks
  "how much will that be?" and Sierra answers "Sorry, I can't share prices
  right now" — the price never reaches the LLM speech path on phone (add
  replies forbid it, phone readback/summary strip it). Step 2's `total=`
  facts line addresses this.
- **`set_order_type` skipped on "Delivery please":** the model acknowledges
  delivery but doesn't call the tool; only the readback blocker ("Pickup or
  delivery has not been set") forces the re-ask that finally records it. The
  gate catches it every time, but it costs 2–4 extra turns.
- **Silent spice guess:** for "one dal makhani" (no spice stated) the model
  passed `spice_level="medium"` on its own instead of asking, dodging the
  NEEDS SPICE refusal. Harmless here (medium is the documented default) but
  it is exactly the per-dish spice interrogation Step 3 removes.

## Files Modified
### `restaurant/voice_stack.py`
`build_llm()` now reads `OPENAI_LLM_MODEL` (default `gpt-4.1-mini`, was
hard-coded `gpt-4o-mini`). Rollback: `OPENAI_LLM_MODEL=gpt-4o-mini`.

### `tests/test_voice_stack.py`
New tests for the `OPENAI_LLM_MODEL` env knob (default / override / blank).

## Files Deleted
None.

## What's NOT in This PR
No prompt, tool-reply, flow, persona, readback, or speech-guard changes —
behavior is identical except for the model name. Those are PRs 075–080.
The harness does not simulate STT noise/echo/background filters (audio-path
only) and does not score naturalness (judge/rubric is PR 080).

## How to Test
```
uv run pytest                                   # full suite
uv run python scripts/dialogue_harness.py       # all 8 scenarios (needs OPENAI_API_KEY)
uv run python scripts/dialogue_harness.py --scenario english_pickup
```
Live: 2–3 real calls; check gpt-4.1-mini turn latency in TurnLatencyTracker
logs. Rollback: `OPENAI_LLM_MODEL=gpt-4o-mini`.

## Post-Merge: VPS Pull Command
`cd /opt/livekit-sarvam && git pull origin main && uv sync`
