# PR 046 — LLM prompt-cache warmup at call start

## Branch
`pr_046_llm-cache-warmup`

## Problem (live call, confirmed via VPS logs 2026-07-06)

Every call's **first** LLM turn was slow — `llm_ttft` 3.25–3.69s — while every turn after
it settled to 0.6–1.6s in the same call. Root cause, confirmed from `turn-latency` logs:

| Turn | `prompt_tokens` | `prompt_cached_tokens` | `llm_ttft` |
|---|---|---|---|
| 1 (first) | 1443 | **0** | **3.69s** |
| 2 | 1488 | 1408 | 1.6s |
| 3 | 1530 | 1408 | 1.63s |
| ... | ... | 1536–1792 | 0.63–1.41s |

OpenAI caches the longest common request prefix (the ~1400-token system prompt) but the
cache expires after a few minutes idle (or a service restart). The caller's very first
utterance always lands on a cold, uncached prefix — a 3+ second dead-air pause right
after the fixed greeting, which read as the voice being "clumsy" / breaking mid-call.

Ruled out: network to `api.openai.com` (2–11ms ping, 430ms full TLS+request), Soniox
STT/TTS (fast, `ttfb≈0.25s`), VPS memory/CPU.

## Fix

Fire a throwaway OpenAI completion with the same system-prompt prefix the moment a call
connects, running in parallel with SIP pickup + the fixed `OPENING_GREETING` playback
(which itself takes 5–8s of TTS audio). By the time the caller finishes their first real
sentence, the cache is warm, so the real first turn gets the normal ~0.6–1.6s `llm_ttft`
instead of ~3.5s.

This is a fire-and-forget side call — it never touches the real `AgentSession` /
`ChatContext`, so it can't affect conversation state, tool calls, or transcripts.

## Files Added

### `restaurant/llm_warmup.py`
- `warmup_enabled()` — `LLM_WARMUP_ENABLED` env kill switch (default on).
- `warm_llm_cache(is_phone)` — one-token throwaway `AsyncOpenAI` completion using
  `build_system_prompt(is_phone=...)` as the system message; logs `LLM_WARMUP ok/failed`
  with elapsed time; swallows all exceptions (never allowed to affect the real call).
- `schedule_llm_warmup(is_phone)` — fire-and-forget `asyncio.create_task` wrapper, no-op
  if disabled.

### `tests/test_llm_warmup.py`
Env kill-switch defaults/override, successful warmup call shape (model, one-token,
system prompt content), exception swallowing, and task-scheduling (mirrors
`tests/test_call_control.py` patterns).

## Files Modified

### `agent.py`
- Import `schedule_llm_warmup` from `restaurant.llm_warmup`.
- Call `schedule_llm_warmup(is_phone=is_phone)` in `entrypoint()` right after `is_phone`
  is resolved (before `session.start()` / greeting), so it races the greeting instead of
  blocking anything.

## What's NOT in This PR

- No continuous/background cache-priming independent of calls (option #2 from
  discussion) — only warms at call start.
- No filler/"one moment" phrase for turn 1 (option #3) — can be a follow-up if warmup
  timing ever proves insufficient.
- No system-prompt shrinking.

## How to Test

```bash
pytest tests/test_llm_warmup.py -q
```

Live: place a test call, watch for `LLM_WARMUP ok channel=phone elapsed=...` in logs
right after `Session started`, then confirm turn-1 `llm_ttft` in the `LATENCY` log line
drops to the same range as later turns:

```bash
journalctl -u restaurant-agent -f | grep -E 'LLM_WARMUP|LATENCY|llm_ttft'
```

Kill switch if this ever causes issues: `LLM_WARMUP_ENABLED=0`, restart agent.

## Post-Merge: VPS Pull Command
`cd /opt/livekit-sarvam && git pull origin main && uv sync`
