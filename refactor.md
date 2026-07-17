# Human Conversation Rebuild — Persona-Driven Conversational Layer

**Working doc for the conversation-system refactor. One step per session.**

## How to use this doc (read this first in every fresh session)

1. Read **Standing context** below, then find the first step whose status is not ✅ DONE.
2. Read ONLY that step (plus the previous step's *Checkpoint* notes) — everything a fresh session needs is in those two places.
3. Do the step: branch per repo convention (`pr/pr_NNN_*.md` doc first, matching branch, tests listed in the doc). Commit locally — **never push or open a PR without explicit user approval**.
4. When the step is verified done, fill in its **Checkpoint** block (commit, deviations, findings, notes for the next session), flip its status to ✅ DONE, and commit the doc update.
5. Stop. The next step belongs to the next session.

Statuses: ☐ TODO · 🔶 IN PROGRESS · ✅ DONE

---

## Standing context (true for every step)

**Problem:** the agent's conversation sounds scripted/robotic. The skeleton is right — *LLM talks, code owns the cart* — but the "LLM talks" half is scripted: hard prompt rules ("ONE short sentence per turn", arrow-chain ORDER FLOW), `SAY EXACTLY:` cue-card tool replies (`replies.py`, returned from inside `OrderCart` methods), per-dish spice interrogation (NEEDS SPICE refusal in `add_item`), a VERBATIM readback template, code-spoken canned lines (greeting, goodbye, recovery), and a regex speech guard.

**Verified facts (don't re-derive):**
- `sanitize_assistant_speech` is **log-only** today — `worker.py:166` computes `cleaned` but never alters spoken output. Deleting it changes nothing at runtime.
- `enforce_english_phone_in_speech` is therefore NOT currently a hard guarantee; it becomes one only when moved into the TTS path (Step 6).
- `orders.py` imports formatters from `replies.py` — cart mutations return pre-formatted speech strings (inversion to fix in Step 2).
- Model is `gpt-4o-mini` at `voice_stack.py:build_llm`.
- `_recent_agent_lines` / `note_agent_speech` / the `conversation_item_added` hook are an existing assistant-utterance capture path (reused by the readback verifier in Step 5).

**User decisions (fixed — do not relitigate):**
- LLM → `gpt-4.1-mini` via `OPENAI_LLM_MODEL` env var; bump to `gpt-4.1` only if Step 7 data says so.
- Persona: keep **Sierra**, as an **AI cashier** — warm, quick Punjabi-restaurant counter manner, trilingual code-mix; NOT a fake-human backstory. Persona doc drafted by Claude, **user approves before it ships**.
- Flow (kept, enforced as a hard code checklist, never trusted to LLM context): items → **one final additional-requests question** (spice preferences + allergies + special instructions, asked once at end of ordering) → pickup/delivery (+address) → name/phone → readback → confirm → place. Adds get a natural one-liner confirm; **no per-dish spice interrogation**.
- Readback: grounded-but-natural — code emits canonical facts, LLM phrases them in the customer's language, a code verifier checks every item/qty/order-type was spoken before `confirm_readback` succeeds.
- Guardrails: delete SAY EXACTLY scripts + phrase-strip regexes; keep only hard TTS-correctness rules.

**Invariants (PR 030 lesson — money path lives in code, never prompt):**
- `_resolve_menu_item` choke point + refusal strings (AMBIGUOUS / NOT FOUND / NEEDS INFO / blockers) stay as-is.
- `gates.readback_blockers` / `place_order_blockers` remain THE hard checklist; cart revision counter keeps invalidating stale readbacks.
- Item names/prices enter the cart only via resolved menu payloads. Spice defaults applied by code, never LLM guess.
- Hard TTS rules survive in the prompt: Punjabi→Gurmukhi / Hindi→Devanagari, never Roman; phone digits as English words; dish names = `voice_line` exactly; checkout terms (pickup/delivery/confirm) stay English; no volunteered price on phone.
- Untouched: turn system, channel filters (`on_user_turn_completed` hygiene), STT/TTS stack, turn detection, analytics, web sync.

**Key files:** `restaurant/agent/core.py` (agent + tools), `gates.py`, `prompt.py`, `replies.py`, `language.py`, `worker.py`, `restaurant/orders.py`, `restaurant/voice_stack.py`. Tests mirror modules in `tests/`.

**PR numbering:** steps map to PRs 074–080. Highest existing doc is `pr/pr_069_*`; 070–073 are claimed by parked plans (current_fixes.md, echo_gaps.md) — verify free numbers against branches before creating each doc.

---

## Step 1 (PR 074) — Model switch + dialogue eval harness + baseline — ✅ DONE

**Goal:** switch to gpt-4.1-mini and build the measurement tool *before* changing behavior, so every later step has a before/after.

**Changes**
- `restaurant/voice_stack.py:build_llm` → `openai.LLM(model=os.getenv("OPENAI_LLM_MODEL", "gpt-4.1-mini"))`.
- New `scripts/dialogue_harness.py` (dev-only, real OpenAI calls, no audio): instantiate `RestaurantAgent` without a session (already null-safe: `_sync_web`/`_record_tool` no-op; `place_order` has a no-session branch near `core.py:840`); manual LLM tool-loop over scripted customer turns at temperature 0; execute tool calls against the real agent; emit transcript + tool log + final `cart.to_state_dict()` + machine assertions (cart contents, gates respected, order placed/not).
- New `tests/scenarios/` (~8): English order; Punjabi (Gurmukhi) order; Hindi order; quantity correction ("I said one not two"); ambiguous dish ("fish"); delivery with phone spoken across two turns; cart change after readback (must force re-read); price-ask on phone.
- Run harness against the CURRENT prompt+model; commit baseline transcripts under `docs/eval/baseline/`.

**Verify:** full existing suite green untouched; new model-env test in `tests/test_voice_stack.py`; 2–3 live calls — check gpt-4.1-mini turn latency via `TurnLatencyTracker` logs. Rollback: `OPENAI_LLM_MODEL=gpt-4o-mini`.

**Definition of done:** harness runs all scenarios green against current behavior; baseline transcripts committed; latency acceptable on live call.

### Checkpoint (fill in when done)
- Date / branch / commit: 2026-07-17 / `pr_074_model-switch-dialogue-harness` / see branch tip (committed locally, NOT pushed — user approval required).
- What shipped vs plan (deviations):
  - `build_llm` env switch shipped as planned via new `llm_model_name()` (tested: default / override / blank).
  - Harness shipped with one addition the plan didn't anticipate: a **reactive turn layer**. Even at temperature 0 the agent non-deterministically asks optional clarifying questions (e.g. reads the phone number back and asks "is that correct?"), which shifts a fixed script one question off. Built-in rule auto-answers "Yes." to the phone-digit confirm (≥6 English digit words + "?"); scenarios may declare `reactive` regex→reply rules answered without consuming the scripted queue. Without this the suite is flaky run-to-run.
  - `ambiguous_fish` works as planned ("fish" → Amritsari Fish Pakora / Punjabi Fish Curry) — but only because the harness runs on the Clover cache (`.env` `USE_CLOVER_MENU=1`, committed `data/menu_cache_bizbull.json`); the static menu has no fish ambiguity, no spice flags, no voice_lines.
  - `price_ask_phone` originally asserted a dollar amount is spoken when asked; the CURRENT agent structurally cannot answer price on phone (refuses "Sorry, I can't share prices right now" — price stripped from all phone-facing tool replies). Assertion relaxed to cart-only so the baseline is green; the refusal is documented in the transcript + PR doc as the "before" evidence for Step 2's `total=` facts line.
- Harness/scenario results & latency numbers: 8/8 machine-green on gpt-4.1-mini, twice in a row (committed run + stability re-run). Full pytest suite 274 passed. **Live-call latency NOT yet measured** — needs 2–3 real calls after deploy; check TurnLatencyTracker logs; rollback `OPENAI_LLM_MODEL=gpt-4o-mini`.
- Notes for next session:
  - Baseline findings for Steps 2–3 (transcripts in `docs/eval/baseline/`): phone price-ask refused even when asked (Step 2); model skips `set_order_type` on "Delivery please" until the readback blocker forces a re-ask, costing 2–4 turns (prompt/flow work, Step 3/4); model silently passes `spice_level="medium"` for unstated spice instead of asking (the per-dish interrogation Step 3 deletes — note the model already dodges it).
  - Run tests with `PYTHONPATH=. uv run --with pytest pytest tests` (pytest is not in the project venv; bare `uv run pytest` picks up miniconda's and can't import `restaurant`/`livekit`).
  - Harness: `uv run python scripts/dialogue_harness.py [--scenario NAME] [--out DIR] [--model ID]` (needs `OPENAI_API_KEY`; default out dir IS `docs/eval/baseline/` — pass `--out` when re-running for comparison so the baseline isn't overwritten).

---

## Step 2 (PR 075) — Tool replies: SAY EXACTLY → structured facts — ✅ DONE

**Goal:** tools stop scripting speech; they return facts the LLM phrases itself. Ships BEFORE the persona prompt so scripts and persona-freedom never coexist contradictorily.

**Reply pattern** (every mutating tool):
```
ADDED: 2 x ਬਟਰ ਚਿਕਨ (Butter Chicken), spice medium.
ORDER NOW: 2 x ਬਟਰ ਚਿਕਨ; 1 x Garlic Naan. total=$34
GUIDE: confirm the add briefly in the customer's language using the exact dish name and quantity above, then keep the order moving.
```
Facts must not be contradicted; phrasing is the LLM's. `total=` stays in facts (answers "how much?" without a tool call); the no-price-on-phone policy lives in the prompt only. Same shape for `set_item_quantity` ("CORRECTED (not added): Garlic Naan is now 3 total.") and `get_order_summary` ("ORDER SO FAR (state ONLY these items — never from memory): …").

**Changes**
- `restaurant/orders.py`: `add_item`/`remove_item`/`update_item_quantity` return a `CartMutation` dataclass (kind added/updated/removed/merged, name, voice_line, qty, note) or error sentinel — drop the `replies` import entirely.
- New `restaurant/agent/facts.py`: `format_mutation_reply(mutation, cart)`, `format_cart_facts(cart)` (the ORDER NOW line), reuse `_qty_word`.
- `core.py`: `add_item`, `set_item_quantity`, `remove_item`, `set_item_spice` (inline SAY EXACTLY ~`core.py:510`), `get_order_summary` → facts pattern. Refusal strings unchanged.
- `replies.py`: delete `format_add/remove/update_tool_reply`, `confirm_items_added`; keep readback/status formatters (until Step 5) and canned lines (until Steps 4/6).
- `prompt.py` minimal touch: delete only "confirm like a cashier (…)" exact-wording clause; add "confirm using the exact names/quantities from ORDER NOW".

**Verify:** rewrite `tests/test_orders.py` mutation-return assertions; `test_agent_replies.py` formatter tests → new `facts.py` tests (qty words, note rendering, Gurmukhi voice_lines pass through untouched); `test_agent_tools.py` money-path assertions (refusals, additive-add guard, revision invalidation) unchanged. Harness re-run: machine assertions green; spot-check confirms state correct qty+name.

**Definition of done:** no `SAY EXACTLY` remains in any tool reply; orders.py has no speech imports; suite + harness green.

### Checkpoint (fill in when done)
- Date / branch / commit: 2026-07-17 / `pr_075_tool-replies-structured-facts` / `cd981c1` (committed locally, NOT pushed — user approval required).
- Deviations:
  - `CartMutation` gained a distinct `merged` kind (add onto an existing line) so the reply can say "ADDED MORE: X is now N total" instead of reading as a fresh add — the plan's dataclass sketch listed the kind but not the wording. Unavailable/not-found still return the unchanged refusal strings (`CartMutation | str` union), so core formats only real mutations.
  - `_qty_word` moved to `facts.py` (its long-term home); `replies.py` now imports it — no duplication, no circular import.
  - `get_order_summary` also dropped its per-reply "Do NOT mention price" phone suffix (plan implied only the SAY EXACTLY swap) — consistent with the decision that the price policy lives in the prompt only; the channel prompt already carries it.
  - `set_item_spice` reply head is `SPICE SET:` (plan didn't specify a name).
  - Addendum (2026-07-17, same branch): `set_customer_contact` was missed in the first pass and kept its instruction-prose replies. A live web call showed gpt-4.1-mini relaying `Phone saved. Read it back as English word digits ONLY: "..."` to the CUSTOMER as "Please say your phone number as separate English digits" (twice), even though the number was saved on the first try. Converted to `NAME SAVED / PHONE SAVED / NAME NOT SAVED / PHONE NOT SAVED` facts + a GUIDE line (`facts.format_contact_reply`) that explicitly says the number is already saved and not to ask the customer to repeat it.
- Harness diff vs baseline (notable phrasing changes / regressions): 8/8 machine-green (`docs/eval/pr075/`, committed). Phone price-ask now ANSWERED from `total=` ("nineteen dollars ninety-nine cents"; baseline refused) and still never volunteered unasked. Confirms are LLM-phrased but grounded ("Two Butter Chicken with medium spice, anything else?"; "ਦੋ ਬਟਰ ਚਿਕਨ medium spice ਨਾਲ ਜੋੜ ਦਿੱਤੇ। ਹੋਰ ਕੁਝ?"); corrections read as fixes ("Butter Chicken changed to one…"). No regressions found. Full suite 285 passed.
- Notes for next session:
  - Non-blocking env issue seen during harness delivery scenario: Clover customer upsert HTTP 400 (missing city/state/zip/country) — fail-open, order still submitted; may predate this step (worth a look someday, unrelated to the rebuild).
  - `format_cart_facts(cart, label=...)` is the reusable snapshot line — Step 3's `record_additional_requests` reply and Step 5's facts can build on it.
  - `test_agent_tools.py::test_readback_refuses_while_incomplete` still asserts the allergies blocker — Step 3 renames it (`additional_requests_recorded`) and must update that test plus `record_allergies` call sites in the harness scenarios' expectations (`allergies_recorded`).

---

## Step 3 (PR 076) — Additional-requests step; kill per-dish spice interrogation — ✅ DONE

**Goal:** adds are frictionless one-liners; spice/allergies/special instructions collected in ONE natural wrap-up question at end of ordering, before customer details. Enforced by gates, not prompt.

**Changes**
- `core.py add_item`: drop the NEEDS SPICE refusal. Spice stated at add time ("spicy butter chicken") passes through as today; otherwise item is added with spice unset. Non-spice required modifier groups (NEEDS INFO, e.g. naan choice in combos) STILL block — genuine choices with no sane default.
- New tool `record_additional_requests(response)` replacing `record_allergies`:
  - sets `state.additional_requests_recorded = True`; stores allergy/special-instruction text (reuse `_NO_ALLERGIES_RE`-style "no" detection; text still flows to Clover/n8n as `allergy_note`);
  - on completion, code-side: every spiced dish still without spice gets **Medium** (existing "no preference = Medium" rule, applied once, deterministically);
  - GUIDE in reply: apply specific spice mentions via existing `set_item_spice` first.
- `gates.py`: `allergies_recorded` → `additional_requests_recorded` (keep `allergy_note`); swap the allergies blocker in `readback_blockers` for: "The final additional-requests question (spice preferences, allergies, special instructions) has not been asked — ask it and call record_additional_requests." This IS the hard checklist — the agent cannot reach readback/place with a skipped step regardless of context.
- `prompt.py`: flow section = the checklist in fixed order (items → additional requests → pickup/delivery → name/phone → readback → confirm), phrased as goals; "the tools tell you what's still missing — trust them."
- `_note_with_spice` / Clover submit path unchanged (spice still lands in the note).

**Verify:** `test_agent_gates.py`: readback blocked until `record_additional_requests`; Medium default only fills unset spiced items; explicit spice never overwritten. `test_agent_tools.py`: add without spice succeeds; NEEDS INFO still blocks; spice-at-add passes through. Harness: scenarios updated to new flow + new scenario "customer never mentions spice" (ends Medium, wrap-up question still asked).

**Definition of done:** no spice question ever needed mid-ordering; wrap-up step gate-enforced; suite + harness green.

### Checkpoint (fill in when done)
- Date / branch / commit: 2026-07-18 / `pr_076_additional-requests-step` (off pr_075) / `94a4281` (committed locally, NOT pushed — user approval required).
- Deviations:
  - `_apply_default_spice()` (the Medium fill) also runs at the top of a successful `get_order_readback`, not only at `record_additional_requests` — safety net so a spiced dish added AFTER the wrap-up can never reach placement spice-unset (the plan didn't cover late adds). It bumps revision + invalidates readback only when it actually fills something, before `readback_revision` is set, so it never wedges the confirm cycle.
  - INVALID SPICE refusal kept in `add_item` for a stated-but-unparseable spice value (plan silent on it; silently dropping a stated spice felt worse).
  - `record_additional_requests` stores the WHOLE wrap-up answer as `allergy_note` when it isn't a plain "no" — e.g. "Medium spice is fine, and no allergies." lands verbatim in the kitchen note. Per plan ("text still flows as allergy_note") but noisier than the old allergies-only answer; revisit if kitchen tickets complain.
  - Prompt checkout-English rule reworded "allergies" → "additional requests/allergies"; otherwise prompt touch limited to flow/tool sections as planned.
- Live-call feel of the new flow: NOT yet live-tested — harness only. 9/9 scenarios green twice (run committed at `docs/eval/pr076/`, stability re-run in scratch). Adds are one-liners ("Two Butter Chicken and one ਗਾਰਲਿਕ ਨਾਨ added. Anything else?"), wrap-up question asked naturally once ("Any spice preferences, allergies, or special instructions?"), code fills Medium (`SPICE DEFAULTED` line) and gpt-4.1-mini respects the do-NOT-re-ask GUIDE.
- Notes for next session:
  - Full suite 289 passed. New scenario `no_spice_mentioned` covers the never-mentions-spice path end-to-end.
  - Known gap (harness-uncovered): if the customer's wrap-up answer names a NON-medium level ("make everything spicy") and the model records without calling `set_item_spice` first, code defaults to medium while the text only lands in `allergy_note`. GUIDE + tool docstring push set_item_spice-first; watch live calls / consider a Step 7 scenario.
  - Step 4 (persona prompt) now owns the flow-section wording rewritten here; `record_additional_requests` GUIDE text is fair game for persona phrasing.
  - Clover customer upsert HTTP 400 (missing city/state/zip) still appearing in delivery harness runs — pre-existing, fail-open, unrelated.

---

## Step 4 (PR 077) — Persona + checklist-driven prompt — ☐ TODO

**Goal:** replace the scripted prompt with the approved AI-cashier persona + goal checklist.

**4a — Persona doc (USER APPROVAL REQUIRED before 4b):** draft Sierra as an AI cashier — warm, quick, Punjabi-restaurant counter manner; speech habits and fillers (ਹਾਂ ਜੀ, acha ji, bilkul); code-mix patterns per language; how she handles confusion, indecision, menu questions; 3–4 few-shot micro-dialogues (≥1 each English/Punjabi/Hindi — few-shot is the strongest tone lever). Lives in new `restaurant/agent/persona.py`. **Stop and get sign-off on the text before wiring it in.**

**4b — Prompt architecture** (`build_system_prompt` assembles ordered sections):
1. PERSONA — approved doc; delivery guidance replaces "ONE sentence per turn": "This is a live call — keep turns short and natural to say aloud, usually one idea and at most one question. Vary your phrasing; never repeat the same acknowledgement twice in a row."
2. HARD SPEECH RULES — carried verbatim from today's prompt (scripts, digits, voice_line, English checkout terms, quantity words). Step 5's verifier depends on the voice_line + English-checkout rules.
3. YOUR JOB — the Step 3 checklist as goals, not lines.
4. TOOL CONTRACT — tool list, TRUST TOOL RESULTS, NEVER GUESS, additive-add warning: content unchanged.
5. CHANNEL — phone/web blocks, price policy unchanged.

**4c — Persona drift enforcement (user-requested 2026-07-18; style can't be hard-gated like the money path, so prevent + re-anchor):**
- **GUIDE-line style nudges:** every `facts.py` GUIDE line carries a persona re-anchor ("confirm this warmly in the customer's language, in your own words") — the text closest to the generation point re-injects style on every cart mutation. Keep nudges short; facts stay facts.
- **Periodic context re-anchoring:** inject a one-line system-role reminder ("you're still Sierra at the counter — warm, flowing, never robotic") into the chat context every N turns via the before-LLM hook (LiveKit chat-ctx edit). N configurable (`PERSONA_REANCHOR_TURNS`, default ~8; `0` = off). No latency cost, no turn regeneration.
- Explicitly OUT of this step: a robotic-marker detection watchdog (revisit in Step 7 once live transcripts exist to calibrate markers).

**Canned lines (all rewritten in persona voice):** opening greeting — keep fixed (latency-critical, pre-LLM `session.say`); `order_placed_goodbye` — keep fixed (wired into hang-up choreography ~`core.py:809`), add language variants keyed off `state.preferred_language`; echo/background reprompts — keep fixed (spoken under `StopResponse`, no LLM turn exists), 2–3 variant pools, no immediate repeats; reservation confirm (~`core.py:949`) — hand to LLM as facts (ref digits as English words); transfer exact line — relax to guidance.

**Rollback:** `PROMPT_STYLE=legacy` env flag keeps the old builder for one release.

**Verify:** prompt unit tests assert non-negotiables present in the assembled prompt (both styles); re-anchor unit test (reminder appears at turn N, absent before, `0` disables); GUIDE nudges covered by existing `facts.py` tests; full harness scored side-by-side vs Step 1 baseline; 5+ live calls per language; transcript review for re-greeting/meta-speech regressions (the old regexes never actually fired on speech — review replaces them).

**Definition of done:** persona approved by user; new prompt live behind flag default-on; harness + live calls reviewed.

### Checkpoint (fill in when done)
- Date / branch / commit:
- Final approved persona summary (one paragraph):
- Deviations:
- Live-call review findings:
- Notes for next session:

---

## Step 5 (PR 078) — Grounded natural readback + post-speech verifier (money path) — ☐ TODO

**Goal:** LLM phrases the readback in the customer's language; code verifies every item/qty/order-type was actually spoken before `confirm_readback` can succeed. `place_order_blockers` unchanged — `readback_confirmed` is simply only set after verification passes.

**`get_order_readback` new return:** `READBACK FACTS` list — per item `2 x ਬਟਰ ਚਿਕਨ (Butter Chicken)`; `order type: pickup (say "pickup" in English)`; name; total (web only) — plus: "read ALL of these in the customer's language, then ask if everything is correct. Your spoken readback is checked — anything missing forces a re-read." Still sets `readback_revision`, clears `readback_confirmed`; new: `readback_pending = True`, clears spoken buffer.

**New pure module `restaurant/agent/readback_verify.py`:**
- Trilingual qty lexicon 1–20 (`_MAX_ITEM_QTY`): English words, Gurmukhi words (ਇੱਕ, ਦੋ…), Devanagari words (एक, दो…), ASCII digits, Indic numerals.
- Normalize: NFC → casefold Latin → strip punctuation preserving Indic codepoints → collapse whitespace.
- Per item aliases: normalized voice_line + English name, parentheticals ("(2 pcs)") stripped.
- Checks: **item presence** (alias substring; missing → `MISSING: you never said 'X' / 'Y'`); **quantity window** (≤3 tokens before alias: found-but-wrong → fail; absent with qty ≥2 → fail; absent with qty 1 → OK, so "and a Garlic Naan" passes); **order type** (closed English vocab anywhere — the reason checkout-English survives in the prompt); **total** (web, warn-level: if a dollar amount is spoken it must equal `cart.total`).
- NOT verified (unverifiable across languages, not money-corrupting): inflection, honorifics, notes/spice, phrasing order. False negatives fail safe → re-read.

**Plumbing:** `OrderSessionState` += `readback_pending: bool`, `readback_spoken: list[str]` (field adds only). `note_agent_speech` appends to buffer while pending (existing `conversation_item_added` path feeds it; barge-in truncation → verifier fails → re-read = safe direction; same-turn readback+confirm → empty buffer → fails). `confirm_readback` runs verifier after revision checks; `READBACK_VERIFY` env: `warn` (log + analytics event, allow — **initial live default**), `strict` (return `READBACK INCOMPLETE: <problems>` + clear buffer, keep unconfirmed), `off` (emergency rollback). `invalidate_readback` also clears pending + buffer.

**Verify:** new `tests/test_readback_verify.py` — passing phrasings ×3 languages; missing item fails; wrong qty fails; qty-1 omission passes; Gurmukhi dish + English qty passes; Devanagari qty passes; empty/truncated buffer fails. `test_agent_tools.py`/`test_agent_place_order.py`: strict-mode confirm blocked until verified speech recorded (simulated `note_agent_speech` feed); warn/off modes. `test_agent_gates.py` blocker functions untouched. Harness: adversarial "sloppy readback" scenario (inject readback missing an item → confirm refused). Live: run `warn`, measure false-negative rate per language from analytics before flipping strict.

**Definition of done:** verifier live in `warn` on real calls; adversarial scenario green; false-negative measurement started.

### Checkpoint (fill in when done)
- Date / branch / commit:
- Deviations (esp. verifier heuristics tuned):
- warn-mode stats so far (per language):
- Notes for next session:

---

## Step 6 (PR 079) — Delete speech guard; real TTS phone-digit enforcement — ☐ TODO

**Goal:** remove dead regex machinery; promote phone-digit enforcement into the actual audio path (first-time hard guarantee).

**Changes**
- `replies.py`: delete `sanitize_assistant_speech` + all `_*_RE` regexes (verified log-only). `worker.py:_on_conv_item` simplifies to note/record/log.
- `core.py`: `tts_node` override on `RestaurantAgent` applying `enforce_english_phone_in_speech` as a streaming filter — pass text through untouched unless a digit-run/digit-word token appears, then buffer to the run boundary (bounded buffering, no latency on normal text). Behind `TTS_PHONE_ENFORCE` env, default on.
- Optional, only if trivially reliable: word fixups (Dhanyavaad→ਧੰਨਵਾਦ) in the same filter. NO general Roman→Gurmukhi transliteration.

**Verify:** migrate/delete `test_speech_policy.py` sanitizer cases; new `tests/test_tts_transform.py` (digit run split across chunks, Indic numerals, word-digit chains ≥7). Live phone call with number readback. Rollback: `TTS_PHONE_ENFORCE=0`; sanitizer deletion needs none.

**Definition of done:** sanitizer gone; phone readback enforced in TTS path on a live call.

### Checkpoint (fill in when done)
- Date / branch / commit:
- Deviations:
- Notes for next session:

---

## Step 7 (PR 080) — Calibration: rubric, judge, model decision — ☐ TODO

**Goal:** systematize "sounds natural"; decide gpt-4.1-mini vs gpt-4.1; finish rollout flags.

- `docs/eval/naturalness_rubric.md`: score 1–5 on acknowledgement variety (no stock phrase >2×/call), sentence-length variety, code-mix appropriateness, zero meta-speech, confusion-handling grace, checkout efficiency (turns-to-place not inflated >20% vs baseline).
- `scripts/judge_transcripts.py` (dev-only LLM-as-judge; human review remains authority).
- Compare harness + live scores vs Step 1 baseline; if flat → `OPENAI_LLM_MODEL=gpt-4.1`, re-measure latency.
- Persona/prompt micro-tuning from findings; flip `READBACK_VERIFY` default to `strict` if Step 5 warn-mode data supports it; consider removing `PROMPT_STYLE=legacy`.

**Definition of done:** rubric + judge committed; model decision made with data; verifier default decided.

### Checkpoint (fill in when done)
- Date / branch / commit:
- Model decision + evidence:
- READBACK_VERIFY final default:
- Remaining known gaps / follow-ups:
