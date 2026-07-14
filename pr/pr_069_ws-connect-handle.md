# PR 069 — WS Connect Handle

## Branch
`pr_069_ws-connect-handle`

## What This PR Does
Fixes finding 6 from `watchdog_gaps.md` (LOW, hardening).
`_ConfigInjectingSession.ws_connect` returned a bare coroutine, but aiohttp's
`ws_connect` returns an awaitable *context manager*. The installed
livekit-plugins-soniox 1.6.5 awaits it, so this worked — but it's the same
duck-typing bug class as the `__aiter__` gap fixed in PR 067: a plugin
upgrade switching to `async with session.ws_connect(...)` would break
silently (config injection dropped, or an outright AttributeError). The new
`_WSConnectHandle` implements both `__await__` and `__aenter__`/`__aexit__`,
wrapping the resulting WS in `_ConfigInjectingWS` on either path.

## Files Added
None.

## Files Modified
### `restaurant/voice_stack.py`
`ws_connect` now returns `_WSConnectHandle` (new class) instead of an ad-hoc
coroutine. Behavior when awaited is identical; `async with` now also works
and delegates `__aexit__` to aiohttp's own handle so cleanup semantics are
preserved.

### `tests/test_voice_stack.py`
Two new tests via a `_FakeWSRequest` that mimics aiohttp's dual awaitable/
context-manager return value: awaiting the handle yields a
`_ConfigInjectingWS` around the inner WS, and `async with` does the same and
propagates exit to the inner request.

## Files Deleted
None.

## What's NOT in This PR
- The EOU watchdog fixes (findings 1–5) — PR 068.
- No behavior change for the current plugin version; this is forward-compat
  hardening only.

## How to Test
```
uv run --with pytest python -m pytest tests/test_voice_stack.py -q
uv run --with pytest python -m pytest tests/ -q   # 4 known order-dependent failures pre-exist
```

## Post-Merge: VPS Pull Command
`cd /opt/livekit-sarvam && git pull origin main && uv sync`
