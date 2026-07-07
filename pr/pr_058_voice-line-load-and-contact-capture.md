# PR 058 — Voice line load + contact capture fixes

## Branch
`pr_058_voice-line-load-and-contact-capture`

## What This PR Does

Fixes three live-call issues from the fish-order transcript:

1. **English voice_line ignored at runtime** — `MenuCache.load()` now merges
   `clover_voice_labels.json` by `clover_item_id`, so Fish Pakora speaks
   **"Fish Pakora"** not Gurmukhi ਮੱਛੀ.
2. **Name asked twice** — `parse_customer_name()` handles `ਅਹ, ਸੰਦੀਪ ਸਿੰਘ`
   (filler + two-word Punjabi names); spice requirements deferred until
   name/phone captured so LLM doesn't hijack the name step.
3. **Duplicate goodbye** — code-owned place-order injects a system mute after
   speaking goodbye so the LLM cannot repeat it.

## Files Modified

### `restaurant/clover/menu.py`
- `MenuCache.load()` merges voice labels when loading menu cache JSON

### `restaurant/menu_provider.py`
- Pass `voice_labels_path` into `MenuCache.load()`

### `restaurant/customer_info.py`
- Leading `ਅਹ`/`ah` filler strip; two-word Punjabi names kept whole

### `restaurant/order_flow.py`
- Defer spice in `outstanding_requirements` until contact captured
- Turn guidance: name/phone step — no spice/modifiers

### `agent.py`
- `_execute_place_order(from_capture=)` mutes LLM after goodbye spoken

### `tests/test_menu_cache_load.py`, `tests/test_customer_info.py`, `tests/test_order_flow.py`
- Regression tests for voice_line load and name parse

## Post-Merge: VPS Pull Command
`cd /opt/livekit-sarvam && git pull origin main && uv sync && systemctl restart restaurant-agent`
