# PR 014 — Fix: Phone call pipeline (silent start, interruptions, wrong audio format)

## Branch
`pr_014_phone-pipeline-fix`

## What This PR Does
Fixes four architectural problems in the phone call path that caused: caller hearing nothing at the start, agent being interrupted by its own echo, random LLM responses triggered by line noise, and double audio transcoding through LiveKit SIP.

## Root Causes Fixed

### 1. No `wait_for_participant()` (silent start)
Agent connected to the room and immediately said the greeting before the SIP participant had fully joined. Greeting audio went into the room with nobody subscribed. Fix: `await ctx.wait_for_participant()` before starting the session.

### 2. `is_phone` detection ran before participant joined
`remote_participants` was empty at detection time → phone calls misidentified as web → wrong pace, wrong audio format, no phone-specific tuning. Fix: detect from the participant returned by `wait_for_participant()`.

### 3. Missing interruption and endpointing guards
`min_endpointing_delay` and `min_interruption_duration` are valid `AgentSession` params (confirmed from source). PR 012 used the wrong name `interrupt_speech_duration`; PR 013 removed both. Now added with correct names for phone channel only.

### 4. Sarvam STT VAD params not set for phone (`saaras:v3` supports these)
Phone line has connection noise, SIP handshake artifacts, and echo. Without VAD tuning these all trigger STT → random LLM responses. Added phone-specific:
- `num_initial_ignored_frames=10` — skip first ~500ms of connection noise
- `interrupt_min_speech_frames=8` — require ~400ms of speech before treating as interruption
- `first_turn_min_speech_frames=10` — stricter requirement on the very first turn
- `min_speech_frames=5` — require ~250ms to confirm speech generally

### 5. TTS audio format wrong for phone
`speech_sample_rate=22050, output_audio_codec="mp3"` forced LiveKit SIP to transcode MP3 at 22050 Hz down to G.711 at 8000 Hz for Twilio — double processing. Sarvam plugin natively supports mulaw at 8000 Hz and decodes it to PCM internally before LiveKit receives it. Phone now uses `speech_sample_rate=8000, output_audio_codec="mulaw"`.

## Files Modified

### `agent.py`
- Added `await ctx.wait_for_participant()` after `ctx.connect()`
- Moved `is_phone` detection to use the returned participant
- Split `AgentSession` into phone-aware path using `**extras` dicts
- Phone STT: added `num_initial_ignored_frames`, `interrupt_min_speech_frames`, `first_turn_min_speech_frames`, `min_speech_frames`
- Phone TTS: `speech_sample_rate=8000`, `output_audio_codec="mulaw"`
- Phone AgentSession: `min_endpointing_delay=0.8`, `min_interruption_duration=1.0`

## What's NOT in This PR
- VAD tuning values are initial estimates — exact frame sizes need to be confirmed against Sarvam API docs
- Latency from Sarvam API peak load is not addressed here (separate concern)
- Web channel is unchanged

## How to Test
```bash
# On VPS after pull
systemctl restart restaurant-agent

# Test phone: dial +15878175156
# Expected: greeting plays within 1-2s of call connecting
# Expected: agent speaks full sentences without being cut off
# Expected: background noise / echo does NOT trigger random responses

# Check logs
journalctl -u restaurant-agent -f
```

## Post-Merge: VPS Pull Command
```bash
cd /opt/livekit-sarvam && git pull origin main
systemctl restart restaurant-agent
```
