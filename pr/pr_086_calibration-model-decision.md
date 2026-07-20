# PR 086 — Calibration: naturalness rubric, LLM judge, multi-provider model decision

## Branch
`pr_086_calibration-model-decision`

## What This PR Does
Step 7 of refactor.md (the calibration step), widened per user decision
(2026-07-19): the model comparison is no longer limited to gpt-4.1-mini vs
gpt-4.1 — Gemini models are first-class candidates. Adds Gemini wiring to the
runtime voice stack (`GEMINI_API_KEY`, `livekit-plugins-google`), makes the
dialogue harness multi-provider via Gemini's OpenAI-compatible endpoint,
commits the naturalness rubric + an LLM-as-judge scorer, and runs the
head-to-head comparison (harness pass rate, judge scores, hard-marker flags,
per-call latency) that backs the final model decision.

## Files Added
### `docs/eval/naturalness_rubric.md`
1–5 rubric: acknowledgement variety, sentence-length variety, code-mix
appropriateness, zero meta-speech, confusion-handling grace, checkout
efficiency (mechanical, ≤ baseline+20% turns-to-place). Plus hard-marker
flags from live-call findings (gap_fixes.md F1/F2): stray-language
code-switch, Roman-Indic, ungrounded dish names, fact contradictions,
meta-speech, spoken grounding parentheticals.

### `scripts/judge_transcripts.py`
Dev-only judge over harness output dirs. Mechanical checks in code (repeated
phrase counter with a cap on acknowledgement-variety, Unicode-script stray
language detector, Roman-Indic wordlist, spoken-parenthetical regex,
turns-to-place vs baseline); the judgment dimensions + semantic flags go to
an LLM judge (default `gpt-4.1`, `--judge-model` to swap) returning strict
JSON. Mechanical flag counts floor the LLM's (max-merge). Writes
`scores.json`/`scores.md` per dir + `comparison.md` across dirs. Human review
remains the authority; the judge ranks candidates and flags transcripts.

### `docs/eval/pr086/<model>/…` + `docs/eval/pr086/comparison.md`
Committed harness runs + judge scores for each candidate model.

## Files Modified
### `pyproject.toml`
Adds `livekit-plugins-google` (resolved 1.6.5, same train as the other
plugins; it handles Gemini 3 thought signatures natively — verified in
`llm.py:_requires_thought_signatures`).

### `restaurant/voice_stack.py`
`llm_model_name()` now reads provider-agnostic `LLM_MODEL` first, falling
back to `OPENAI_LLM_MODEL` (PR 074 rollback instructions keep working).
`build_llm()` routes `gemini-*` ids to `google.LLM` with
`GEMINI_API_KEY`/`GOOGLE_API_KEY` and thinking minimized by default:
Gemini 2.5 takes `GEMINI_THINKING_BUDGET` (default 0, floored at 128 for
pro ids); Gemini 3 rejects budgets and takes `GEMINI_THINKING_LEVEL`
(default "low", its minimum — live-verified: `thinking_budget` on a 3.x
model is ignored with a warning). Gemini primaries are wrapped in a
LiveKit `FallbackAdapter` with an OpenAI fallback (`LLM_FALLBACK_MODEL`,
default gpt-4.1-mini, `none` disables) with `attempt_timeout=10.0` —
Google's API-enforced minimum deadline; the adapter's 5s default 400s
every request (live-verified both ways). OpenAI-primary path unchanged.

### `restaurant/agent/readback_verify.py` (+ `tests/test_readback_verify.py`, `tests/test_agent_tools.py`)
`READBACK_VERIFY` default flipped warn → strict (user-approved 2026-07-19):
zero warn-mode verifier warnings across all 30 comparison scenario runs —
PR 084's English dish names removed the transliteration false-negatives
that had kept strict unsafe. `warn`/`off` remain explicit opt-outs.

### `scripts/dialogue_harness.py`
Multi-provider: `make_client()` sends `gemini-*` through the OpenAI-compat
endpoint with `GEMINI_API_KEY`; `completion_kwargs()` keeps `seed=7` for
OpenAI, uses `reasoning_effort` none/low for Gemini (no seed — rejected
there). Two compat fixes: the tool schema's internal `"type": "function"`
key is stripped (Gemini 400s on it), and the assistant tool-call message is
now round-tripped via `msg.model_dump()` because Gemini 3 requires its
thought signatures echoed back verbatim. Also records per-LLM-call wall time
(`llm_latency` mean/p95/max per run + summary line) as decision evidence.

### `tests/test_voice_stack.py`
Provider routing tests: `LLM_MODEL` beats `OPENAI_LLM_MODEL`; gemini ids
build `google.LLM`, gpt ids build `openai.LLM`; thinking budget default 0,
env override, invalid fallback; pro-model floor of 128 asserted via an
`__init__` spy.

## Files Deleted
None.

## Decision (user-approved 2026-07-19)
**`LLM_MODEL=gemini-3.5-flash` with gpt-4.1-mini FallbackAdapter fallback;
`READBACK_VERIFY` default strict.** Evidence (`docs/eval/pr086/comparison.md`,
judge gpt-4.1):
- Candidates compared: gpt-4.1-mini (10/10 harness), gemini-3.5-flash and
  gemini-3.1-flash-lite (9/10 each). gpt-4.1 and gemini-3.1-pro-preview were
  dropped by the user mid-comparison (gpt-4.1 also rate-limited at 30k TPM).
- gemini-3.5-flash led every naturalness dimension (ack variety 4.9 vs 4.1,
  zero spoken "(Garlic Naan)" parentheticals vs 12) and kept dish names /
  checkout terms in English inside Gurmukhi sentences — the hard rules
  gpt-4.1-mini bends. Latency parity (~1.2–1.3s/call non-streaming).
- The single Gemini failure is load-bearing: once a conversation aggregates
  name + phone + delivery address, Gemini's NON-configurable
  PROHIBITED_CONTENT filter deterministically blocked the reply
  (delivery_split_phone, 3/3 repro, both Gemini models, survives 6 retries;
  compat endpoint accepts no safety_settings — probed). Every delivery order
  reaches that state, hence the code-owned OpenAI fallback rather than
  Gemini-only.

## What's NOT in This PR
- No live-call measurements — harness + judge only; live latency/quality
  validation (and TurnLatencyTracker TTFT numbers) after deploy.
- `PROMPT_STYLE=legacy` removal — kept one more release; the persona prompt
  has still never been live-called on Gemini.
- No streaming/TTFT measurement in the harness (non-streaming calls only).

## How to Test
```
PYTHONPATH=. uv run --with pytest pytest tests -q
uv run python scripts/dialogue_harness.py --model gemini-3.5-flash --out /tmp/eval-gemini
uv run python scripts/judge_transcripts.py /tmp/eval-gemini --baseline docs/eval/baseline
```

## Post-Merge: VPS Pull Command
`cd /opt/livekit-sarvam && git pull origin main && uv sync`
(plus `GEMINI_API_KEY` + `LLM_MODEL` in the VPS `.env` if the decision lands
on Gemini)
