# Order engine rebuild — architecture

## Why
The old flow let the LLM drive the conversation and mutate the cart via free
tool calls, with code chasing it using regexes and guard flags. That is why one
ambiguous word ("fish") became two invented dishes with an invented quantity.
Prompt rules are not guarantees; control flow is.

## The inversion: LLM proposes, code disposes
```
  transcript ──▶ [ EXTRACTOR (LLM) ] ──▶ Proposal ──▶ [ OrderEngine (code) ] ──▶ [Action…]
                  language only                         owns ALL state,             │
                                                        confirms every item         ▼
                                                                            [ RENDERER (LLM/TTS) ]
                                                                             says it in-language
```
* **Extractor (LLM):** turns one messy multilingual utterance into a structured
  `Proposal` (adds/corrections/removals/yes/no/order_type/name/phone/…). It
  never touches the cart. Output is a small JSON schema — easy to validate.
* **OrderEngine (code, this package):** the single source of truth. Pure state
  machine, no I/O. Resolves dishes via the **kept** matcher, and:
  - ambiguous term → asks which one (never guesses),
  - no quantity stated → asks (never invents),
  - every item confirmed before it locks; every correction sets an exact total.
* **Renderer (LLM/TTS):** turns a code-chosen `Action` (`confirm_item`,
  `clarify`, `readback`, …) into the caller's language. The *content* (which
  dish, which options, the read-back list, totals) is code-supplied and exact;
  the LLM only phrases it warmly.

## What we KEEP from the old code (it's good)
- `restaurant/clover/match.py` — cross-script phonetic matcher + abstain.
- `restaurant/clover/*`, `menu_provider` — menu cache, Clover POS, submit.
- `orders.py` cart math, tenant config, LiveKit session/telephony plumbing.

## What we REPLACE
- `order_flow.py`, the `agent.py` checkout ladder, and the `conversation.py`
  regex intent detection — the "three competing authorities" — with this engine
  + a thin extractor + renderer.

## Status
- [x] Stage 1 — `OrderEngine` deterministic core + tests (`tests/test_engine.py`).
- [ ] Stage 2 — `CloverResolver` adapter (engine ↔ real matcher/menu cache).
- [ ] Stage 3 — `extractor.py` (LLM → Proposal, JSON schema + validation).
- [ ] Stage 4 — `renderer.py` (Action → in-language speech, fixed templates on
      the money path) + LiveKit adapter replacing the old turn handler.
- [ ] Stage 5 — shadow mode (log proposed vs. correct), then ONE pilot
      restaurant, then the rest. No four-at-once rollout.

## Non-negotiables
1. Code owns 100% of cart state. The LLM never adds/removes/sets quantity.
2. Confirmation on the money path (each item + final order) is mandatory.
3. Ambiguity is always a question, never a guess. Quantities are never invented.
4. STT accuracy on real calls is measured before pilot — it is the ceiling.
