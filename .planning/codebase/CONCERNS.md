# Codebase Concerns

**Analysis Date:** 2026-07-14

## Tech Debt

### Latency telemetry never resets after first turn

**Issue:** `TurnLatencyTracker._emit_summary` logs metrics only once per session, labeled always as `turn=2`. The `_TurnSlice` is reset by `_begin_turn()` which gates on `self._turn.user_final_at is None`. After the first FINAL transcript, this condition is permanently false, so all subsequent turns emit no LATENCY logs.

**Files:** `restaurant/analytics/turn_latency.py:55-134` (especially lines 94-107, 124-125)

**Impact:** Production is nearly blind to per-turn latency degradation. Noisy-environment gaps (watchdog plan, turnwatchdog.md) cannot be validated. The 3-14s delays seen during hybrid-agent testing were invisible to telemetry.

**Fix approach:** Reset both `user_final_at` and `user_stopped_at` to `None` in `_TurnSlice.reset()` (currently lines 30-38 reset only thinking/speaking/llm/tts fields). Verify the gate at line 106-107 fires on every turn by adding a debug counter.

---

### Test suite polluted by global menu cache (hermetic isolation missing)

**Issue:** `restaurant/menu_provider.py:15-16` defines module-level `_cache` and `_cache_loaded` globals. `restaurant/clover/client.py:12-14` calls `load_dotenv()` at import time, so importing ANY menu-related test module sets `USE_CLOVER_MENU=1` in the process environment. The first call to `_get_cache()` (line 23-49) pins the **production cache** (`data/menu_cache_bizbull.json`) into `_cache`/`_cache_loaded` module globals, which **nothing resets**. No `conftest.py` exists to isolate tests.

**Files:**
- `restaurant/menu_provider.py:15-16, 23-49` (global state)
- `restaurant/clover/client.py:12-14` (import-time env load)
- `tests/test_customer_info.py` (currently fails with order-dependent behavior)
- `tests/test_menu_match.py:69-74, 98-101` (manual opt-in fixtures trying to work around this)

**Impact:** Test execution order matters. Running `test_menu_match.py` before `test_customer_info.py` causes the latter to fail with wrong menu cache (the Singh/"Bhatura (single)" false positive in current_fixes.md PR 070 depends on this). Production tests pass in isolation but fail in the full suite. Confidence in the test suite is low.

**Fix approach:** Create `tests/conftest.py` with an autouse fixture that monkeypatches `menu_provider._cache = None`, `menu_provider._cache_loaded = True`, and `USE_CLOVER_MENU=0`. Existing opt-in fixtures in test_menu_match.py/test_menu_browse.py override via their own monkeypatch — fixture ordering preserves precedence. See current_fixes.md PR 070 §"Changes — 2" for exact code.

---

### Circular imports + lazy module coupling in customer_info.py

**Issue:** `restaurant/customer_info.py:210, 222, 263` have lazy imports from `restaurant.conversation` (which is scheduled for deletion in refactor.md). The file imports `conversation` at runtime in three functions: `_menu_item_hint_in_text`, `parse_customer_name`. This creates a fragile dependency on a 1039-line module that will be deleted during the hybrid-agent refactor.

**Files:**
- `restaurant/customer_info.py:210, 222, 263` (lazy conversation imports)
- `restaurant/conversation.py:1-1039` (to be deleted)
- Callers: `restaurant/agent/core.py:52-56, 597, 612-618` (set_customer_contact uses parse_customer_name)

**Impact:** The refactor cannot delete `conversation.py` wholesale until these lazy imports are severed. Refactoring is blocked. If `conversation.py` is accidentally deleted before the fix, customer name parsing breaks silently (ImportError at runtime).

**Fix approach:** Move `_PICKUP_KEYWORDS`, `_DELIVERY_KEYWORDS`, `_LANGUAGE_KEYWORDS` regexes from `conversation.py` into `customer_info.py`, or define them locally in `parse_customer_name`. The actual use is phrase rejection for name parsing — pure text matching, no intent/phase needed. Inline the regex checks.

---

## Known Bugs

### Menu item hint incorrectly rejects customer name "Singh" (false positive)

