# Project Overview

## What We're Building

A **Punjabi-first restaurant voice agent** that handles:
- Food orders (pickup and delivery)
- Reservation bookings
- Menu queries and recommendations

Customers call a phone number or open a web link — the agent answers in Punjabi, takes their order naturally, and confirms it. No human staff needed for routine order-taking.

---

## Target Users

Punjabi-speaking customers ordering from a Punjabi restaurant. Primary channel is phone (most restaurant callers use phone, not apps). Web is secondary for tech-savvy users.

---

## Why This Stack

| Concern | Choice | Reason |
|---|---|---|
| Real-time voice transport | LiveKit (self-hosted) | Open-source WebRTC, full control, no per-minute billing |
| Phone channel | Twilio SIP | Tested with LiveKit, Indian +91 numbers available |
| STT | Sarvam Saaras v3 | Best Indian-language STT, native `pa-IN` (Punjabi) support |
| LLM | Sarvam-30B | Understands Punjabi context, fast enough for real-time |
| TTS | Sarvam Bulbul v3 | Natural Punjabi voice output |
| Plugin bridge | `livekit-plugins-sarvam` | Official LiveKit plugin — STT + TTS + LLM in one package |

---

## Channels

| Channel | How | Who Uses It |
|---|---|---|
| Phone | Twilio → SIP → LiveKit → Agent | Majority of restaurant callers |
| Web | Browser → WebRTC → LiveKit → Agent | Tech-savvy, younger customers |

Same agent code handles both. Customer experience is identical.

---

## Agent Capabilities (Phase 1 Scope)

### Order Taking
- Accept food orders for pickup or delivery
- Handle multi-item orders ("2 paneer burgers and a mango lassi")
- Clarify ambiguities ("ਕੀ ਤੁਸੀਂ ਸਪਾਈਸੀ ਚਾਹੁੰਦੇ ਹੋ?")
- Confirm order before placing ("ਕੀ ਇਹ ਠੀਕ ਹੈ?")
- Collect delivery address and contact number

### Reservation Booking
- Take date, time, party size
- Confirm availability
- Collect customer name and phone number

### Menu Queries
- Answer "ਕੀ ਤੁਹਾਡੇ ਕੋਲ X ਹੈ?" (do you have X?)
- Today's specials
- Allergen/dietary queries (vegetarian, vegan)
- Prices

---

## Language Behaviour

- **Primary**: Punjabi (Gurmukhi script in LLM, audio `pa-IN`)
- **Code-mixed**: Handles Punjabi + English naturally ("delivery ਲਈ ਚਾਹੀਦਾ" = "want it for delivery")
- **Fallback**: If STT detects Hindi or English, agent responds in same language (Phase 2)

---

## Latency Goal

**< 1.2 seconds** from end of customer speech to first agent audio output on both web and phone. This requires all three streaming layers active (STT streaming + LLM streaming + TTS streaming). See [09-latency-analysis.md](09-latency-analysis.md) for full breakdown.
