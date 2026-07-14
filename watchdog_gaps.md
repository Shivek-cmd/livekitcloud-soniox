# Watchdog gaps — audit findings & handoff (PR 067)

Deep audit of the turn-handling voice pipeline (VAD → Soniox STT →
turn detector → endpointing → EOU watchdog → `commit_user_turn`), performed
2026-07-12 during local testing of PR 067 (`pr_067_eou-watchdog`) per
`localtesting.md`. Every claim below was verified against the installed
`livekit-agents` / `livekit-plugins-soniox` 1.6.5 source and live call logs.
Companion docs: `turnwatchdog.md` (original plan), `pr/pr_067_eou-watchdog.md`.

## State (updated 2026-07-13)

The whole stack is **merged to `origin/main`**: PRs 059–063 (hybrid-brain
rebuild, #96/#97), PR 064 (#106), PR 065 (#103), PR 066 (#104), and PR 067
(#105). The two fixes from the audit session landed inside PR 067 (commit
`5fe80d7`): `_ConfigInjectingWS` delegates `__aiter__` (pre-fix, dunder
lookup bypassed `__getattr__`, the plugin's `async for msg in ws` loop
crashed on every connect and the WS reconnect-looped → zero transcripts
whenever the PR 065/066 config injection was active — **pre-fix latency
measurements for those PRs are invalid and must be re-taken**), and the EOU
watchdog re-arms its timer when a non-final interim arrives while
`user_state == "listening"` (observed live: timer expired at EOU+2.0s, first
interim at EOU+4.0s, 4.9s unrescued stall). The TEMP diagnostics log line was
removed before merge.

**Findings 1–6 are now fixed** (2026-07-13) — findings 1–5 in PR 068
(`pr_068_watchdog-gap-fixes`: `restaurant/channels/eou_watchdog.py`,
`tests/test_eou_watchdog.py`) and finding 6 in PR 069
(`pr_069_ws-connect-handle`: `restaurant/voice_stack.py`,
`tests/test_voice_stack.py`). One
deviation from the finding-2 plan as written: step 3's "skip the reset if a
real `is_final` arrived" cannot key off `user_input_transcribed` — the forced
commit's interim promotion emits an identical-looking final on the event bus
(agent_activity.py:2020). Real finals are detected instead by probing
`_audio_recognition._last_final_transcript_time` (only stamped by real STT
finals, audio_recognition.py:1115); on probe failure the watchdog errs toward
resetting (spurious reset = one reconnect; missed reset = phantom turn).

After both fixes, a full test call ran clean: transcript_delay 26–613ms,
eou_delay 0.5–0.9s, stop→speaking 1.7–3.7s over 12 turns. Caveat: Soniox
finalized every turn on its own in that call, so the watchdog's forced-commit
path has **not yet been observed firing on a real stall**.

## What was verified correct

- Explicit tuned VAD (PR 066) really flips `_using_default_vad=False`;
  `audio_recognition.py` then trusts VAD end-of-speech timestamps. The
  watchdog's anchor — `user_state → "listening"` on VAD END_OF_SPEECH after
  `VAD_MIN_SILENCE_SEC` (0.25s) — is the right signal.
- Soniox endpoint knobs reach the server: `max_endpoint_delay_ms` and
  `endpoint_sensitivity` via `STTOptions`; `endpoint_latency_adjustment_level`
  via the WS config injection (functional after the `__aiter__` fix; Soniox
  accepted the merged config in live calls).
- `session.commit_user_turn()` is a legitimate rescue with non-manual turn
  detection in 1.6.5: promotes the interim to a final, appends it to the
  turn, runs EOU detection (`trigger="manual"`), generates a reply.
- No double-commit race on a timely final: single event loop — a final
  cancels the timer and clears `_has_interim` before an expired timer can
  act; `agent_state in ("thinking", "speaking")` guards the reply window.

## Findings (PR 067 merged without these; 1–5 fixed in PR 068, 6 in PR 069)

### 1. HIGH — silence flush is a no-op in live calls; rescue costs ~4s

`agent_activity.py:1481` passes `audio_detached=not session.input.audio_enabled`.
With a live mic that is False, and `audio_recognition.py:954` only pushes
silence frames when `audio_detached` is true — so `stt_flush_duration` does
nothing in our deployment. A watchdog rescue is therefore: 2.0s timer + up to
2.0s `transcript_timeout` waiting for a final that (under noise) won't come →
fall back to interim ≈ 4–4.5s dead air. The module docstring's
"silence-flushes the STT" claim is wrong for attached audio.

**Fix:** drop `_TRANSCRIPT_TIMEOUT_SEC` to ~1.0 and correct the docstring.

### 2. HIGH — forced commit doesn't consume Soniox's eventual final → phantom turn / double reply

The forced commit promotes the interim, but Soniox's held final still arrives
5–30s later. The framework logs "transcript arrives after turn has been
committed" and treats the text as NEW turn content. Observed live (first test
call, 05:28:20): a stale ` हाँ।` final instantly committed as a fresh turn
(`eou_delay=0.00`) and Sierra answered the same utterance twice. Every real
watchdog rescue will be followed by exactly this.

