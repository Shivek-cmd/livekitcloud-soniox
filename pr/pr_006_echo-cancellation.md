# PR 006 — Fix: Echo cancellation on microphone

## Problem
Agent's audio played through the speaker was being picked up by the mic,
causing the agent to hear itself and respond twice (echo feedback loop).

## Fix
Explicitly set `echoCancellation: true`, `noiseSuppression: true`, and
`autoGainControl: true` when enabling the microphone track in the browser.

## Files Changed
- `web/src/App.tsx` — added audio constraints to `setMicrophoneEnabled()`
