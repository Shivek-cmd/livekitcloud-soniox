# PR 012 — Fix web audio + phone barge-in cutoff

## Problems fixed

### 1. Web: agent generates audio but browser plays nothing
TTS was working (logs showed "WebSocket session completed successfully") but browsers
block audio autoplay unless the AudioContext is explicitly resumed after user gesture.
`el.autoplay = true` alone is not sufficient.

**Fix:**
- Added `await room.startAudio()` immediately after `room.connect()` — resumes the
  AudioContext while we are still inside the user's click gesture
- Added `el.play().catch(() => {})` on each attached audio element as a fallback

### 2. Phone: agent speaks a few words then stops (5/10 calls)
Phone audio from the speaker leaks back into the microphone (acoustic echo). The STT
detects this as user speech, which triggers an interruption and cuts the agent off
mid-sentence.

**Fix:**
- `interrupt_speech_duration=1.5` — requires 1.5s of continuous detected speech before
  the agent stops talking (default is 0.5s — too sensitive for phone echo)
- `min_endpointing_delay=0.8` — waits longer before treating silence as end-of-turn,
  reducing false triggers from phone line noise

### 3. Minor: web UI still said "Punjab Da Dhaba"
Updated to "Bizbull Restaurant" to match the agent's name.

## Files changed
- `web/src/App.tsx` — `startAudio()`, explicit `play()`, restaurant name
- `agent.py` — `interrupt_speech_duration`, `min_endpointing_delay`
