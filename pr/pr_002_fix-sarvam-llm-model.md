# PR 002 — Fix: Update Sarvam LLM model name

## Summary
`sarvam-30b-16k` was deprecated by Sarvam AI. Updated to `sarvam-30b`.

## Error
```
Model 'sarvam-30b-16k' has been deprecated.
Please use one of the available models instead: sarvam-30b, sarvam-105b.
```

## Files Changed
- `agent.py` — line 243: `sarvam.LLM(model="sarvam-30b-16k")` → `sarvam.LLM(model="sarvam-30b")`

## Test
Agent connected to LiveKit Cloud Console, greeting played via TTS, LLM now responds when user speaks.
