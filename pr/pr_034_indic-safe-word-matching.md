# PR 034 — Indic-safe word matching (fixes "stuck at allergies")

## Branch
`pr_034_indic-safe-word-matching`

## Status
✅ **Ready for review** — implementation complete on branch `pr_034_indic-safe-word-matching`.

## The bug (live transcript, 2026-07-02)

Sierra asked the allergies question; caller answered "ਨਹੀਂ ਨਹੀਂ," — **filtered as
background**. Then "ਹੈਲੋ—", "ਹੈਲੋ," — filtered. Call stuck at `special_instructions`
until abandoned. Reproduced deterministically.

Two stacked root causes, both **script bugs**, both verified:

1. **`\b` is broken for Gurmukhi/Devanagari.** Python `re` does not treat matras and
   bindi (ੀ ੋ ਂ …) as word characters, so `\bਨਹੀਂ\b` **never matches anything** — the
   word ends in bindi, and `\b` needs a word char on one side. Every Gurmukhi keyword
   ending in a matra/bindi inside a `\b(...)\b` pattern is silently dead code:
   ਨਹੀਂ (no), ਦੋ (two — quantity parsing!), ਡਿਲਿਵਰੀ (delivery), ਚਾਹੀਦਾ (want),
   ਲੈ (take), ਕਿਹਾ (said), ਬੰਦਾ/ਆਦਮੀ (human escalation), ਕਿਨਾ (price), ਤੇ (and).
   14 compiled patterns across 4 modules contain Indic text with `\b`.
2. **The background filter's short-answer allowlist is Latin-only.** "no", "hello",
   "haan" pass; ਨਹੀਂ, ਹੈਲੋ, ਹਾਂ do not exist in it. With (1) making intent fall to
   `general`, the caller's short Punjabi answers hit the allowlist and get dropped.

Combined effect: **a Punjabi speaker cannot answer the allergies question.** The
answer is always short ("ਨਹੀਂ") → intent misses → allowlist misses → dropped.

## What This PR Does

### 1. `restaurant/text_match.py` — Indic-aware word boundaries

`word_bounded(body)` / `indic_word_re(body)` replace `\b(...)\b`:

- **Left boundary** `(?<![\w + Indic marks])` — no match mid-word (stricter than the
  old `\b`, which wrongly allowed matches right after a matra).
- **Right boundary** `(?!\w)` — forbids letter continuation but **allows combining
  marks**, preserving the intentional stem matches (`ਕਰ ਦ` → ਕਰ ਦਿਓ,
  `ਮਿਲੇਗ` → ਮਿਲੇਗਾ, `ਚਾਹੀ` → ਚਾਹੀਦਾ) that the old patterns relied on.

Indic letters already count as `\w`; only the mark classes needed special handling.

### 2. Migrate all 14 Indic-containing patterns

| Module | Patterns |
|---|---|
| `conversation.py` | `_PRICE_RE`, `_AVAIL_RE`, `_PICKUP_RE`, `_DELIVERY_RE`, `_ADD_RE`, `_QTY_ITEM_RE`, `_I_SAID_RE`, `_WANT_ORDER_ONLY_RE`, `_DONE_RE`, `_NO_RE`, `_HUMAN_RE` |
| `phone_echo.py` | `_PRICE_SIGNAL_RE`, `_ORDER_SIGNAL_RE` |
| `order_parse.py` | `_QTY_RE` (fixes ਦੋ quantity extraction) |

Pure-Latin patterns keep plain `\b` — unchanged behavior.

### 3. Script-independent short-answer allowlist

`phone_background._SHORT_MEANINGFUL` checks now also compare **phonetic keys**
(PR 032's `phonetic_key`): ਨਹੀਂ→`nhn`≡"nahin", ਹੈਲੋ→`hl`≡"hello", ਹਾਂ→`hn`≡"haan",
ਜੀ→`j`≡"ji" — one list covers all three scripts, no per-script duplication.

### 4. Devanagari coverage for ladder-critical intents

Hindi answers were never matchable at all: नहीं/नही added to `_NO_RE`,
हाँ/ठीक/बिल्कुल/जी to `_YES_RE`, बस/हो गया to `_DONE_RE`. (Sierra's greeting
promises Hindi.)

## Behaviour changes (verified against the live transcript)

| Input (exact transcript turns) | Before | After |
|---|---|---|
| "ਨਹੀਂ ਨਹੀਂ," at allergies | `general` → **dropped** | `confirm_no` → answers the step |
| "ਹੈਲੋ," | dropped | passes (phonetic ≡ "hello") |
| "ਦੋ ਸਮੋਸੇ" | qty 1 (ਦੋ dead) | qty **2** |
| "ਡਿਲਿਵਰੀ" | not delivery intent | `delivery` |
| "ਬੰਦਾ" (want a person) | ignored | `human` escalation |
| "नहीं" (Hindi no) | unmatched | `confirm_no` |

## What's NOT in This PR (PR 035/036 per approved plan)

- Code-owned ladder speech (allergies/pickup questions spoken by code, English)
- Asked-and-answered flags / monotonic checkout phases
- Unclear→repeat-once→default policy
- Double-add guard + cart-aware guidance
- No `.env` changes; no kill switch — dead patterns matching again is strictly the
  intended behavior of the existing word lists

## Files Added

### `restaurant/text_match.py`
`INDIC_MARKS`, `word_bounded()`, `indic_word_re()`.

### `tests/test_text_match.py`
- Boundary unit tests (word-end bindi/matra, stem continuation, mid-word rejection)
- Three-script intent matrix (en / pa / hi) for no, yes, done, delivery, human, qty
- Exact live-transcript regression: turns 8–10 and 17–21 no longer filtered
- True background chatter still filtered

## Files Modified

`restaurant/conversation.py`, `restaurant/phone_echo.py`,
`restaurant/phone_background.py`, `restaurant/order_parse.py` — as above.

## How to Test

```bash
PYTHONPATH=. uv run pytest tests/test_text_match.py -q
PYTHONPATH=. uv run pytest tests/ -q
```

Manual (phone, after deploy): full order in Punjabi; at "Any allergies…?" answer
"ਨਹੀਂ ਨਹੀਂ" → flow must advance to pickup/delivery. Order "ਦੋ ਸਮੋਸੇ" → qty 2 in cart.

## Post-Merge: VPS Pull Command

```bash
cd /opt/livekit-sarvam && git fetch origin && git checkout main && git reset --hard origin/main && uv sync && systemctl restart restaurant-agent
```

## Verification checklist

- [x] `resolve_intent("ਨਹੀਂ ਨਹੀਂ,")` → `confirm_no`; not background-filtered
- [x] "ਹੈਲੋ" not filtered; TV-fragment chatter still filtered
- [x] "ਦੋ ਸਮੋਸੇ" parses quantity 2
- [x] Stems still match: ਕਰ ਦਿਓ (add), ਮਿਲੇਗਾ (availability), ਚਾਹੀਦਾ (want)
- [x] Full suite green (minus 4 pre-existing failures)
- [ ] Live call: allergies step answers cleanly in Punjabi, Hindi, English
