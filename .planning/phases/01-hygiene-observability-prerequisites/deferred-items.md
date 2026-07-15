# Deferred Items — Phase 01, Plan 01

Out-of-scope failures observed while running the full test suite during
01-01 execution (pre-existing, unrelated to `restaurant/channels/phone_echo.py`
/ `restaurant/channels/phone_background.py` changes; confirmed via
`git diff --stat` that this plan touched only those two files):

- `tests/test_customer_info.py::test_parse_punjabi_name_with_filler_and_two_words`
  and `::test_parse_two_word_english_name` — pre-existing failures in
  `restaurant/customer_info.py` name parsing. Matches the parked
  "customer-name-menu-hint-bug" ("Singh" → "single" fuzzy-match bug) tracked
  in `current_fixes.md` (PR 070/071) — not started per user instruction
  ("start only when asked").
- `tests/test_ambient_audio.py::test_build_web_ambient_player` and
  `::test_build_phone_ambient_player` — pre-existing `RuntimeError: There is
  no current event loop in thread 'MainThread'` failures, unrelated to
  turn-filter logic. Not investigated further (out of scope for HYG-01).

Not fixed here per the executor scope boundary (only auto-fix issues directly
caused by the current task's changes).
