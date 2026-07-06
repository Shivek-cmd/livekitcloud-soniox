# PR 053 — Background-speech filter dropping real answers

## Branch
`pr_053_background-filter-menu-and-filler-fix`

## Problem (live call, 2026-07-06)

Two genuine caller answers got dropped as "background chatter":

```
Sierra: (asking which mocktail flavor)
Caller: "Blue Lagoon."             ← filtered as background

Sierra: "Any allergies or special instructions?"
Caller: "ਅਹ, ਨਹੀਂ।" (um, no)        ← filtered as background
```

Traced both directly against `is_likely_background_speech()`:

1. **"Blue Lagoon."** — tokenizes to `["blue", "lagoon"]`. The filter only
   keeps a 2-token utterance if **both** tokens are in a fixed generic
   allowlist (yes/no/pickup/hello/etc.) — neither "blue" nor "lagoon" is
   there, and never could be without hand-listing every possible dish/drink
   name, which doesn't scale.
2. **"ਅਹ, ਨਹੀਂ।"** — tokenizes to `["ਅਹ", "ਨਹੀਂ"]`. `"ਨਹੀਂ"` phonetic-folds to
   `"nhn"`, but the allowlist only had the shorter `"na"` (folds to `"n"`) —
   the fuller nahin/ਨਹੀਂ spelling had no matching entry. Even after fixing
   that, the hesitation filler `"ਅਹ"` (um) still isn't "meaningful," and the
   2-token rule requires **both** tokens meaningful — so the filler word
   itself would keep dragging a real answer down to "background."

## Fix

### `restaurant/phone_background.py`
- Added `"nahin"` to `_SHORT_MEANINGFUL` — its phonetic key (`"nhn"`) now
  matches `"ਨਹੀਂ"`, verified directly against `restaurant.clover.match.phonetic_key`.
- New `_FILLER_TOKENS` (`ah/um/uh/erm/hmm/ਅਹ/ਉਹ`) + `_drop_fillers()` — hesitation
  markers are stripped **before** the meaningful-token check instead of
  counting against it, so `"ਅਹ, ਨਹੀਂ"` reduces to `["ਨਹੀਂ"]` and is correctly
  recognized as a real answer.
- New `_looks_like_named_answer()` — a Title-Case bypass (every word
  capitalized, capped at 1–3 words) for proper-noun-style answers like "Blue
  Lagoon" or "Palak Paneer." Checked *after* `_BACKGROUND_FRAGMENT_RE`, so
  known junk phrases ("Thank You") are still caught regardless of case.

**Trade-off, stated plainly**: the Title-Case heuristic is a real judgment
call, not a hard guarantee — a short, incidentally-capitalized TV fragment
this STT engine transcribes cleanly could theoretically slip through. Given
the alternative is actively dropping real customer answers on live calls
right now, and the existing `_BACKGROUND_FRAGMENT_RE`/`is_likely_stt_noise`
checks still run first, this is a worthwhile trade, but it's a softer
guarantee than the other two changes in this PR (which are exact,
evidence-verified fixes).

### `tests/test_phone_background.py`
- `test_named_answer_not_background` — reproduces "Blue Lagoon."
- `test_filler_prefixed_no_not_background` — reproduces "ਅਹ, ਨਹੀਂ।"
- `test_title_case_bypass_does_not_match_long_sentences` — confirms the
  regex itself is scoped to short phrases (a 7-word capitalized sentence
  doesn't match it — separately, utterances over 2 tokens were already
  passed through by the pre-existing length check regardless, so this only
  verifies the new regex's own scope, not a length-based safety net on the
  overall function).

## What's NOT in This PR

- Did not add `special_instructions`/`order_type` to the phase-based bypass
  list (`customer_name`/`customer_phone`/`readback`) — PR 050 already added a
  re-ask fallback for every code-owned checkout phase, so a wrongly-dropped
  turn there now self-corrects on the next turn instead of going silent.
  Broadening the phase bypass further would reduce the filter's actual
  noise-catching value elsewhere without a concrete case requiring it.
- No change to `_BACKGROUND_FRAGMENT_RE`, `is_likely_stt_noise`, or the
  phone-echo bypass — unrelated to the two confirmed failures here.

## How to Test

```bash
PYTHONPATH=. pytest tests/test_phone_background.py -q
```

Live: answer a menu/flavor question with a short proper-noun-style name, and
separately answer a yes/no checkout question with a hesitation filler + "no"
(e.g. "um, no") — confirm neither gets dropped as background.

## Post-Merge: VPS Pull Command
`cd /opt/livekit-sarvam && git pull origin main && uv sync`