**Issue:** `parse_customer_name("Sandeep Singh")` returns `None` instead of `"Sandeep Singh"`. The parser vetoes any name candidate that matches a menu item via `_menu_item_hint_in_text` → `menu_provider.resolve_item_in_text`. With `USE_CLOVER_MENU=1` (always true in production), the phonetic matcher matches "Singh" → "Bhatura (single)" because `phonetic_key("singh") = "sng"` prefix-matches `phonetic_key("single") = "sngl"`, awarding the flat `UNIQUE_SINGLE_CONF = 0.65` (restaurant/clover/match.py:276-280). This clears `DEFAULT_MIN_CONF = 0.55`, so the hint treats it as a menu item.

**Files:**
- `restaurant/customer_info.py:245-286` (_menu_item_hint_in_text, parse_customer_name)
- `restaurant/clover/match.py:276-280` (UNIQUE_SINGLE_CONF)
- `restaurant/agent/core.py:597` (set_customer_contact: calls parse_customer_name or falls back to raw string with filler text)
- `tests/test_customer_info.py:71-72, 75-76` (fails on order-dependent test execution)

**Trigger:** Any customer with surname "Singh" (common for this restaurant's clientele) saying their full name at the name prompt.

**Workaround:** The fallback in `core.py:597` (`clean = parse_customer_name(name) or name.strip()`) means the name IS saved, but with filler text intact and no name cleaning applied.

**Fix approach:** See current_fixes.md PR 070 — add `_MENU_HINT_MIN_CONF = 0.8` gate **inside `_menu_item_hint_in_text` only**. The hint's job is precision ("is this REALLY a dish?"), opposite to the order path's recall. Threshold 0.8 is calibrated to block `UNIQUE_SINGLE_CONF (0.65)` but pass exact/phonetic full-coverage matches (0.85+) that are legitimate dish duplicates in speech.

---

### Phone number never accepted: STT word-digits not normalized on input

**Issue:** At order checkout, the agent asks for phone but rejects every attempt in an infinite loop — "repeat the number, I need 10 digits" — even when the caller says all 10 digits in words. Root cause: `extract_phone_digits` (`customer_info.py:67-80`) strips every non-digit with `re.sub(r"\D", "", ...)`. Soniox (`stt-rt-v5`, hints `pa/en/hi`, no inverse-text-normalization configured) frequently transcribes dictated numbers as **words** — "nine four one three seven" or Hindi/Punjabi words ("nau char ek…"). Zero ASCII digits survive the strip → `None` → `set_customer_contact` (core.py:612-618) says "Phone NOT saved" → gates keep firing → loop forever.

The full word→digit map **already exists** in the same file (`_SPOKEN_DIGIT_WORDS`, lines 19-64) but is only wired into the **TTS readback (output)** direction (`enforce_english_phone_in_speech`, lines 115-156). It was never applied to the **STT (input)** direction.

Secondary gap: `looks_like_phone_utterance` (line 83-90) counts only ASCII digits, so a word-dictated number isn't recognized as phone speech and can be misrouted into `parse_customer_name`.

**Files:**
- `restaurant/customer_info.py:19-64` (_SPOKEN_DIGIT_WORDS — only used for output)
- `restaurant/customer_info.py:67-80` (extract_phone_digits — no word normalization)
- `restaurant/customer_info.py:83-90` (looks_like_phone_utterance — no word recognition)
- `restaurant/agent/core.py:612-618` (set_customer_contact — calls extract_phone_digits)
- `restaurant/agent/gates.py:58-59` (place_order_blockers — enforces 10-digit phone)

**Trigger:** Caller dictates phone as words: "nine four one three seven five two six eight eight" or mixed "94137 five two six eight eight" or Punjabi words.

**Workaround:** Caller can say digits slowly with pauses (Soniox might transcribe individual digits as ASCII). This is UX debt and fails in noisy environments (restaurant chatter, agent ambient audio).

**Fix approach:** See current_fixes.md PR 072 — create `_spoken_words_to_digits(text) -> str` helper that tokenizes text, replaces whole-token matches from `_SPOKEN_DIGIT_WORDS` with their digit, handles "double X"/"triple X" prefixes (common in Indian-English dictation). Wire it into `extract_phone_digits` after `_INDIC_NUMERAL_MAP` translate, before the `\D` strip. Also wire into `looks_like_phone_utterance` so word-dictated numbers register as phone utterances. Then `parse_customer_name`'s guard at line 258 works for free.

---

### Echo filter false positive: option answers flagged as echo

**Issue:** When agent asks "Would you like it mild, medium, spicy, or extra spicy?" and caller replies "I would keep it spicy", the reply is silently dropped as echo by `is_likely_phone_echo` (restaurant/channels/phone_echo.py:149-185). The reply tokenizes to `[would, keep, it, spicy]`; three tokens ("would", "it", "spicy") appear in the agent's question, only "keep" is unique — below the ≥2-unique escape threshold. Structural flaw: **answers to option-list questions inherently reuse the question's words**, but the overlap-count function treats function words ("would", "it") the same as content words. The caller only got through on retry because "want" hit `_ORDER_SIGNAL_RE`.

**Files:**
- `restaurant/channels/phone_echo.py:149-185` (is_likely_phone_echo — token overlap logic)
- `restaurant/agent/core.py:240, 252` (on_user_turn_completed calls this, always with intent=None/phase=None)

**Impact:** Customer answers to option questions (spice level, delivery choice, etc.) are silently dropped. No log entry, no reprompt by default — dead air until caller says "Hello" (PR 073 adds single-drop reprompt if a question is pending, but false positives should be prevented first).

**Trigger:** Agent asks a multi-option question; caller's natural answer reuses question words with at least one new word (but fewer than 2 unique content words).

**Fix approach:** See echo_gaps.md PR 073 §"Changes — 1" — add small `_STOPWORDS` frozenset (function words: "i, we, you, it, the, a, an, is, are, do, would, could, like…" plus Punjabi/Hindi equivalents). Compute content-word overlap: if the user's reply has any new content word not in the agent's line, **the reply is not echo**. Fall through to length-banded thresholds only for pure-stopword or all-overlapping content replies. Exact-match / truncated-prefix checks stay untouched.

---

### Background filter false positive: "No, thanks" flagged as background

**Issue:** After agent asks "Anything else?" and caller replies "No, thanks", the turn is silently dropped as background speech by `is_likely_background_speech` (restaurant/channels/phone_background.py:154). The `_BACKGROUND_FRAGMENT_RE` contains `thank you|thanks` (aimed at TV chatter) and runs **before** the short-meaningful-reply logic, so "thanks" swallows the most common way to decline an offer — even though "no" is on `_SHORT_MEANINGFUL`. Even if reordered, the 2-token rule requires *all* tokens meaningful, so "no thanks" would still drop.

**Files:**
- `restaurant/channels/phone_background.py:154` (_BACKGROUND_FRAGMENT_RE)
- `restaurant/channels/phone_background.py` (is_likely_background_speech logic)
- `restaurant/agent/core.py:262-264` (on_user_turn_completed calls this)

**Impact:** Customer's clear "No, thanks" (declining to order more) is dropped; no response is heard; customer may repeat or hang up. Rare compared to echo false positives, but directly impacts "Anything else?" flow — the final cart validation step.

**Trigger:** Short reply containing "thanks" or "thank you" in any context (not just TV chatter).

**Fix approach:** See echo_gaps.md PR 073 §"Changes — 2" — compute tokens early (already done lower down; reuse), and **if reply is ≤3 tokens and ANY token is meaningful (passes `_token_is_meaningful`), return False (not background)**. "No, thanks" → 2 tokens, "no" is meaningful → passes. TV "thank you" still drops (neither token meaningful). Then adjust the bottom 2-token rule from *all* meaningful to *any* meaningful (simpler, less prone to future false positives). Relatedly, consider it a rare background false negative when the LLM answers once vs. a false positive that mutes a real caller.

---

### Ambient audio tests fail unconditionally on Python 3.13

**Issue:** `tests/test_ambient_audio.py::test_build_web_ambient_player` and `::test_build_phone_ambient_player` fail unconditionally on Python 3.13+. The `build_ambient_player` function (restaurant/channels/ambient_audio.py) constructs livekit's `BackgroundAudioPlayer`, whose `rtc.AudioSource.__init__` falls back to `asyncio.get_event_loop()` (livekit/rtc/audio_source.py:56) — which raises `RuntimeError` outside a running loop on modern Python. **Production is unaffected**: the only call site is inside `async def entrypoint` (restaurant/agent/worker.py:132), always under a running loop.

**Files:**
- `tests/test_ambient_audio.py:41-52` (failing test cases)
- `restaurant/channels/ambient_audio.py` (build_ambient_player calls)

**Impact:** Test suite cannot run on Python 3.13+ without skipping these tests. CI/CD environment mismatch if CI runs 3.13 but dev/prod run 3.12. Confidence in ambient audio feature is lost.

**Fix approach:** Smallest fix, tests-only (no product code changes): construct the player inside an event loop in each test. Example:

```python
async def _build():
    return build_web_ambient_player()
player = asyncio.run(_build())
```

Or a tiny shared `_in_loop(fn)` helper in the test file. Current_fixes.md PR 071 has the exact code pattern.

---

## Security Considerations

### Menu cache file loaded without validation or versioning

**Issue:** `restaurant/clover/menu.py:MenuCache.load()` and `restaurant/menu_provider.py:_get_cache()` load `data/menu_cache_bizbull.json` or a tenant-specific cache path without verifying the file's checksum, modification time, or version. If the cache file is corrupted, tampered, or replaced with an old version, the menu will silently serve stale item prices and modifiers to customers.

**Files:**
- `restaurant/menu_provider.py:40` (_cache = MenuCache.load(path))
- `restaurant/clover/menu.py:MenuCache.load()` (JSON deserialization without validation)

**Current mitigation:** The file is in `.gitignore` and generated by Clover sync scripts (scripts/sync_menu.py).

**Recommendations:**
1. Add a "version" or "synced_at" field to the cache JSON and validate it on load.
2. Compute and store a checksum (SHA256) in the file and verify it on load.
3. Add a max-age check: reject caches older than 24 hours (configurable).
4. Log a warning if the cache is stale; fall back to static menu.

---

### Clover API token in environment without access control

**Issue:** `.env` file (not in repo, but must exist) contains `CLOVER_API_TOKEN` (plaintext). No `.env` encryption, no key rotation policy. If a developer's machine is compromised or the `.env` file is accidentally committed, the Clover API is exposed.

**Files:**
- `.env` (listed in .gitignore, but not encrypted)
- `restaurant/clover/client.py:12-14` (loads via load_dotenv() at import time)
- `restaurant/clover/order_submit.py:53-58` (CloverClient initialized with token)

**Current mitigation:** `.env` is in `.gitignore`; `.env.example` is committed without secrets; systemd runs the agent as a restricted user.

**Recommendations:**
1. Use AWS Secrets Manager or HashiCorp Vault for prod token storage.
2. Rotate Clover API token quarterly.
3. Add a pre-commit hook to detect `.env` file commits.
4. Document `.env` setup in onboarding; require GPG signing for manual `.env` changes.

---

## Performance Bottlenecks

### Menu cache reloaded from disk on every order submit

**Issue:** `restaurant/clover/order_submit.py:_cached_item()` (lines 114-123) reloads the entire MenuCache from disk **every time** it's called, which happens during `_match_spice_modifier()` (line 126), called for every item in the cart during submit. With typical cart sizes of 3-5 items, the cache JSON (61 items, ~30KB) is deserialized 3-5 times per order. For a high-order-volume restaurant, this is wasteful I/O and parsing work.

**Files:**
- `restaurant/clover/order_submit.py:114-123` (_cached_item — no caching)
- `restaurant/clover/order_submit.py:126` (_match_spice_modifier — called per item)
- `restaurant/clover/order_submit.py:167-240` (submit_cart_to_clover loops over items)

**Impact:** Slower order submit, higher CPU use, cascading latency to customer (they wait longer for "order confirmed").

**Fix approach:** Load the cache once at the start of `submit_cart_to_clover`, cache it in a function-local or class-level variable, reuse for all `_match_spice_modifier` calls. The cache is already module-level in `menu_provider` — import it there or pass it as a parameter.

---

### Synchronous Clover submit blocks async event loop

**Issue:** `restaurant/clover/order_submit.py:submit_cart_to_clover()` (line 304) is synchronous and uses `urllib.request.urlopen` (synchronous HTTP). It must be called via `asyncio.to_thread()` from async tool code (restaurant/agent/core.py), but there is no defensive documentation or guard. If a future refactor calls it directly from an async context, the event loop will block for 1-5 seconds (typical Clover API latency), stalling STT/TTS/agent thinking.

**Files:**
- `restaurant/clover/order_submit.py:1-377` (entire module is sync)
- `restaurant/agent/core.py` (place_order tool calls it via asyncio.to_thread, but this is easy to miss)

**Current mitigation:** Refactor.md §2.2 notes the pattern; current code uses `asyncio.to_thread` in the place_order tool.

**Recommendations:**
1. Add a large docstring comment at the top of `order_submit.py`: "All functions in this module are synchronous and must be called via `asyncio.to_thread()` from async contexts."
2. Consider rewriting `submit_cart_to_clover` as async (using `aiohttp` instead of `urllib`) for future scaling.

---

## Fragile Areas

### Exception handling overly broad, swallows context

**Issue:** Multiple locations use bare `except Exception:` that logs the exception but doesn't re-raise or perform graceful fallback. Examples:
- `restaurant/agent/core.py:211, 231, 715` — echo/background reprompt failures, Clover submit failures
- Bare except swallows the traceback context and makes debugging harder. A network failure vs. a bug in the exception handler become indistinguishable.

**Files:**
- `restaurant/agent/core.py:211, 231, 715` (except Exception: logger.exception(...) but no fallback)

**Impact:** Production errors are logged but may not be actionable. A silent Clover failure (line 715) logs "Clover submit unexpected error" but the LLM has no feedback on what to tell the customer.

**Fix approach:**
1. Use specific exception types: `except TimeoutError:`, `except ConnectionError:`, etc.
2. If a bare `except Exception:` is needed, immediately re-raise: `except Exception: logger.exception(...); raise`.
3. For expected fallbacks (e.g., echo reprompt failure), log at WARNING level and perform the fallback action.

---

### Latency telemetry gate logic is fragile and order-dependent

**Issue:** `restaurant/analytics/turn_latency.py:94-107` resets the turn via `_begin_turn()`, which only runs if `self._turn.user_final_at is None`. But `_emit_summary()` (line 55) only resets `_turn_active = False` at line 92, **never clears the timestamp fields**. After the first emit, `user_final_at` stays non-None forever, so `_begin_turn()` never fires, so `_turn_counter` never increments beyond 1.

The gate is fragile: depend on callback order (which is hit first, `user_input_transcribed` or `user_state_changed`?). The logic should be refactored to be order-independent.

**Files:**
- `restaurant/analytics/turn_latency.py:55-134`

**Fix approach:** Refactor the state machine:
- Always increment `_turn_counter` on the first user event of a new turn.
- Define "new turn" as: `user_stopped_at` or `user_final_at` was already recorded AND we're hearing a NEW user event. Use a generation counter or explicit "turn ended" flag instead of timestamp nullability.
- Test both callback orderings.

---

### Menu browse uses fragile regex patterns for category extraction

**Issue:** `restaurant/menu_browse.py:30-75` hard-codes Clover category_name values from `data/menu_cache_bizbull.json` as regex patterns (e.g., "Appetizers", "Main Courses"). If a restaurant changes the menu structure or Clover category names, the browse module silently returns empty lists or wrong categories — no error, no fallback.

**Files:**
- `restaurant/menu_browse.py:30-75` (hard-coded category patterns)

**Impact:** Category browse ("What appetizers do you have?") fails silently for restaurants with custom category names.

**Fix approach:** Load categories dynamically from the MenuCache at startup. Define a `categories()` function that returns the list of available categories. The LLM can be prompted with these categories at session start.

---

## Test Coverage Gaps

### No autouse test isolation fixture for menu cache

**Issue:** Tests importing menu-related modules lazily load the production cache (Clover menu) without isolation. No autouse fixture to reset `menu_provider._cache` and `_cache_loaded` between tests or to force static-menu mode.

**Files:**
- `tests/conftest.py` — does not exist
- `restaurant/menu_provider.py:15-16, 23-49` (global state)
- `tests/test_menu_match.py, test_customer_info.py, test_menu_browse.py` (affected by pollution)

**Impact:** Test order matters; test isolation is broken.

**Fix approach:** Create `tests/conftest.py` with autouse fixture (current_fixes.md PR 070 §2 has the exact code).

---

### Phone echo and background filters lack regression test coverage for false positives

**Issue:** `restaurant/channels/phone_echo.py` and `restaurant/channels/phone_background.py` filters are tested for True cases (actual echo, actual background) but lack comprehensive regression tests for the false positives in echo_gaps.md:
- "I would keep it spicy." should **not** be echo.
- "No, thanks." should **not** be background.

No tests exist for these cases, so a future refactor could reintroduce the bugs.

**Files:**
- `tests/test_phone_echo.py` (current tests don't cover option-answer false positive)
- `tests/test_phone_background.py` (current tests don't cover "No, thanks" false positive)

**Fix approach:** Add regression tests (echo_gaps.md PR 073 §"Tests" has the exact test cases).

---

### Ambient audio tests only run when WEB/PHONE_AMBIENT_ENABLED is set

**Issue:** `tests/test_ambient_audio.py` uses `monkeypatch.setenv()` to enable features, but the tests that actually call `build_ambient_player()` (lines 41-52) are only run when the env vars are "1". If a developer doesn't read the test file, they might not realize these tests exist. The AsyncIO event loop issue (Python 3.13 bug) is masked by disabled-by-default tests.

**Files:**
- `tests/test_ambient_audio.py:41-52` (only run if WEB_AMBIENT_ENABLED=1)

**Fix approach:** Ensure the tests always run (or clearly document why they're conditional). Fix the AsyncIO issue (PR 071) so they pass.

---

## Scaling Limits

### Session recorder disk write not async

**Issue:** `restaurant/analytics/session_recorder.py:finalize()` writes the session transcript to disk synchronously. If the disk is slow or full, this blocks the agent thread. With many concurrent sessions, disk I/O could become a bottleneck.

**Files:**
- `restaurant/analytics/session_recorder.py` (write operations)

**Current deployment:** Single-instance VPS, unlikely to hit this limit soon, but it's a constraint.

**Scaling path:** Refactor to use `aiofiles` for async writes, or queue transcripts to an async task that batches writes.

---

### Menu cache loaded entirely into memory for every session

**Issue:** `MenuCache.load()` deserializes the entire menu JSON (61 items) into Python objects and pins it in module memory. Each session creates a new agent instance but shares the same global `_cache`. With 100+ concurrent sessions, this is fine (shared memory). But if the cache grows (new menu items added), memory footprint grows linearly and no reload happens without a process restart.

**Current deployment:** Single VPS, 61 items ~1MB in memory — not a concern.

**Scaling path:** Implement cache TTL and async refresh; use a database (SQLite or Postgres) instead of JSON file.

---

## Missing Critical Features

### No voice-label fallback for unseen menu items

**Issue:** If Clover syncs a new menu item but the voice-labels overlay (`data/clover_voice_labels.json`) is not updated, the agent cannot pronounce the new item. TTS will mangle the spelling, and the LLM won't recognize customer speech about that item (no voice label for phonetic matching).

**Files:**
- `restaurant/clover/menu.py:MenuCache.load()` — loads voice labels
- `data/clover_voice_labels.json` — overlay file, must be manually updated

**Current mitigation:** Sync script (scripts/sync_menu.py) updates the cache file, but voice labels are manual.

**Recommendation:** Add a fallback: if an item has no voice label, generate one phonetically or ask the user to record it.

---

### No retry logic for Clover API failures

**Issue:** If the Clover API is temporarily unavailable (network glitch, API maintenance), `submit_cart_to_clover` fails once and gives up. No exponential backoff, no retry, no queue.

**Files:**
- `restaurant/clover/order_submit.py:304` (single attempt)
- `restaurant/agent/core.py:710-718` (catches exception, logs, moves on)

**Current deployment:** Single restaurant, Clover API is reliable. For scaling, this is required.

**Scaling path:** Add retry logic with exponential backoff (3 attempts, 1s → 2s → 5s delays). Queue failed orders to a retry job. Notify restaurant staff if an order submit fails after retries.

---

*Concerns audit: 2026-07-14*