**Fix (plan, replaces the earlier suggestion):** the originally proposed
match-and-drop in the `is_final` branch **cannot work** — traced in the
installed 1.6.5 source: `user_input_transcribed` is emitted synchronously
mid-way through `_on_stt_event` (audio_recognition.py:1100), and the same
coroutine then re-appends the stale text from a *local* variable (line 1116)
and schedules the EOU task (line 1147), overwriting anything a handler
clears. There is no hook between "final received" and "buffer appended /
EOU scheduled". The framework's only built-in suppression is
manual-turn-detection-only and gated on `_user_turn_committed`, which is
cleared right after commit — it never covers a 5–30s-late final.

Chosen design — **reset the STT stream after the forced commit lands**, in
`eou_watchdog.py` only:

1. When the watchdog fires, set `_pending_stt_reset = True`.
2. Subscribe to `agent_state_changed`; on transition to `"thinking"` (or
   `"speaking"`) with the flag set, clear it and call
   `session.clear_user_turn()`. Its `_update_stt(None); _update_stt(stt)`
   (audio_recognition.py:925-927) tears down the Soniox WS, and the plugin
   does **no** finalize/flush handshake on client-side close — the held
   final dies at the socket and never reaches the framework. The
   thinking-transition anchor matters: clearing earlier (e.g. on the commit
   future's done callback) would wipe `_audio_transcript` before the EOU
   task reads it at run time, emptying the very turn being committed.
3. Skip the reset if a real `is_final` arrived between fire and the
   thinking transition (Soniox finalized inside `transcript_timeout` —
   nothing stale is held).
4. Also drop the pending reset if `user_state` → `"speaking"` first (a new
   VAD-detected utterance means resetting would drop in-flight speech).
5. Log the reset at warning level so live-call logs show the path.

Why the reconnect is safe: the pipeline swap is synchronous (no await
between the two `_update_stt` calls, so no frames are dropped); audio
buffers in the new pipeline's unbounded channel during the ~100–300ms WS
connect; VAD/interruption is a separate pipeline and unaffected; and the
reset fires while the agent is thinking/speaking, when the user is least
likely to be talking. Cost: one Soniox reconnect per rescue (rare path).

Ordering note vs finding #4: in the `is_final` branch, handle the
stale-tracking state BEFORE resetting `_fired_this_turn`.

### 3. MEDIUM — re-arm path can commit mid-utterance when VAD misses speech

The re-arm (added this session) arms on the FIRST interim while listening and
fires 2s later even if interims are still streaming. If Silero (threshold
0.6) never flags the speech but Soniox is transcribing it, the commit lands
mid-sentence → truncated turn.

**Fix:** make the timer slide — reset it on every non-empty interim so it
fires 2s after the LAST token, not the first.

### 4. MEDIUM — `_fired_this_turn` only resets on a VAD "speaking" transition

If the next utterance is also VAD-missed (the same noise the watchdog exists
for), the flag stays True and the watchdog is dead for the rest of the call.

**Fix:** also reset it when a final transcript arrives (the `is_final` branch
of `_on_transcript`).

### 5. LOW — lifecycle/hygiene

The timer task survives session close; a post-close fire makes
`commit_user_turn` raise inside an unawaited task. The future returned by
`commit_user_turn` is discarded, so its exceptions are never retrieved.

**Fix:** cancel the timer on `session.on("close")`; add a logging
done-callback on the returned future. Also remove the TEMP debug line.

### 6. LOW — `_ConfigInjectingSession.ws_connect` returns a bare coroutine

aiohttp's `ws_connect` returns an awaitable *context manager*. The current
plugin awaits it, so this works — but it's the same duck-typing bug class as
the `__aiter__` one; a plugin upgrade using `async with` breaks it silently.

**Fix (optional hardening):** return a small object implementing both
`__await__` and `__aenter__`/`__aexit__`.

### 7. INFO — remaining slow turns are VAD-side, not STT-side

Turns showing negative `transcript_delay` with multi-second `eou_delay` mean
Silero kept extending `last_speaking_time` on background noise after the
final was already in hand. Knob: `VAD_ACTIVATION_THRESHOLD` (0.6 → ~0.7 per
its own docstring), not watchdog/Soniox settings. Separately, the
`turn-latency` line printing `transcript_delay=-3105ms` is confusing —
clamp or label preemptive turns.

## Out of scope for PR 067 (track separately)

- **Conversational loop:** "chicken tikka" vs "Chicken Tikka Masala" — LLM/
  menu matching cycled between "we have it", "mild/medium/spicy?", and "we
  don't have it" for 5 turns. Needs its own fix (menu-matching/prompt).
- **Turn-detector holds on short Punjabi replies** (`end_of_turn_probability`
  below the 0.36 unlikely-threshold) — PR 066 endpointing-tuning territory.

## Suggested verification once fixed

Per `localtesting.md`: local stack, continuous background noise near the mic,
short replies ("ਹਾਂ ਜੀ"). Expect `EOU watchdog: no final transcript … forcing
commit` followed by a reply in ≤ ~3.5s, and NO duplicate Sierra reply when
the stale final arrives later. Then re-measure PR 065/066 endpoint settings —
pre-`__aiter__`-fix numbers are invalid (see above).
