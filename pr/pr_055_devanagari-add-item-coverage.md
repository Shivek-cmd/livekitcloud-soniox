# PR 055 — Devanagari (Hindi-script) add-item phrase recognition

## Branch
`pr_055_devanagari-add-item-coverage`

## What This PR Does

Extends the add-item detection regexes in `restaurant/conversation.py` to
recognize Devanagari (Hindi script) phrasing, not just Gurmukhi (Punjabi
script) and Latin transliteration. The opening greeting advertises Hindi
support (`OPENING_GREETING`: "I speak English, Hindi, and Punjabi"), but
`detect_intent()` had no Devanagari patterns at all — a caller ordering in
Hindi script (e.g. "एक प्लेन राइस भी कर दियो" / "मुझे एक मैंगो कुल्फी
चाहिए") would not be classified `ADD_ITEM`.

This was split out of a local branch that originally bundled it with a
mid-checkout-add mechanism; that other half turned out to be redundant with
PR 054's `reopen_after_add`/checklist rework (already merged to `main` as
GitHub PR #90) and was dropped. Only this independent Devanagari fix is new.

## Files Modified

### `restaurant/conversation.py`
- `_ADD_RE` — added Devanagari alternation: `चाहि(?:ए|ये|या)|ऑर्डर|डाल द|जोड़|ले|कर द|एड`
  (मुझे...चाहिए / ऑर्डर करो / डाल दो / जोड़ो / ले लो / कर दो / एड करो).
- `_ADD_IMPERATIVE_RE` — added Devanagari imperative forms:
  `करो|कर द|दो|दिया|दियो|दीजिए`.
- `detect_intent()` — the standalone `ਚਾਹੀ(?:ਦਾ|ਦੀ|ਦੇ)` check (which returns
  `ADD_ITEM` ahead of the general `_ADD_RE`/`_ADD_IMPERATIVE_RE` combo) now
  also matches the Devanagari equivalent `चाहि(?:ए|ये|या)`.

### `tests/test_conversation.py`
- `test_detect_add_intent_devanagari` — asserts both example phrases above
  classify as `ADD_ITEM`.

## What's NOT in This PR
- Does not add Devanagari coverage to other intent regexes (`_DONE_RE`,
  `_PICKUP_RE`, `_DELIVERY_RE`, allergy patterns, etc.) — scoped to the
  confirmed add-item gap only. A fuller Devanagari audit across
  `conversation.py` is a separate, larger task.
- Does not touch the menu-matching/auto-add pipeline
  (`restaurant/order_parse.py`, `restaurant/clover/match.py`) — this PR is
  intent classification only; whether a Devanagari-spelled dish name itself
  matches the menu is a separate (already partially-addressed, see PR 032/033)
  concern.
- Pre-existing failures in `tests/test_ambient_audio.py`,
  `tests/test_menu_match.py::test_auto_add_threshold_env`, and three cases in
  `tests/test_order_parse.py` were verified to already fail on `main`
  (post-PR-054/#90) before this branch's changes — not caused by or fixed in
  this PR, left untouched.

## How to Test
```bash
PYTHONPATH=. pytest tests/test_conversation.py tests/test_order_flow.py tests/test_phone_echo.py -q
```

Live: order an item using Hindi-script phrasing (e.g. "मुझे एक मैंगो कुल्फी
चाहिए" or "एक प्लेन राइस भी कर दियो") — confirm it's recognized as an add
instead of falling through to a generic/confused reply.

## Post-Merge: VPS Pull Command
`cd /opt/livekit-sarvam && git pull origin main && uv sync`
