# PR 063 — Package Reorg: channels/ and analytics/

## Branch
`pr_063_package-reorg`

## What This PR Does
Final PR of the conversation-architecture rebuild (`refactor.md` Part II §3, "PR 062 — package-reorg" in the pre-renumbering plan). Pure mechanical restructure: `git mv` the channel-hygiene modules into `restaurant/channels/` and the analytics modules into `restaurant/analytics/` (history preserved), then update every import site across `restaurant/` and `tests/`. Zero logic changes.

## Files Added
### `restaurant/channels/__init__.py`
Empty package marker for the channel-hygiene package.

### `restaurant/analytics/__init__.py`
Empty package marker for the analytics package.

## Files Moved (`git mv`, no content changes except imports noted below)
| From | To |
|---|---|
| `restaurant/phone_echo.py` | `restaurant/channels/phone_echo.py` |
| `restaurant/phone_background.py` | `restaurant/channels/phone_background.py` |
| `restaurant/stt_noise.py` | `restaurant/channels/stt_noise.py` |
| `restaurant/ambient_audio.py` | `restaurant/channels/ambient_audio.py` |
| `restaurant/call_control.py` | `restaurant/channels/call_control.py` |
| `restaurant/web_sync.py` | `restaurant/channels/web_sync.py` |
| `restaurant/session_recorder.py` | `restaurant/analytics/session_recorder.py` |
| `restaurant/analytics_store.py` | `restaurant/analytics/analytics_store.py` |
| `restaurant/turn_latency.py` | `restaurant/analytics/turn_latency.py` |

## Files Modified (import-path updates only)
### `restaurant/channels/phone_background.py`
Sibling imports re-pointed: `restaurant.phone_echo` → `restaurant.channels.phone_echo`, `restaurant.stt_noise` → `restaurant.channels.stt_noise`.

### `restaurant/agent/core.py`
Imports re-pointed to `restaurant.channels.{call_control,phone_background,phone_echo,stt_noise,web_sync}` and `restaurant.analytics.session_recorder`.

### `restaurant/agent/worker.py`
Imports re-pointed to `restaurant.channels.{ambient_audio,web_sync}` and `restaurant.analytics.{analytics_store,session_recorder,turn_latency}`.

### `tests/test_phone_echo.py`, `tests/test_phone_background.py`, `tests/test_stt_noise.py`, `tests/test_ambient_audio.py`, `tests/test_call_control.py`, `tests/test_session_recorder.py`
Import paths (and the one `patch("restaurant.call_control.…")` string) updated to the new package paths.

## Files Deleted
None (moves only).

## What's NOT in This PR
- No logic, behavior, or signature changes anywhere — imports only.
- `restaurant/clover/`, `restaurant/tenants/`, `menu*.py`, `orders.py`, `customer_info.py`, `voice_stack.py`, `session_config.py`, `llm_warmup.py`, `reservations.py`, `text_match.py`, root `agent.py`, `token_server.py`, `web/`, `admin/`, `scripts/`, `deploy/` — all untouched (none import the moved modules).

## How to Test
```
python -m pytest tests/ -q          # full suite green
python -c "import restaurant.agent.worker"   # entrypoint imports resolve
```

## Post-Merge: VPS Pull Command
`cd /opt/livekit-sarvam && git pull origin main && uv sync`
