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

**Status: 4a — persona draft awaiting user approval. No prompt wiring yet.**

## Files Added
### `restaurant/agent/persona.py`
The Sierra persona document: who she is (AI cashier, no fake-human backstory), counter manner,
per-language code-mix patterns, confusion/indecision/menu-question handling, and four few-shot
micro-dialogues (English / Punjabi / Hindi / indecision). Drafted by Claude; **must be user-approved
before it is wired into the prompt (4b)**.

## Files Modified
(4b — pending persona approval)
### `restaurant/agent/prompt.py`
`build_system_prompt` becomes an ordered-section assembler; legacy builder behind `PROMPT_STYLE=legacy`.
### `restaurant/agent/replies.py` / `restaurant/agent/core.py`
Canned lines rewritten in persona voice; goodbye gets language variants; echo/background reprompt
variant pools; reservation confirm handed to LLM as facts; transfer line relaxed to guidance.
Core also gains the periodic persona re-anchor (before-LLM chat-ctx injection every
`PERSONA_REANCHOR_TURNS` turns).
### `restaurant/agent/facts.py`
GUIDE lines gain short persona style nudges ("confirm this warmly in the customer's language,
in your own words") — facts stay facts.

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
