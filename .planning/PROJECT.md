# Human Conversation Rebuild — Order Taking Assistant

## What This Is

A voice-ordering agent for a Punjabi restaurant (LiveKit phone/web, Soniox STT, OpenAI GPT) that currently talks from a rigid, rule-scripted prompt (one-sentence-per-turn, fixed order flow, exact confirm phrasing, banned phrases). This milestone rebuilds the conversational layer so the LLM owns *how* it talks — persona-driven, natural, human — while code/tools continue to own everything about the order that must never be wrong: items, quantities, customizations, allergies, customer contact info.

## Core Value

The conversation must sound and feel genuinely human — natural pacing, no script, no robotic phrasing — while the actual order data stays 100% reliable, because it is owned by tool calls and gates, never trusted from LLM free-form output.

## Requirements

### Validated

- ✓ Hybrid architecture: LLM talks, code owns the cart — existing (PRs 059–062, "hybrid rebuild")
- ✓ Tool-based order mutation (add_item, set_item_quantity, set_item_spice, remove_item, record_allergies, set_order_type, set_delivery_address, set_customer_contact) — existing
- ✓ Business-rule gates (place_order_blockers, readback_blockers) as pure, stateless validation — existing (`restaurant/agent/gates.py`)
- ✓ Multi-language support — English/Punjabi/Hindi code-mixing via Soniox STT — existing
- ✓ Turn watchdog / noisy-environment end-of-speech handling — existing (PRs 065–069)
- ✓ Phone (SIP) and Web (WebRTC) channels via LiveKit audio bridges — existing
- ✓ Three parked bugs resolved as prerequisite hardening (menu-hint fuzzy-match false positive "Singh"→"single", phone word-digit STT normalization, echo/background filter false positives), plus per-turn latency observability surviving filter-dropped turns — Phase 1 (HYG-01–04)

### Active

- [ ] Replace rigid, rule-scripted `prompt.py` with a persona-driven prompt — deepen the existing "Sierra" host character (backstory, personality, natural voice) instead of prescribing exact lines
- [ ] Drop hard turn-structure constraints (one sentence / one question per turn) — let the LLM pace conversation naturally
- [ ] Keep TTS-pronunciation-correctness rules as hard constraints, not persona scripting: Punjabi/Hindi must render Gurmukhi/Devanagari (never Roman), phone digits must be spoken as English words
- [ ] Redesign turn-handling flow (`restaurant/agent/core.py`) so the LLM owns conversational direction; only tools can mutate order-critical data
- [ ] Reshape tool contracts if a more natural flow calls for it (open to change — not required to preserve current tool shapes)
- [ ] Give the LLM conversational context each turn: full transcript history AND a structured order-state summary (both, not one or the other)
- [ ] Validate success via live call testing — the bar is a real phone/web call that feels human, not a transcript rubric

### Out of Scope

- Exact scripted response templates / fixed phrasing — this is precisely what's being removed, reintroducing it defeats the goal
- Menu/POS integration changes — untouched by this rebuild
- New payment methods (e.g. card payment) — not part of this milestone unless raised separately

## Context

- The prior "hybrid rebuild" (PRs 059–062, `refactor.md`) already established "LLM talks, code owns cart," but the prompt itself stayed heavily rule-scripted: forced one-sentence turns, a fixed ORDER FLOW sequence, exact confirm phrasing ("Yes — one X and one Y", never "I've added"), and a long NEVER list. That's the layer this milestone tears out.
- PR 030 lesson (carried forward): prompt-only rules regress on live calls — money-path guarantees must live in code/tools/gates, not prompt text. This rebuild applies that lesson in the other direction too: loosen persona/tone freely, but order correctness stays strictly code-owned.
- Three previously parked bug-fix plans (menu-hint bug, phone-digits bug, echo/background filter false positives — tracked in `current_fixes.md` / `echo_gaps.md`) are expected to be resolved as a byproduct of this rebuild rather than as standalone fixes.
- Turn watchdog / noisy-environment end-of-speech infra (PRs 065–069) is not being rebuilt here, except where it interacts with natural (non-rigid) turn-taking.

## Constraints

- **Correctness**: Order data (items, quantities, customizations, allergies, customer contact) must never be corrupted by LLM hallucination — enforced through tool calls and gates, never trusted from free-form LLM output.
- **TTS pronunciation**: Punjabi/Hindi output must render in Gurmukhi/Devanagari (never Roman script); phone digits must always be spoken as English words. Non-negotiable regardless of persona freedom — these are TTS-engine correctness requirements, not scripting.
- **Tech stack**: LiveKit (SIP/WebRTC audio bridges), Soniox STT, OpenAI GPT — existing stack, no indication this milestone changes it.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Full replacement of prompt.py's rule-scripted flow with a persona-driven prompt | Current script reads as robotic; goal is natural, human conversation | — Pending |
| Drop the one-sentence/one-question-per-turn constraint entirely | Real conversation doesn't follow a rigid turn structure | — Pending |
| Keep TTS/pronunciation rules (script, digit-reading) as hard constraints | These are correctness constraints for the TTS engine, not personality scripting | — Pending |
| Feed the LLM both full transcript history and a structured order-state summary each turn | Natural memory plus reliable state grounding, not one or the other | — Pending |
| Tool contracts open to reshaping if a more natural flow needs it | Current tool shapes were designed around the old rigid flow; not assumed to be final | — Pending |
| Fold the 3 parked bugs into this rebuild instead of separate PRs | Rebuild is expected to naturally resolve them (e.g. natural phone-digit speech, less rigid echo filtering) | — Pending |
| Success measured via live call test, not transcript rubric | User will personally judge naturalness by talking to the agent | — Pending |
| Menu-hint veto needs a confidence floor (0.8), not a bare presence check | A 0.65-confidence fuzzy match ("Singh"→"Bhatura (single)") was vetoing valid customer names; gating on confidence fixes precision without touching the order/menu-match path | ✓ Phase 1 |
| Background-drop reprompt threshold drops to 1 (from 3) when a question is pending | A single false-positive drop right after a question must not cause dead air while waiting for a 3-drop streak | ✓ Phase 1 |
| `_SPOKEN_DIGIT_WORDS` map wired into STT input direction, not just TTS output | Dictated phone numbers as words (English/Hindi/Punjabi/Gurmukhi/Devanagari) were stripped to zero digits by `extract_phone_digits`, causing an infinite rejection loop | ✓ Phase 1 |
| Turn latency tracker forces a fresh slice on each new user utterance | A filter-dropped turn (`StopResponse`) left `_turn_active` stuck `True`, corrupting the next real turn's latency measurement | ✓ Phase 1 |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-07-15 after Phase 1*
