# Project Overview

## Goal

Build a real-time Punjabi voice agent using a self-hosted LiveKit server and Sarvam AI's Indian-language models.

## What It Does

A user speaks Punjabi into a browser/app. The agent listens, understands, generates a response using a large language model, and speaks back — all in Punjabi, in real-time.

## Why This Stack

| Concern | Choice | Reason |
|---|---|---|
| Real-time voice transport | LiveKit (self-hosted) | Open-source WebRTC, no vendor lock-in, full control |
| STT | Sarvam Saaras v3 | Best-in-class for Indian languages, native `pa-IN` support |
| LLM | Sarvam-30B / 105B | Trained on Indian languages, understands Punjabi context |
| TTS | Sarvam Bulbul v3 | Natural Punjabi voice output |
| Plugin bridge | `livekit-plugins-sarvam` | Official LiveKit plugin — STT + TTS + LLM all wired in |

## Language Focus

Primary: **Punjabi (`pa-IN`)**
Secondary: Hindi (`hi-IN`), English (`en-IN`) — code-mixed support via Saaras v3

## Scope (Phase 1)

- Self-host LiveKit server via Docker
- Build a Python voice agent worker
- Wire Sarvam STT → Sarvam LLM → Sarvam TTS pipeline
- Test end-to-end Punjabi conversation
- Basic system prompt tuned for Punjabi responses
