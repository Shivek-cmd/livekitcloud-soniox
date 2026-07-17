# PR 077 — Persona + checklist-driven prompt (Step 4 of Human Conversation Rebuild)

## Branch
`pr_077_persona-checklist-prompt`

## What This PR Does
Replaces the scripted system prompt with the approved Sierra AI-cashier persona plus an
ordered-section prompt architecture (PERSONA / HARD SPEECH RULES / YOUR JOB / TOOL CONTRACT /
CHANNEL). The persona owns tone, code-mix habits, and delivery guidance ("keep turns short and
natural" replaces "ONE sentence per turn"); the hard TTS-correctness rules, tool contract, and
flow checklist carry over unchanged in content. Canned code-spoken lines (goodbye, echo/background
reprompts, reservation confirm, transfer line) are rewritten in persona voice. Old prompt builder
kept behind `PROMPT_STYLE=legacy` for one release.

Also adds persona drift enforcement (4c): style nudges in every `facts.py` GUIDE line
(re-anchors persona at the generation point on each cart mutation), and a periodic one-line
system-role persona reminder injected into the chat context every N turns via the before-LLM
hook (`PERSONA_REANCHOR_TURNS`, default ~8, `0` = off). A robotic-marker detection watchdog is
deliberately deferred to Step 7 (needs live transcripts to calibrate).

**Status: shipped (4a approved 2026-07-18; 4b+4c implemented). Harness 9/9 ×2; live-call
review per language still pending.**

## Files Added
### `restaurant/agent/persona.py`
The Sierra persona document: who she is (AI cashier, no fake-human backstory), counter manner
(fuller flowing sentences per user feedback), per-language code-mix patterns,
confusion/indecision/menu-question handling, and four few-shot micro-dialogues
(English / Punjabi / Hindi / indecision) — user-approved. Post-approval functional amendment
(spoken lines untouched): `[tools: …]` annotations inside the micro-dialogues, because
dialogue-only examples deterministically taught gpt-4.1-mini to add just the FIRST of several
named dishes and chat about the rest (harness `no_spice_mentioned` failed until annotated).
Also home to Step 4c: `PERSONA_REANCHOR_LINE` + `persona_reanchor_turns()`
(`PERSONA_REANCHOR_TURNS`, default 8, 0=off).
### `tests/test_prompt.py`
Non-negotiables asserted in BOTH styles; channel blocks; persona/legacy content; env parsing;
re-anchor injection (fires at N, not before; 0 disables; skipped in legacy style).

## Files Modified
### `restaurant/agent/prompt.py`
`build_system_prompt` assembles ordered sections (PERSONA → HARD SPEECH RULES → YOUR JOB →
TOOL CONTRACT → CHANNEL); `prompt_style()` reads `PROMPT_STYLE` (legacy keeps the old prompt
verbatim, incl. old exact transfer line, for one release). New persona-style-only bullet in
NEVER GUESS: several dishes named in one turn are ALL added before speaking.
### `restaurant/agent/replies.py`
`order_placed_goodbye(order_type, language)` — en/hi variants, Punjabi default for pa/mixed/unknown;
echo/background reprompts became 3-variant pools with no-immediate-repeat.
### `restaurant/agent/core.py`
Periodic persona re-anchor injected in `on_user_turn_completed` every N real turns (system-role
line via `turn_ctx.add_message`, persona style only); goodbye call passes `preferred_language`;
`book_reservation` returns RESERVATION BOOKED facts + GUIDE (ref spoken char-by-char, digits as
English words); `transfer_to_human` returns TRANSFER STARTED + GUIDE instead of prose; GUIDE
lines of set_item_spice / record_additional_requests / get_order_summary carry style nudges.
### `restaurant/agent/facts.py`
`_mutation_guide` GUIDE lines carry persona style nudges ("warm and in your own words, never
reading these lines aloud") — facts stay facts.
### `restaurant/channels/phone_echo.py`
Added "take your time" to `_RECOVERY_ECHO_PHRASES`. Deliberately NOT adding caller-plausible
pool fragments ("one more time", "ਇੱਕ ਵਾਰ ਫਿਰ", "a little noisy") — a caller asking us to
repeat must never be dropped (PR 073 lesson); full-line echoes are caught via `_recent_agent_lines`.
### `tests/test_agent_replies.py`
Goodbye language-variant tests; pool no-immediate-repeat; pool lines filtered as echo of self.
### `docs/eval/pr077/`
Harness run vs the persona prompt: 9/9, committed.

## Files Deleted
None.

## What's NOT in This PR
- Readback verifier (Step 5 / PR 078); speech-guard deletion + TTS digit enforcement (Step 6 / PR 079).
- No tool/gate/flow changes — Step 3's checklist and gates are consumed as-is.

## How to Test
```
PYTHONPATH=. uv run --with pytest pytest tests
uv run python scripts/dialogue_harness.py --out /tmp/pr077_run
```
Prompt unit tests assert non-negotiables present in both prompt styles; harness compared
side-by-side vs `docs/eval/baseline/`; 5+ live calls per language reviewed for re-greeting /
meta-speech regressions.

## Post-Merge: VPS Pull Command
`cd /opt/livekit-sarvam && git pull origin main && uv sync`
