# PR 042 — Voice flow correctness pass (speech collision, corrections, hallucinated read-backs, intent priority)

## Branch
`pr_042_speech-collision-fix`

## What This PR Does

Diagnosed against two live call transcripts and the actual `agent.py` /
`livekit-agents` SDK behavior (not guessed). Four distinct, reproducible bugs
were found and fixed in this branch — bundled together per request rather
than split into separate PRs. Each is independently testable; see the
sub-sections below.

---

## Fix 1 — Garbled back-to-back speech (filler/ladder/LLM collision)

### Problem

Live call transcripts show Sierra's speech occasionally garbled into a single
run-on, mixed-language sentence, e.g.:

> "ਹਾਂ ਜੀ, ਇੱਕ ਗਾਰਲਿਕ Will that be pickup or delivery? menu check kardi haan."

`"menu check kardi haan."` is a literal Punjabi filler string from
`restaurant/fillers.py` (`FillerKind.PROCESSING` pool) — real evidence that
two or three independently-triggered `session.say()` calls landed
back-to-back in the same turn window.

Root cause (confirmed against the `livekit-agents` SDK):

1. `AgentActivity` queues every `session.say()` / generated reply as a
   `SpeechHandle` in a single FIFO priority queue (`agent_activity.py`,
   `_speech_q` / `_scheduling_task`). All our call sites use the same
   priority (`SPEECH_PRIORITY_NORMAL`), so speeches never interrupt each
   other — they play strictly back-to-back.
2. `AgentSession` supports `min_consecutive_speech_delay` to force a pause
   between consecutive queued speeches, but it was never set in
   `restaurant/session_config.py` — the gap defaulted to `0.0`.
3. `agent.py::_maybe_speak_filler` fired a filler via
   `asyncio.create_task(self._speak_filler(line))` — fire-and-forget, no
   `SpeechHandle` tracked, not awaited — in the same `on_user_turn_completed`
   call that, moments later, lets the framework generate and speak the real
   LLM turn reply (accelerated further by `preemptive_generation`, enabled by
   default). The `agent_session_busy()` guard only inspects `agent_state` at
   decision time, before the real reply's generation has started.
4. The same fire-and-forget pattern was used by `_echo_reprompt` and
   `_background_reprompt`, exposed to the same class of collision.

### Solution

- `min_consecutive_speech_delay` (env-tunable via `MIN_CONSECUTIVE_SPEECH_DELAY_SEC`,
  default 0.3s) now set on `AgentSession` in `session_config.py` — forces a
  clean pause between any two queued speech handles.
- New `RestaurantAgent._speech_in_flight()` helper checks
  `session.current_speech` right before firing a fire-and-forget filler or
  reprompt. `_speak_filler`, `_echo_reprompt`, `_background_reprompt` all skip
  (do not queue) if speech is already in flight, instead of stacking behind
  it.

### Files Modified
- `restaurant/session_config.py` — `min_consecutive_speech_delay_seconds()` + wired into `AgentSession(**kwargs)`.
- `agent.py` — `_speech_in_flight()` + guard added to `_speak_filler`, `_echo_reprompt`, `_background_reprompt`.
- `.env.example` — document `MIN_CONSECUTIVE_SPEECH_DELAY_SEC`.
- `tests/test_session_config.py` (new) — env default/override.

---

## Fix 2 — Quantity corrections compounded instead of fixing

### Problem

Conversation 2, turn 11: caller says *"I said one, not two"* — Sierra calls
`add_to_order` again to "fix" it. But `OrderCart.add_item` always merges
additively (`existing.quantity += quantity`), and there was no tool to set an
absolute quantity. The correction attempt pushed qty from 1 to 2 — the exact
wrong number the caller was trying to correct away from.

### Solution

- `OrderCart.update_item_quantity(name, quantity)` (`restaurant/orders.py`) —
  sets an absolute quantity (not additive); `quantity<=0` removes the line.
- New `update_item_quantity` function tool in `agent.py`, with a docstring
  telling the LLM this is the correction path, not `add_to_order`.
- `restaurant/prompts.py` — explicit system-prompt instruction: any time the
  customer is correcting a quantity already in the order, call
  `update_item_quantity`, never `add_to_order`.
- `restaurant/conversation.py` — `format_update_tool_reply()` template, phrased
  as a correction ("Got it — one X, fixed.") so it never reads as a second add.

### Files Modified
- `restaurant/orders.py`, `agent.py`, `restaurant/prompts.py`, `restaurant/conversation.py`
- `tests/test_orders.py` (new) — additive `add_item` vs. absolute `update_item_quantity`, zero-removes, not-found.

---

## Fix 3 — LLM hallucinates order contents on mid-call status questions

### Problem

Conversation 2, turns 9–10: Sierra twice states *"two Fish Pakora (extra
ajwain)"* — a dish the caller never ordered (they ordered one Amritsari
Fish). No tool call is logged for either turn — pure LLM freeform text.

