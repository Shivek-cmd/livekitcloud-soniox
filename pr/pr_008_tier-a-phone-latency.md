# PR 008 — Tier A phone latency + conversation polish

## Branch
`pr_008_tier-a-phone-latency` (merged directly to `main`)

## Commits
- `f63829e` — TurnDetector, preemptive TTS, latency logs, session_config
- `7ede58d` — Tighter endpointing (1.2→), search cap 2 items, no numbered lists in prompt
- `dd8c5e2` — `PHONE_ENDPOINTING_MAX=0.8` default

## What This PR Does

Replaces the **PR 005 slow phone config** (1s endpointing, no preemptive gen, no barge-in) with LiveKit-recommended **TurnHandlingOptions** while keeping echo protection via Cloud Krisp + `phone_echo.py`.

Also fixes **numbered menu lists** ("1. halwa, 2. jamun…") by capping search results and prompt rules.

### Latency improvements (measured on VPS test calls)

| Metric | PR 005 phone | After PR 008 (0.8 max) |
|--------|--------------|-------------------------|
| `eou_delay` | ~2.5s (hit max) | **0.5–0.9s** typical |
| `user_stop→speaking` | ~5–6s | **~3–4s** (tool turns still ~7s) |
| Echo loop | None (but dead) | **None** + adaptive barge-in |
| Numbered lists | Yes (8 items) | **No** — 2-item natural sentences |

## Files Added

### `restaurant/session_config.py`
- `build_agent_session(is_phone)` — single factory for phone vs web
- Phone: `TurnDetector(v1-mini)`, dynamic endpointing, preemptive TTS, adaptive interruption
- Env-tunable: `PHONE_ENDPOINTING_*`, `PHONE_PREEMPTIVE_*`, `PHONE_GREETING_SETTLE_SEC`, etc.

### `restaurant/turn_latency.py`
- Hooks `user_state_changed`, `agent_state_changed`, `metrics_collected`
- Logs `LATENCY turn=N | eou_delay=… | user_stop→speaking=… | llm_ttft=…`

## Files Modified

### `agent.py`
- Uses `build_agent_session()` + `TurnLatencyTracker`
- Removed inline `AgentSession` phone/web blocks (old STT-only config)
- Prompt: ban numbered lists, quotes on dish names, natural 2-item offers
- Greeting settle via `phone_greeting_settle_seconds()`

### `restaurant/menu_provider.py`
- `search_menu()` limit **8 → 2**; prose-style tool hints (good/bad examples)
- No bullet list in tool output (was teaching GPT to enumerate)

### `docs/vps-config.md`
- Deploy section with `vps_deploy.sh`, git SSH, menu sync steps

## What's NOT in This PR

- **Tier B:** echo false positives, search alias gaps, order state machine, TTS post-processor
- **Phase 8c:** Clover order submit
- `livekit-plugins-silero` — not needed; bundled VAD in livekit-agents 1.6.x
- BVCTelephony in RoomInputOptions — tried before, failed init; trunk Krisp sufficient

## How to Test

```bash
# VPS deploy
bash /opt/livekit-sarvam/scripts/vps_deploy.sh

# Outbound call
PYTHONPATH=/opt/livekit-sarvam uv run python scripts/test_call.py +91XXXXXXXXXX

# Verify in logs:
journalctl -u restaurant-agent -f | grep -E 'LATENCY|USER:|SIERRA:|Ignoring'

# On call:
# - Replies start sooner after you stop talking
# - No echo self-talk
# - "mithhe kya hai?" / "starters?" → two items in one sentence, NOT "1… 2… 3…"
# - eou_delay under 1s in LATENCY lines
```

## Post-Merge: VPS

```bash
bash /opt/livekit-sarvam/scripts/vps_deploy.sh
```

Current production: **`dd8c5e2`**.
