# PR 019 — STT: codemix mode + 8kHz sample rate for phone

## Branch
`pr_019_codemix-phone-samplerate`

## What This PR Does
Two STT improvements based on the official Sarvam "Building for Indian Languages" guide.

## Changes

### agent.py — `sarvam.STT()`

**`mode="codemix"` (was `"transcribe"`)**

In `transcribe` mode, callers saying "2 butter chicken chahiye" produce:
  `"2 बटर चिकन चाहिए"` — our `find_item("बटर चिकन")` returns nothing.

In `codemix` mode, English words stay in English:
  `"2 butter chicken चाहिए"` — `find_item("butter chicken")` matches correctly.

This directly fixes a silent failure mode where callers order in Punjabi/Hindi
but the menu lookup fails because item names got transliterated into Gurmukhi/Devanagari.

**`sample_rate=8000 if is_phone else 16000` (was always `16000`)**

Per Sarvam docs: "Saaras v3 is tuned for telephony. For 8kHz audio, set sample_rate=8000."
Phone SIP audio arrives at 8kHz natively. Sending 8kHz audio with `sample_rate=16000` causes
LiveKit to upsample it, which adds noise and degrades transcription quality. Matching the
native phone rate gives Saaras the signal it was optimised for.

## Files Modified
- `agent.py` — `sarvam.STT()` configuration only

## How to Test
```bash
cd /opt/livekit-sarvam && git pull origin main && systemctl restart restaurant-agent

uv run python scripts/test_call.py +91XXXXXXXXXX

# Say in Hindi: "haan ji, mujhe 2 butter chicken chahiye"
# Expect: agent finds "butter chicken" and asks spice level (not "sorry, not on menu")

# Watch logs:
journalctl -u restaurant-agent -f | grep "USER:"
# Should see: USER: 2 butter chicken चाहिए  ← English name preserved
```

## Post-Merge: VPS Pull Command
```bash
cd /opt/livekit-sarvam && git pull origin main
systemctl restart restaurant-agent
```
