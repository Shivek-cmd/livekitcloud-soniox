# PR 047 — Checkout ladder intent guard + production-grade LLM warmup

## Branch
`pr_047_ladder-intent-guard-and-llm-warmup-v2`

## Problem (live call, 2026-07-06)

Two separate bugs surfaced in the same test call transcript.

### Bug 1 — checkout ladder steamrolled an unanswered question

```
Turn 3  Caller: "...ਬਟੂਰੇ 'ਚ ਕਿਹੜੀ ਆਈਟਮ ਹੈ? ਬਟੂਰੇ ਮਿਲ ਜਾਣਗੇ?" (what's in bhature? is it available?)
        Sierra: "...ਬਟੂਰੇ ਉਪਲਬਧ ਨਹੀਂ ਹਨ। ਕੁਝ ਹੋਰ سفارش ਕਰਨਾ ਚਾਹੁੰਦੇ ਹੋ?" (not available, anything else?)
Turn 4  Caller: "ਨਹੀਂ, ਛੋਲੇ ਬਟੂਰੇ ਨਹੀਂ ਹਨ।" (no [more], chole bhature isn't there)
        Sierra: "Any allergies or special instructions?"
Turn 5  Caller: "ਛੋਲੇ ਬਟੂਰੇ ਨਹੀਂ ਹਨ।" (chole bhature isn't there — repeating, NOT an allergy answer)
        Sierra: "Will that be pickup or delivery?"   ← WRONG — allergies was never answered
```

Root cause: `_NO_RE` in `restaurant/conversation.py` is an **unanchored** substring
match — it fires on "ਨਹੀਂ" (no/not) appearing *anywhere* in an utterance, including
deep inside a predicate negation like "ਨਹੀਂ ਹਨ" (are not / there isn't), which has
nothing to do with answering a yes/no question. `is_allergies_step_answer()` then
blindly trusted `CONFIRM_NO` as "customer answered allergies" and the checkout ladder
advanced past a question the caller never actually answered — matching the user's
report: *"it went into her flow... she should answer based on what I'm asking."*

Turn 4's leading "ਨਹੀਂ," genuinely was a discourse-level "no [more items]" and must
keep working; turn 5 has no such leading negative — the "ਨਹੀਂ" only appears buried
inside an unrelated descriptive sentence about a dish.

### Bug 2 — script leak in TTS

`سفارش` (Urdu/Arabic script for "order") leaked into Sierra's Gurmukhi speech —
same class of bug as the "Dhanyavaad" fix in PR 045, different word.

### Bug 3 — PR 046's LLM warmup only got a partial cache hit

PR 046's warmup call sent only `messages` (system prompt + "Hi") with no `tools`.
Every real turn sends the full 13-tool function-calling schema alongside the system
prompt, so the serialized request prefix OpenAI hashes for caching didn't match —
confirmed via the live call: `llm_ttft` improved from ~3.5s (cold) to only ~2.0s
(partial hit) instead of the fully-warmed ~0.6–1.6s.

## Fix

### `restaurant/conversation.py`
- New `is_confirm_no(text)` — **leading**-negative match only (mirrors the existing
  anchored `_YES_RE` shape), via new `_LEADING_NO_RE`. A bare/leading "no", "ਨਹੀਂ,",
  "nahi ji" etc. still counts; a negation embedded later in a sentence about
  something else (food availability, prices, etc.) no longer does.
- `detect_intent()`'s `CONFIRM_NO` fallback now uses `is_confirm_no()` instead of
  the raw unanchored `_NO_RE.search()`.
- `is_allergies_step_answer()`'s `GENERAL`-intent fallback does the same.
- `_NO_RE` itself is untouched and still used as-is in `is_done_ordering()`, where
  it's already gated by requiring co-occurrence with `_ENOUGH_RE` — lower false-hit
  risk, out of scope for this fix.
- `sanitize_assistant_speech()` — added `"سفارش": "ਆਰਡਰ"` to the existing
  Urdu/Arabic-script replacement dict (same mechanism as the Dhanyavaad fix).

### `agent.py`
- `_try_run_checkout_ladder()`, `SPECIAL_INSTRUCTIONS` branch: when the caller's
  turn does **not** answer allergies and isn't a detour intent (price/availability/
  status/human/add — reused from `order_flow.DETOUR_INTENTS`), re-speak
  `ALLERGIES_QUESTION` instead of silently advancing (old bug) or going dead silent
  (what fixing bug 1 alone would otherwise cause, since `fillers.py` blocks fillers
  in this phase and the general checkout-mute path has no fallback speech).
