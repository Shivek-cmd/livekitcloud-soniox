# PR 048 — Allergies-step false positive on complaint/meta-question

## Branch
`pr_048_allergies-meta-question-guard`

## Problem (live call, 2026-07-06, found while verifying PR 047 on the deployed VPS)

Caller pushed back after being asked allergies without their prior question ever
being answered:

```
Sierra: "Any allergies or special instructions?"
Caller: "Did you understand what I asked you? Like, why are you asking for
         allergies and special instructions?"
```

`is_allergies_step_answer()` has:

```python
if "allerg" in t or "ਐਲਰਜੀ" in text:
    return True
```

This is an unconditional substring check — it fires whenever the word
"allergy/allergies" appears **anywhere**, including a caller complaining about
being asked, not just an actual answer. Same root pattern as the `_NO_RE` bug
fixed in PR 047 (unanchored keyword matching mistaken for intent), just a
different line in the same function that PR 047 didn't touch.

Verified directly: `is_allergies_step_answer(complaint_text, GENERAL)` returned
`True` before this fix.

## Fix

### `restaurant/conversation.py`
- New `_META_QUESTION_RE` — matches a literal `?` anywhere, or a leading
  why/what/did-you/are-you/should-you/you-should-not — i.e. question-shaped
  pushback directed at the assistant.
- `is_allergies_step_answer()`'s `"allerg"` substring check now also requires
  `not _META_QUESTION_RE.search(text)`, so a genuine allergy mention ("I have a
  peanut allergy", "ਮੈਨੂੰ ਐਲਰਜੀ ਹੈ...") still counts, but a complaint/question
  about being asked does not.

### `tests/test_conversation.py`
- `test_allergies_complaint_is_not_an_answer` — reproduces the exact live-call
  complaint, asserts it's no longer treated as an answer.
- `test_real_allergy_mention_still_counts_as_answer` — English + Gurmukhi
  positive allergy mentions still return `True` (no regression).

## What's NOT in This PR

- Does not address the separate compound-utterance gap also found in this
  call ("no [more items], but do you have sarson da saag?" — the trailing
  question never gets answered because only one intent is extracted per
  utterance). That's a bigger architectural question, not a one-line fix.
- Does not address the pre-existing `is_likely_background_speech()` filter
  dropping genuine hesitant speech as noise (separate module, separate bug).
- No broader audit of every loose-substring check in `conversation.py` — this
  PR fixes the one confirmed instance found live; a fuller audit can be a
  follow-up if more of these surface.

## How to Test

```bash
PYTHONPATH=. pytest tests/test_conversation.py tests/test_order_flow.py -q
```

Live: at the allergies step, say something that mentions the word "allergies"
as a complaint/question (not an answer) — confirm Sierra does not silently
advance to pickup/delivery.

## Post-Merge: VPS Pull Command
`cd /opt/livekit-sarvam && git pull origin main && uv sync`
