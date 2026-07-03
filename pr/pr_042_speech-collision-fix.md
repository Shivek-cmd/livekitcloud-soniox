# PR 042 — Fix garbled back-to-back speech (filler/ladder/LLM collision)

## Branch
`pr_042_speech-collision-fix`

## Problem

Live call transcripts show Sierra's speech occasionally garbled into a single
run-on, mixed-language sentence, e.g.:

> "ਹਾਂ ਜੀ, ਇੱਕ ਗਾਰਲਿਕ Will that be pickup or delivery? menu check kardi haan."

`"menu check kardi haan."` is a literal Punjabi filler string from
`restaurant/fillers.py` (`FillerKind.PROCESSING` pool). It is not a
hallucination — it is real evidence that two or three independently-triggered
`session.say()` calls landed back-to-back in the same turn window.

Root cause (confirmed against the `livekit-agents` SDK, not guessed):

1. `AgentActivity` queues every `session.say()` / generated reply as a
   `SpeechHandle` in a single FIFO priority queue (`agent_activity.py`,
   `_speech_q` / `_scheduling_task`). All our call sites use the same
   priority (`SPEECH_PRIORITY_NORMAL`), so speeches never interrupt each
   other — they play strictly back-to-back.
2. `AgentSession` supports `min_consecutive_speech_delay` to force a pause
   between consecutive queued speeches, but it is never set in
   `restaurant/session_config.py` — the gap defaults to `0.0`.
3. `agent.py::_maybe_speak_filler` fires a filler via
   `asyncio.create_task(self._speak_filler(line))` — fire-and-forget, no
   `SpeechHandle` tracked, not awaited. It fires in the same
   `on_user_turn_completed` call that, moments later, lets the framework
   generate and speak the real LLM turn reply (accelerated further by
   `preemptive_generation`, already enabled by default in
   `session_config.py`). The `agent_session_busy()` check that guards the
   filler only inspects `agent_state` at decision time, before the real
   reply's generation has started — so it does not prevent the collision.
4. The same fire-and-forget pattern (`asyncio.create_task`, no handle
   tracking) is used by `_echo_reprompt` and `_background_reprompt`, which
   are exposed to the same class of collision.

Net effect: with no inter-utterance gap and no coordination between
independently-fired speech calls, two or three unrelated utterances queue
back-to-back and read/sound like one garbled, mixed-language sentence.

## Solution

| Change | Why |
|--------|-----|
| Set `min_consecutive_speech_delay` (env-tunable, default ~0.3s) on `AgentSession` in `session_config.py` | Forces a clean pause between any two queued speech handles — cheap, SDK-native, fixes the "ran together" symptom regardless of which two calls collide |
| Track the `SpeechHandle` returned by `session.say()` for fire-and-forget paths (`_speak_filler`, `_echo_reprompt`, `_background_reprompt`) instead of discarding it | Lets us check/await instead of firing blind |
| Re-check `session.current_speech` immediately before firing a fire-and-forget filler/reprompt, not just `agent_state` at decision time | Avoids scheduling a filler in the same breath as an about-to-be-generated real reply |
| Skip (do not queue) a fire-and-forget filler/reprompt if speech is already in flight, instead of letting it stack | A late filler is worse than no filler — never queue "catch-up" fillers behind other speech |

## Files Modified

### `restaurant/session_config.py`
- Add `_env_float("MIN_CONSECUTIVE_SPEECH_DELAY_SEC", 0.3)` and pass
  `min_consecutive_speech_delay=...` into `AgentSession(**kwargs)`.

### `agent.py`
- `_speak_filler`, `_echo_reprompt`, `_background_reprompt`: capture the
  `SpeechHandle`, re-check `self._session.current_speech` right before
  calling `session.say()`, and no-op if speech is already in flight instead
  of queuing behind it.

### `.env.example`
- Document `MIN_CONSECUTIVE_SPEECH_DELAY_SEC`.

## What's NOT in This PR

- Quantity-correction tool (additive `add_to_order` merge bug) — PR 043.
- Forcing order read-back through ground-truth cart state (LLM
  hallucinating cart contents) — PR 044.
- `resolve_intent` phase-override fix for explicit add-item utterances
  during `order_type` phase — PR 045.
- No change to `preemptive_generation` — left enabled (latency win); the
  gap delay is sufficient to stop garbling without giving that up.

## How to Test

- [x] `PYTHONPATH=. uv run pytest tests/` — 143 passed, 7 pre-existing
      failures unrelated to this change (confirmed identical on `main`
      before this branch: `test_ambient_audio.py`, `test_menu_match.py`,
      `test_order_parse.py`), 2 new tests in `tests/test_session_config.py`
      pass
- [ ] Outbound test call (`scripts/test_call.py`): trigger a filler (ask
      price / availability mid-order) immediately followed by an add — confirm
      Sierra's two utterances are audibly separated, not run together
- [ ] `journalctl -u restaurant-agent -f | grep SIERRA:` during a live call —
      no more multi-language run-on lines mixing a filler string with a
      ladder/LLM line
- [ ] Confirm `FILLERS_ENABLED=1` test call: fillers still fire, just never
      collide with the main reply

## Post-Merge: VPS Pull Command

`cd /opt/livekit-sarvam && git pull origin main && uv sync && systemctl restart restaurant-agent`
