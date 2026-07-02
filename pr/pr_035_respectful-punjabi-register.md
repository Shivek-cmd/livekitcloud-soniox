# PR 035 — Respectful Punjabi/Hindi register (fixes informal ਤੂੰ / तू)

## Branch
`pr_035_respectful-punjabi-register`

## Status
✅ **Ready for review** — implementation complete on branch `pr_035_respectful-punjabi-register`.

## The bug (live transcript, 2026-07-02)

Sierra mixed **formal** and **informal** second-person address in the same call:

| Turn | Line | Problem |
|------|------|---------|
| 3 | "ਤੂੰ ਕਿਹੜੀ ਮਸਾਲੇ ਦੀ ਪਸੰਦ **ਕਰੇਗਾ**?" | Informal **ਤੂੰ** + singular verb |
| 4 | "ਤੁਸੀਂ… **ਦevੋਗੇ**?" | Correct formal |
| 11 | "**ਤੇਰਾ** ਆਰਡਰ ਪੜ੍ਹ ਕੇ ਦੱਸਦੀ ਹਾਂ" | Informal possessive **ਤੇਰਾ** |

In a Canadian restaurant phone order, unknown callers must always get **ਤੁਸੀਂ / ਤੁਹਾਡਾ / ਜੀ**
(Punjabi) or **आप / आपका** (Hindi). **ਤੂੰ / तू** reads as rude or overly familiar.

Root cause: prompts say "natural warm Gurmukhi" but never **require** formal register.
Conversational LLM turns are unguarded; code-owned templates (goodbye, name question)
already use respectful forms.

## What This PR Does

### 1. Prompt + per-turn guidance (soft guard)

`prompts.py` and `language_turn_guidance()` add a mandatory **REGISTER** rule with
good/bad examples. Transfer line fixed: Sierra speaks **ਕਰ ਰਹੀ ਹਾਂ** (female), not **ਕਰਦਾ ਹਾਂ**.

### 2. `restaurant/respect_speech.py` — output guard (hard guard)

`apply_respectful_register(text)` runs in `sanitize_assistant_speech()` before TTS:

- Gurmukhi: ਤera/ਤeri/ਤੇਰੇ → ਤੁਹਾਡ-* ; ਤenu → ਤੁਹਾਨੂੰ ; ਤੂੰ → ਤੁਸੀਂ
- Hindi: तera/तum forms → आप-* ; तू → आप
- Common informal customer-directed verbs → respectful plural (ਕਰੇਗਾ → ਕਰੋਗੇ, etc.)

Longest-match-first string replacements — same pattern as existing script-slip fixes.

### 3. Tests

`tests/test_respect_speech.py` — live-transcript regressions, Hindi, no false positives
on already-formal lines.

## Behaviour changes

| LLM output (before guard) | After guard |
|---|---|
| "ਤੂੰ ਕਿਹੜੀ ਮਸਾਲੇ ਦੀ ਪਸੰਦ ਕਰੇਗਾ?" | "ਤੁਸੀਂ ਕਿਹੜੀ ਮਸਾਲੇ ਦੀ ਪਸੰਦ ਕਰੋਗੇ?" |
| "ਤੇਰਾ ਆਰਡਰ" | "ਤੁਹਾਡਾ ਆਰਡਰ" |
| "तू क्या चाहोगे?" | "आप क्या चाहोगे?" |

## What's NOT in This PR

- Code-owned ladder speech (allergies/pickup templates) — PR 036
- Phase machine / asked-and-answered flags
- Analytics flag for informal register (optional follow-up)
- No `.env` changes; guard always on

## Files Added

### `restaurant/respect_speech.py`
`apply_respectful_register()`, `INFORMAL_REGISTER_MARKERS` (for tests).

### `tests/test_respect_speech.py`
Transcript regressions + unit tests.

## Files Modified

`restaurant/prompts.py`, `restaurant/conversation.py` — register rules + sanitize hook.

## How to Test

```bash
PYTHONPATH=. uv run pytest tests/test_respect_speech.py tests/test_conversation.py -q
PYTHONPATH=. uv run pytest tests/ -q
```

Manual: full Punjabi order — every Sierra line must use **ਤੁਸੀਂ/ਤੁਹਾਡਾ**, never **ਤੂੰ/ਤੇਰਾ**.

## Post-Merge: VPS Pull Command

```bash
cd /opt/livekit-sarvam && git fetch origin && git checkout main && git reset --hard origin/main && uv sync && systemctl restart restaurant-agent
```

## Verification checklist

- [x] Turn 3 transcript line corrected by guard
- [x] Turn 11 "ਤੇਰਾ ਆਰਡਰ" → "ਤੁਹਾਡਾ ਆਰਡਰ"
- [x] Formal lines unchanged (ਤੁਸੀਂ, ਤੁਹਾਡਾ, goodbye template)
- [x] Full suite green (minus pre-existing failures)
- [ ] Live call: no ਤੂੰ/ਤੇਰਾ in any Sierra turn