- LLM warmup call moved from right after `is_phone` resolution to right after
  `agent = RestaurantAgent(is_phone=is_phone)` is constructed, so it can pass the
  agent's real registered tools (`agent.tools`) into the warmup — still races the
  greeting comfortably (greeting alone runs 5-8s of TTS before the caller can even
  reply).

### `restaurant/llm_warmup.py` (rewritten)
- Now drives the warmup through the **actual** `openai.LLM` plugin
  (`voice_stack.build_llm()`) and a real `livekit.agents.llm.ChatContext`, passing
  the **real tool list** (`agent.tools`, threaded in as a parameter — no import of
  `agent.py`, avoids a circular import) instead of a hand-rolled raw `AsyncOpenAI`
  call with no tools. This guarantees the request prefix OpenAI caches is byte-
  identical to a real conversation turn.
- Uses `extra_kwargs={"max_completion_tokens": 1}` to keep the throwaway call cheap
  (verified this is the correct plugin-level param name, not `max_tokens`).
- Verified manually end-to-end against the real OpenAI API before wiring in:
  13 tools serialized correctly, `prompt_tokens=1414` (matches production's ~1443
  ballpark), 200 OK.

### `tests/test_llm_warmup.py` (rewritten)
Updated to mock `ChatContext`/`build_llm` instead of `AsyncOpenAI`, matching the new
implementation; same coverage shape (env kill-switch, tools/system-prompt passed
through, exception swallowing, task scheduling).

### `tests/test_conversation.py`
New tests for `is_confirm_no()` (leading vs embedded negation), plus a regression
test reproducing the exact turn-5 transcript line to confirm
`is_allergies_step_answer()` now returns `False` for it and `detect_intent()` no
longer misclassifies it as `CONFIRM_NO`.

## What's NOT in This PR

- No general contextual "answer any off-script question mid-checkout" capability —
  that remains an LLM-mute-during-checkout architectural tradeoff from PR 045.
  This PR only stops the ladder from *wrongly advancing* on an unanswered question
  and adds a re-ask nudge for the allergies step specifically; it does not attempt
  to have Sierra directly re-address "what's in bhature" mid-checkout.
- The re-ask fallback is scoped to `SPECIAL_INSTRUCTIONS` only (the phase in the
  reported bug), not generalized to every code-owned checkout phase, to keep this
  change narrow and testable (see `docs/HANDOFF.md` — PR 030 was reverted for
  over-broad phase-rule changes).
- No generic "strip all Arabic-script characters" safety net — only the specific
  known leaked word is mapped, matching the existing Dhanyavaad-fix pattern.

## How to Test

```bash
PYTHONPATH=. pytest tests/test_conversation.py tests/test_llm_warmup.py tests/test_order_flow.py -q
```

Live:
1. Place a test call, say something containing "ਨਹੀਂ" mid-sentence about a menu
   item during the allergies step (e.g. repeat an earlier availability question) —
   confirm Sierra re-asks allergies instead of jumping to pickup/delivery.
2. Confirm a genuine "ਨਹੀਂ ਜੀ" / "no" bare answer at allergies still advances
   normally to pickup/delivery (no regression).
3. Watch for `LLM_WARMUP ok channel=phone elapsed=...` in logs, then confirm turn-1
   `llm_ttft` in the `LATENCY` line drops into the fully-warmed 0.6–1.6s range
   (not the ~2.0s partial-hit seen after PR 046 alone):

```bash
journalctl -u restaurant-agent -f | grep -E 'LLM_WARMUP|LATENCY|llm_ttft'
```

Kill switch unchanged: `LLM_WARMUP_ENABLED=0`.

## Post-Merge: VPS Pull Command
`cd /opt/livekit-sarvam && git pull origin main && uv sync`
