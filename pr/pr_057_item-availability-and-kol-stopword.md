# PR 057 — Item availability matching + ਕੋਲ/Chole false-positive fix

## Branch
`pr_057_item-availability-and-kol-stopword`

## What This PR Does

Fixes live-call failures where callers ask **"do you have kheer?"** /
**"ਗੁਲਾਬ ਜਾਮੁਨ ਅਵੇਲੇਬਲ ਹੈ?"** and Sierra says the dish is not on the menu
or answers about the wrong item.

Root causes closed:
1. Punjabi **ਕੋਲ** ("with/us") phonetically matched **Chole** in full sentences.
2. `find_item()` on whole questions returned wrong dishes (Chole instead of Kheer).
3. No code-owned single-item availability reply — LLM guessed or used wrong tool.
4. Punjabi availability phrases (`ਹੈਗੀ`, `ਅਵੇਲੇਬਲ`) not detected as availability intent.
5. **ਡੈਜ਼ਰਟ** (Punjabi spelling) missing from dessert category aliases.

## Files Modified

### `restaurant/clover/match.py`
- Add stopwords: `ਕੋਲ`, `ਹੈਗੀ`, `ਅਵੇਲੇਬਲ`, `available`, `hai`, `gi`

### `restaurant/menu_provider.py`
- `extract_dish_query()` — strip availability wrappers, chunk-first dish match
- `resolve_item_in_text()` — question utterances use chunk path only (no full-sentence `find_item`)
- `check_item()` — resolves via `extract_dish_query()` first

### `restaurant/conversation.py`
- Extend `_AVAIL_RE` for `ਹੈਗੀ`, `ਅਵੇਲੇਬਲ`, `hai gi`
- `is_availability_question()`, `format_availability_reply()`

### `restaurant/menu_browse.py`
- Add `ਡੈਜ਼ਰਟ` / `desert` dessert aliases

### `agent.py`
- `_try_answer_item_availability()` — code-owned yes/no for "do you have X?"
- `check_menu_item` tool uses `extract_dish_query()`

### `tests/test_item_availability.py`
- Kheer question regression (not Chole)
- Gulab jamun availability
- ਡੈਜ਼ਰਟ category browse

## How to Test

```bash
PYTHONPATH=. pytest tests/test_item_availability.py tests/test_menu_browse.py tests/test_menu_match.py -q
```

Live:
1. "ਸਾਡੇ ਕੋਲ ਖੀਰ ਹੈਗੀ ਹੈ?" → yes, Kheer available
2. "ਗੁਲਾਬ ਜਾਮੁਨ ਅਵੇਲੇਬਲ ਹੈ?" → yes, Gulab Jamun available
3. "ਡੈਜ਼ਰਟ ਚ ਕੀ ਹੈ?" → lists desserts

## Post-Merge: VPS Pull Command
`cd /opt/livekit-sarvam && git pull origin main && uv sync && systemctl restart restaurant-agent`
