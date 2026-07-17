# PR 078 — Grounded natural readback + post-speech verifier (Step 5 of Human Conversation Rebuild)

## Branch
`pr_078_grounded-readback-verifier`

## What This PR Does
Replaces the VERBATIM readback template with a grounded-but-natural readback: `get_order_readback`
now returns a `READBACK FACTS` list (per-item qty + voice_line, order type, name, total on web)
that the LLM phrases in the customer's language, and a new pure code verifier
(`restaurant/agent/readback_verify.py`) checks that every item, quantity, and the order type were
actually SPOKEN before `confirm_readback` can succeed. The money path is unchanged:
`place_order_blockers` still requires `readback_confirmed` at the current cart revision —
confirmation is simply only granted after verification passes (in `strict` mode) or is logged
for measurement (in `warn` mode, the initial live default).

The spoken text is captured through the existing assistant-utterance path (`note_agent_speech`,
fed by the `conversation_item_added` hook): `get_order_readback` sets `readback_pending` and
clears a per-readback speech buffer; every assistant line while pending is appended; the
verifier runs over the buffer at `confirm_readback`. Barge-in truncation or a same-turn
readback+confirm leaves the buffer short → verifier fails → re-read (fail-safe direction).

`READBACK_VERIFY` env: `warn` (default — log + analytics event, allow), `strict` (refuse with
`READBACK INCOMPLETE: <problems>`, clear buffer, keep unconfirmed), `off` (emergency rollback).

## Files Added
### `restaurant/agent/readback_verify.py`
Pure, I/O-free verifier. Trilingual quantity lexicon 1–20 (English words, Gurmukhi words,
Devanagari words, ASCII digits, Gurmukhi ੦-੯ / Devanagari ०-९ numerals). Normalization:
NFC → casefold → strip punctuation preserving Indic codepoints → tokenize. Per item, aliases =
normalized voice_line + English name with parentheticals ("(2 pcs)") stripped. Checks:
- **item presence** — alias token-sequence must appear in the spoken buffer;
- **quantity window** — a quantity token within 3 tokens before the alias: wrong number → fail;
  absent with qty ≥ 2 → fail; absent with qty 1 → OK ("and a Garlic Naan" passes);
- **order type** — closed vocab anywhere: English (pickup / pick up / delivery / deliver /
  delivered) plus the exact phonetic Gurmukhi/Devanagari transliterations gpt-4.1-mini actually
  produces mid-Punjabi/Hindi (ਪਿਕਅਪ / पिकअप / ਡਿਲੀਵਰੀ / डिलीवरी — seen in every pa/hi harness
  readback; the customer heard the order type, so failing them is a pure false negative). Still
  a closed list, never fuzzy;
- **total** (web only, warn-level) — if a numeric dollar amount was spoken it must equal
  `cart.total`.
NOT verified (unverifiable across languages, not money-corrupting): inflection, honorifics,
notes/spice, phrasing order. Also home to `readback_verify_mode()` (READBACK_VERIFY env).

### `tests/test_readback_verify.py`
Passing phrasings ×3 languages; missing item fails; wrong qty fails; qty-1 omission passes;
Gurmukhi dish + English qty passes; Devanagari qty passes; empty/truncated buffer fails;
order-type vocab; total mismatch warns (web); normalization + parenthetical stripping.

### `tests/scenarios/sloppy_readback.json`
Adversarial harness scenario (strict mode): the first spoken readback is censored so Garlic Naan
is never "said" → `confirm_readback` must refuse with READBACK INCOMPLETE → the model re-reads
uncensored → confirm succeeds → order places.

## Files Modified
### `restaurant/agent/gates.py`
`OrderSessionState` += `readback_pending: bool = False`, `readback_spoken: list[str]`
(field adds only — blocker functions untouched). `invalidate_readback` also clears
pending + buffer (any cart mutation voids the in-flight readback capture).

### `restaurant/agent/facts.py`
New `format_readback_facts(cart, include_total)` — the READBACK FACTS block (items via the
same `_dish_label` grounding as ORDER NOW, order type with say-"pickup"-in-English note, name,
total on web only) plus a GUIDE line: phrase naturally in the customer's language, but every
item/qty/order type must actually be spoken — the spoken readback is checked, anything missing
forces a re-read.

