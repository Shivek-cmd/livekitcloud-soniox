# PR 017 — Sarvam best practices: flush_signal, turn_detection, auto language, fast endpointing

## Branch
`pr_017_sarvam-best-practices`

## What This PR Does
Applies all official Sarvam + LiveKit best practices from the Sarvam documentation.
Fixes the root cause of the echo loop and reduces response latency significantly.

## Changes

### agent.py

**`flush_signal=True` on STT**
- Enables Sarvam's server to emit speech start/end events.
- Without this, turn detection has no signal to work from — turn-taking is broken.

**`turn_detection="stt"` on AgentSession**
- Tells LiveKit to use Sarvam's VAD for turn detection instead of a generic timer.
- Combined with flush_signal, this is what allows Sarvam to properly suppress the
  agent's own voice from being detected as user input (the echo loop fix).

**`min_endpointing_delay` corrected**
- Was: 0.8s for phone, not set for web (defaulted to something slow)
- Now: 0.07s for web, 0.2s for phone
- Sarvam STT has ~70ms processing latency. The delay was adding 700ms+ of silence
  after every user utterance before the LLM kicked in. Latency drops significantly.

**`language="unknown"` on STT (auto-detect)**
- Was: `language="pa-IN"` (Punjabi only — rejected any other language at STT level)
- Now: `language="unknown"` (auto-detects English, Hindi, Punjabi, and other Indian languages)
- The LLM already detects and mirrors the caller's language. Now the STT will actually
  transcribe what they say correctly regardless of language.

**Removed `phone_session_extras` dict**
- Was a separate dict unpacked into AgentSession. Inlined directly for clarity.

## What's NOT changed
- TTS still uses `target_language_code="pa-IN"` — Bulbul v3 can render text in multiple
  languages regardless. Dynamic per-turn TTS language switching is a future improvement.
- Phone STT VAD params unchanged (num_initial_ignored_frames etc.)
- All prompt, menu, and order logic unchanged.

## How to Test
```bash
# Deploy
cd /opt/livekit-sarvam && git pull origin main && systemctl restart restaurant-agent

# Test in English
uv run python scripts/test_call.py +91XXXXXXXXXX
# Say: "hi I want to order butter chicken"

# Test in Hindi
# Say: "haan ji, mujhe butter chicken chahiye"

# Test in Punjabi
# Say: "haan ji, mein butter chicken lena chahunda haan"

# Watch logs
journalctl -u restaurant-agent -f | grep -E "USER:|SIERRA:|Session started"
```

## Expected improvements
- Echo loop should be significantly reduced (turn_detection="stt" + flush_signal)
- Response latency should drop by ~700ms on web calls
- Hindi and English callers now transcribed correctly (was garbled before)

## Post-Merge: VPS Pull Command
```bash
cd /opt/livekit-sarvam && git pull origin main
systemctl restart restaurant-agent
```
