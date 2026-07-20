# PR 084 — Gap 5: English dish names never spoken in Gurmukhi

## Branch
`pr_084_english-dish-names`

## What This PR Does
Closes **Gap 5**: `lamb_biryani` (and siblings) resolved to a Gurmukhi `speak_as`
voice_line ("ਲੈਮ ਬਿਰਿਆਨੀ"), so `search_menu` handed the transliterated name to the
LLM, which correctly repeated it — an English proper name mispronounced by the pa
TTS. Primary fix is **data policy** (mark these dishes english-mode); a **prompt
rule** and a **TTS backstop filter** provide defence in depth.

Backstop behind `TTS_DISH_ENGLISH_ENFORCE` (default on).

## Files Modified
### `restaurant/clover/speech_policy.py` + `data/clover_voice_labels.json`
- Adds `lamb_biryani`, `chicken_biryani`, `lamb_rogan_josh`, `chicken_tikka_masala`
  to `ENGLISH_VOICE_KEYS` — the Non-Veg Mains whose Gurmukhi speak_as only
  transliterates the English word. Genuinely Punjabi-named dishes stay Gurmukhi.
- `data/clover_voice_labels.json` regenerated via `scripts/rebuild_voice_labels.py`
  (the baked file overrides live policy at load — see deviation); 4 items flipped
  to english mode.

### `restaurant/agent/prompt.py`
- HARD SPEECH RULES: "NEVER transliterate an English dish name into
  Gurmukhi/Devanagari … speak the dish exactly as the tool's voice_line gives it."
  Mirrored in `_legacy_core_prompt`.

### `restaurant/agent/tts_transform.py` + `restaurant/menu_provider.py` + `restaurant/clover/menu.py`
- New `menu_provider.english_dish_reverse_map()` — normalized Gurmukhi speak_as
  token sequence → English name, english-mode items only (never rewrites deliberate
  gurmukhi-mode dishes); static-menu fallback; cached per menu load. New
  `MenuCache.all_items()` accessor.
- New `DishNameFilter` in `tts_transform.py` (same pure feed/flush shape as
  `PhoneSpeechFilter`): holds a trailing run of Gurmukhi tokens, longest-match
  against the map on run boundary/flush, replaces matched spans with English, passes
  unmatched Gurmukhi through. Chained in `tts_node` with `phone_enforced_stream`.

### `restaurant/agent/persona.py`
- Fixes english-mode dish mentions in TONE EXAMPLES (butter chicken ×3, mango lassi,
  paneer tikka ×2) so the examples don't teach the anti-pattern; gurmukhi-mode
  dishes (samosa chaat, garlic naan, paneer butter masala) kept Gurmukhi.

## Tests
- `tests/test_speech_policy.py` (+1): biryanis resolve `("Lamb/Chicken Biryani", "english")`.
- `tests/test_tts_transform.py` (+10): DishNameFilter chunked live-repro
  (`"…ਲੈਮ ਬਿਰਿ" + "ਆਨੀ…"` → "Lamb Biryani"); ਸਮੋਸਾ ਚਾਟ untouched; flush-tail rewrite;
  multi-token longest match; empty-map/env-off no-ops; chain with PhoneSpeechFilter.
- New `tests/test_dish_reverse_map.py` (3); `tests/test_prompt.py` snapshot.
- Full suite: **405 passed**, then **408 passed** after the bounded-hold post-review fix.

## Deviations from Plan
- **The plan's "policy edit takes effect without regenerating clover_voice_labels.json"
  is WRONG** — `resolve_speech_from_label` short-circuits on baked `voice_line`+
  `speech_mode`, so the file had to be regenerated (`rebuild_voice_labels.py`); it is
  now part of the PR.
- **Broadened `ENGLISH_VOICE_KEYS` beyond the plan's two** (added rogan josh +
  chicken tikka masala — same transliteration failure mode).
- **Broadened the persona example fix beyond line 88** so the new HARD rule isn't
  self-contradicted by other english-mode dishes shown in Gurmukhi.

## Post-Review Fix (same branch, commit after `a280ec1`)
Bounded hold implemented for real: the original filter held the entire trailing
Gurmukhi run until flush, so a pure-Punjabi reply emitted **nothing** until the LLM
finished generating (TTS start delayed). `DishNameFilter._commit_prefix` now streams
runs/tokens as soon as greedy decisions are final; hold ≤ ~one dish name + partial
token (14-word Punjabi reply → 12 chunks emitted during feed, was 0). +3 tests.

## What's NOT in This PR
- DishNameFilter only rewrites Gurmukhi runs — a Devanagari transliteration of an
  english-mode dish wouldn't be caught (no live evidence it occurs).
- Live-verify (English non-veg recs → Roman "Lamb Biryani"; Punjabi call → ਸਮੋਸਾ ਚਾਟ
  still Gurmukhi) deferred to the post-all-steps live call.

## How to Test
```
PYTHONPATH=. uv run --with pytest pytest tests -q
```