### `restaurant/agent/core.py`
- `note_agent_speech` appends to `state.readback_spoken` while `readback_pending`.
- `get_order_readback` returns `format_readback_facts(...)` instead of the VERBATIM template;
  still sets `readback_revision` / clears `readback_confirmed`; new: sets `readback_pending`,
  clears the buffer.
- `confirm_readback` runs the verifier after the existing revision checks, per
  `READBACK_VERIFY` mode; on strict failure returns `READBACK INCOMPLETE` + problems and clears
  the buffer (stays pending so the re-read is captured); warn mode logs + records a
  `readback_verify_warn` analytics event and confirms; success clears pending.

### `restaurant/agent/prompt.py`
Readback lines in YOUR JOB + both tool lists (persona AND legacy — the tool's return shape
changed, so the legacy prompt's VERBATIM instruction would now be wrong): "read back ALL of its
READBACK FACTS in the customer's language, then ask if everything is correct."

### `restaurant/agent/replies.py`
Delete `format_order_readback` + `CONFIRM_CLOSE` (replaced by READBACK FACTS; `format_order_status`
stays — used by `_not_in_cart`).

### `scripts/dialogue_harness.py`
Turn-selection fix surfaced by this step's harness run: scenario reactive rules are now
consulted BEFORE the built-in phone-digit confirm. The model sometimes asks a combined
question ("…is that number right? Now, pickup or delivery?"); the generic built-in "Yes."
made it guess `set_order_type("pickup")` on a delivery order (delivery_split_phone failed) —
the specific "Delivery please." rule must win.
Scenario support for the adversarial test: `"readback_verify"` sets the env mode for the run;
`"censor_speech"` entries (`{"text", "max_uses"}`) strip a substring from what gets fed to
`note_agent_speech` while a readback is pending (simulates a sloppy/truncated spoken readback
without touching the LLM context); new expect key `"tool_result_contains"`
(`{"tool", "contains", "min": 1}`).

### `tests/test_agent_tools.py`
Readback-cycle tests updated to the new return (READBACK FACTS instead of READ THIS BACK
VERBATIM); new strict/warn/off confirm tests with a simulated `note_agent_speech` feed.

### `tests/test_agent_place_order.py`
`_make_ready` feeds a complete spoken readback via `note_agent_speech` so the confirm is
verifier-clean in any mode.

### `tests/test_agent_replies.py`
`format_order_readback` tests removed (formatter deleted).

## Files Deleted
None (function-level deletions in `replies.py`).

## What's NOT in This PR
- `sanitize_assistant_speech` deletion + TTS phone-digit enforcement (Step 6 / PR 079).
- Flipping `READBACK_VERIFY` default to `strict` — needs warn-mode false-negative data from
  live calls per language first (Step 7 decides).
- Naturalness rubric / judge (Step 7 / PR 086).

## Known false-negative data (why warn is the initial default)
Replaying the committed pr078 harness transcripts through the verifier: 5/9 regular scenarios
verify fully clean; 4/9 would fail strict, ALL from one cause — when speaking Punjabi/Hindi the
model renders an English `voice_line` into Gurmukhi/Devanagari ("ਬਟਰ ਚਿਕਨ" for voice_line
"Butter Chicken", "पनीर टिक्का" for "Paneer Tikka"), which is outside the voice_line +
English-name alias set. This bends the "dish names = voice_line exactly" hard rule (a known
PR 077 watch item), and adding general dish-name transliteration to the verifier is explicitly
out (plan). Live warn-mode data per language + Step 7 decide: fix the model's rule-following,
or accept it stays warn for pa/hi.

## How to Test
```
PYTHONPATH=. uv run --with pytest pytest tests
uv run python scripts/dialogue_harness.py --out docs/eval/pr078
```
Live: deploy with default `READBACK_VERIFY=warn`, place real calls per language, grep logs /
analytics for `readback_verify_warn` events to measure false negatives before considering strict.
Rollback: `READBACK_VERIFY=off` (verifier), none needed for the facts readback itself.

## Post-Merge: VPS Pull Command
`cd /opt/livekit-sarvam && git pull origin main && uv sync`
