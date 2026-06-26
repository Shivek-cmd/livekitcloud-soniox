# PR 020 — Phone Call Humanization (echo, voice, latency)

## Branch
`pr_020_phone-humanization`

## What This PR Does
Single PR holding the step-by-step fixes for the phone call quality problems:
voice breaking/echo (Sierra interrupting herself), slow voice, and latency.
Each fix is applied and tested one at a time. This doc is updated as fixes land.

Backed by the diagnosis in `docs/diagnosis/phone-call-quality.md` and the captured
references in `docs/reference/`. All changes verified available in `livekit-agents 1.6.3`
(no upgrade needed — see the diagnosis doc's "Version compatibility — VERIFIED" section).

## Fixes in this PR

### ✅ Fix 1 — Un-interruptible greeting
`agent.py`: the opening `session.say(...)` now passes `allow_interruptions=False`.
Sierra's greeting always plays in full and can no longer be cut off by the echo of
her own TTS coming back over the SIP/phone path. Directly addresses the worst symptom
(voice breaking at the start of the call). Only the greeting is affected; the rest of
the conversation stays fully interruptible.

### ⬜ (planned, not yet applied — added one at a time with approval)
- Fix 2 — `min_interruption_words` so only real words (not echo) interrupt Sierra.
- Fix 3 — add Silero VAD + move off bare `turn_detection="stt"` to the recommended turn detector.
- Fix 4 — `resume_false_interruption` + `false_interruption_timeout` recovery.
- Fix 5 — reset hand-tuned Sarvam fine-grained VAD frame params to defaults.
- Fix 6 — voice/pace pass: phone `pace` back to 1.0, A/B speakers, TTS buffer for faster first audio.
- Fix 7 — latency: `preemptive_generation`, endpointing tuning, thinking fillers.
- Investigate `aec_warmup_duration` (built-in AEC) for phone echo.

## Files Added
- `pr/pr_020_phone-humanization.md` — this doc.
- `docs/reference/README.md`, `docs/reference/sarvam-tts-plugin.md`,
  `docs/reference/sarvam-stt-plugin.md`, `docs/reference/livekit-turn-detection-interruptions.md`,
  `docs/reference/livekit-noise-cancellation.md` — captured Sarvam + LiveKit knowledge base.
- `docs/diagnosis/phone-call-quality.md` — root-cause analysis + verified version compatibility.

## Files Modified
- `agent.py` — greeting `say()` gains `allow_interruptions=False` (Fix 1).
- `docs/plan/01-overview.md` — links to the new reference + diagnosis docs.
- `.gitignore` — ignore `.cursor/mcp.json` (holds the Sarvam API key; must never be committed).

## What's NOT in This PR
- No move to LiveKit Cloud. Code-level fixes first; Cloud/ai-coustics only if echo persists after.
- No `livekit-agents` upgrade (all needed params confirmed present in 1.6.3).
- No noise-cancellation model added yet.

## How to Test
```bash
cd /opt/livekit-sarvam && git pull origin main && systemctl restart restaurant-agent
uv run python scripts/test_call.py +91XXXXXXXXXX
# Listen: the full greeting should always play cleanly with no cut-out at the start.
journalctl -u restaurant-agent -f | grep -E "USER:|SIERRA:"
```

## Post-Merge: VPS Pull Command
```bash
cd /opt/livekit-sarvam && git pull origin main && systemctl restart restaurant-agent
```
