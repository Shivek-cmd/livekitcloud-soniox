# PR 092 — Fix end-of-call goodbye always speaking Punjabi

## Branch
`pr_092_goodbye-language-enum-fix`

## What This PR Does
Reported bug: the agent's closing/goodbye line at the end of a call was
always spoken in Punjabi, regardless of what language the rest of the
conversation was actually conducted in.

Root cause: the end-of-call goodbye is a **code-spoken** line (not
LLM-generated) — `order_placed_goodbye()` in `restaurant/agent/replies.py`,
called from `RestaurantAgent._finalize_order()` in
`restaurant/agent/core.py`. It picks the language branch with:

```python
lang = str(language or "").lower()
if lang == "en": ...
if lang == "hi": ...
# else: hardcoded Punjabi
```

`core.py` calls it with `language=getattr(self.state, "preferred_language",
None)` — the raw `CustomerLanguage` enum object, not `.value`.
`CustomerLanguage` is defined as `class CustomerLanguage(str, Enum)`
(`restaurant/agent/language.py:14`), and for a `(str, Enum)` mixin,
`Enum.__str__` takes precedence over the `str` mixin's `__str__` in the
MRO — so `str(CustomerLanguage.ENGLISH)` evaluates to
`"CustomerLanguage.ENGLISH"`, not `"en"` (verified interactively). That
string never equals `"en"` or `"hi"`, so the `lang == "en"` / `lang == "hi"`
checks never matched, and every call — English, Hindi, or Punjabi sessions
alike — silently fell through to the hardcoded Gurmukhi default.

(`false_add_correction_phrase`, the sibling function with the identical
`"en"`/`"hi"`-else-Punjabi shape, was *not* affected in practice — its one
call site in `core.py` already passes `self.state.preferred_language.value`,
not the enum object. Fixed anyway for defensive consistency, since it shares
the exact same fragile parsing pattern.)

## Files Modified

### `restaurant/agent/replies.py`
- `order_placed_goodbye()` and `false_add_correction_phrase()`: replaced
  `lang = str(language or "").lower()` with
  `lang = str(getattr(language, "value", language) or "").lower()` —
  extracts `.value` when given a `CustomerLanguage` enum, falls back to the
  value itself when given a plain string or `None`. Handles both current
  call shapes (`core.py` passes the raw enum to `order_placed_goodbye`, and
  `.value` to `false_add_correction_phrase`) without requiring the call
  sites to change.

### `tests/test_agent_replies.py`
- New `test_goodbye_accepts_enum_not_just_raw_value` — calls
  `order_placed_goodbye` with actual `CustomerLanguage` enum members (not
  raw strings), reproducing the real `core.py` call shape. This is the
  regression test: it would have failed against the old code (every branch
  falling through to Punjabi) and passes now.

### `tests/test_agent_place_order.py`
- `test_goodbye_spoken_and_sentinel_with_session` previously asserted the
  goodbye contained `"ਧੰਨਵਾਦ"` (Punjabi) — passing only because of this bug,
  since the `_make_ready` fixture conversation is entirely English and
  `preferred_language` defaults to `CustomerLanguage.ENGLISH`
  (`gates.py`). Updated to assert the correct English goodbye text
  (`"Thank you so much ji"`) now that the fix makes the language actually
  respected.

## Tests
- `tests/test_agent_replies.py`: existing `test_goodbye_language_variants`
  (raw string args) still passes; new
  `test_goodbye_accepts_enum_not_just_raw_value` covers the actual enum
  call shape used in production and fails without the fix.
- `tests/test_agent_place_order.py::test_goodbye_spoken_and_sentinel_with_session`
  updated to match correct (English) behavior for an English-only session.
- Full suite: **481 passed**.

## Deviations from Plan
None — single root-cause fix, no scope expansion.

## What's NOT in This PR
- No change to `CustomerLanguage`'s enum definition (e.g. switching to
  `StrEnum` on Python 3.11+, which would make bare `str()` behave as
  expected) — fixing the two call sites'/parsing function's assumption is a
  narrower, lower-risk fix than changing a shared enum's semantics.
- No change to the default-to-Punjabi fallback behavior for unset/mixed
  language — that default is intentional per the existing docstrings and
  unaffected by this bug; this PR only restores the ability for `"en"`/`"hi"`
  to actually be selected when the session language is one of those.

## How to Test
```
PYTHONPATH=. uv run --with pytest pytest tests -q
```

Manual call-flow check:
1. Start a call/web session conducted entirely in English, complete an
   order through to `place_order`.
2. Confirm the closing goodbye line is spoken in English
   ("Perfect, your order's in! ... Thank you so much ji — see you soon!"),
   not Punjabi.
3. Repeat with a Hindi-conducted session; confirm the Hindi goodbye variant
   is spoken.
4. Repeat with a Punjabi-conducted (or mixed/unclear-language) session;
   confirm the Punjabi goodbye variant is spoken (unchanged, intentional
   default).

## Post-Merge: VPS Pull Command
`cd /opt/livekit-sarvam && git pull origin main && uv sync`