Root cause: the caller's question in turn 10, *"ਮੇਰਾ ਆਰਡਰ ਦੱਸੋ... ਕੀ ਆਰਡਰ
ਕੀਤਾ ਜੀ ਮੈਂ?"* ("tell me my order... what did I order?"), matched `_ADD_RE`
(which contains the bare word `ਆਰਡਰ`/"order") and was classified `ADD_ITEM`,
not a status question. That routed the LLM into free generation — the one
existing code-owned read-back (`format_order_readback`, grounded in the real
cart) only fires at the final-confirmation ladder step, not for an ad-hoc
mid-call "what do I have so far?".

### Solution

- New `UserIntent.ASK_ORDER_STATUS` + `_ORDER_STATUS_RE`, checked in
  `detect_intent` *before* the price/add-item patterns so a status question
  always wins over the `ਆਰਡਰ` false match.
- New `format_order_status(cart, include_price)` template (`restaurant/conversation.py`)
  — neutral mid-conversation cart read, grounded in the real cart, distinct
  from the final-confirmation `format_order_readback` (no order_type/"All good?").
- `RestaurantAgent._try_answer_order_status()` — code-owned, runs at any
  phase, first in `on_user_turn_completed`, before the checkout ladder.
  Never lets the LLM free-generate this answer.

### Files Modified
- `restaurant/conversation.py`, `agent.py`
- `tests/test_conversation.py` — exact regression case from the transcript, plus template tests.

---

## Fix 4 — Leading negation swallows a restated menu item

### Problem

Conversation 1: caller adds Garlic Naan (turn 4), it silently fails to
register, caller restates it — *"ਨਹੀਂ ਨਹੀਂ, ਗਾਰਲਿਕ ਨਾਨ ਕਰੋ"* (turn 6) — but
`_NO_RE` matches the leading "ਨਹੀਂ ਨਹੀਂ" and the whole utterance is
classified `CONFIRM_NO` (read as "no allergies"), so the ladder advances
straight to pickup/delivery while the item is still never added. The caller
has to repeat it a third time (turn 7, *"ਗਾਰਲਿਕ ਨਾਨ ਐਡ ਕਰੋ"*) before it
finally lands — and even then, `_ADD_RE` was missing "ਐਡ" (the common
Gurmukhi spelling of the English loanword "add") entirely.

### Solution

- `_add_item_with_action_cue(text)` (`restaurant/conversation.py`) — a named
  menu item + an add-imperative cue (ਕਰੋ/ਕਰ ਦ/ਦਿਓ/ਦਿਉ/ਐਡ/add) now wins over
  `_NO_RE`, checked in `detect_intent` right before the negation check.
- Added "ਐਡ" to `_ADD_RE`.
- Supporting fix: `restaurant/menu.py::find_item` (static-menu fallback) only
  checked query-in-item-name, so a dish name embedded in a longer sentence
  could never resolve via `menu_item_hint_in_text`. Now matches both
  directions with a length guard against short-string false positives.

### Files Modified
- `restaurant/conversation.py`, `restaurant/menu.py`
- `tests/test_conversation.py` — exact regression cases (restated item after "ਨਹੀਂ ਨਹੀਂ", Gurmukhi "ਐਡ", plain negation still works).

---

## What's NOT in This PR

- No change to `preemptive_generation` (left enabled — latency win; the
  speech-delay gap is sufficient to stop garbling without giving it up).
- No rework of the checkout-ladder/LLM hybrid architecture itself — these are
  targeted correctness fixes within the existing design.
- Clover-cache confidence matcher (`restaurant/clover/match.py`) untouched —
  Fix 4's `menu.py` change only affects the static-menu fallback
  (`USE_CLOVER_MENU=0`), not the production matcher.

## How to Test

- [x] `PYTHONPATH=. uv run pytest tests/` — 154 passed, 7 pre-existing
      failures unrelated to this branch (confirmed identical on `main` before
      this branch: `test_ambient_audio.py`, `test_menu_match.py`,
      `test_order_parse.py`)
- [ ] Outbound test call (`scripts/test_call.py`): trigger a filler (ask
      price / availability mid-order) immediately followed by an add —
      confirm the two utterances are audibly separated, not run together
- [ ] Live call: add an item, get the quantity wrong, correct it ("I said
      one, not two") — confirm the cart ends at the corrected quantity, not
      compounded
- [ ] Mid-call, ask "what's my order so far?" — confirm the read-back matches
      the actual cart, not a hallucinated item
- [ ] Add an item, then restate/correct it after a "no no" — confirm it adds
      instead of silently advancing the ladder
- [ ] `journalctl -u restaurant-agent -f | grep SIERRA:` during a live call —
      no more multi-language run-on lines

## Post-Merge: VPS Pull Command

`cd /opt/livekit-sarvam && git pull origin main && uv sync && systemctl restart restaurant-agent`
