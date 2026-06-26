# Project Overview

## What We're Building

A **Punjabi restaurant voice agent** named **Sierra** for **Bizbull Restaurant** that handles:
- Food orders (pickup and delivery)
- Reservation bookings
- Menu queries and recommendations

Customers call a phone number or open a web link — Sierra answers in natural Punjabi-English (the way real Canadian Punjabi restaurant staff speak), takes the order, and confirms it. No human staff needed for routine order-taking.

---

## Target Users

Punjabi-speaking customers ordering from a Punjabi restaurant. Primary channel is phone (most restaurant callers use phone, not apps). Web is secondary for tech-savvy users.

---

## Why This Stack

| Concern | Choice | Reason |
|---|---|---|
| Real-time voice transport | LiveKit (self-hosted) | Open-source WebRTC, full control, no per-minute billing |
| Phone channel | Twilio SIP | Tested with LiveKit, Canadian numbers available |
| STT | Sarvam Saaras v3 | Best Indian-language STT, native `pa-IN` (Punjabi) support |
| LLM | Sarvam-30B | Understands Punjabi context, fast enough for real-time |
| TTS | Sarvam Bulbul v3 | Natural Punjabi voice output, handles code-mixed Punjabi+English |
| Plugin bridge | `livekit-plugins-sarvam` | Official LiveKit plugin — STT + TTS + LLM in one package |

---

## Channels

| Channel | How | Status |
|---|---|---|
| Phone | Twilio → SIP → LiveKit → Agent | **Live** — `+15878175156` |
| Web | Browser → WebRTC → LiveKit → Agent | **Live** — `https://sarvam.bizbull.ai` |

Same agent code handles both. Customer experience is identical.

---

## Agent Capabilities (Phase 1 Scope)

### Order Taking
- Accept food orders for pickup or delivery
- Handle multi-item orders ("2 paneer tikka and a mango lassi")
- Ask spice level (mild/medium/spicy) for all starters and mains
- Ask for special instructions per item
- Collect name and phone number (digit by digit)
- Confirm full order before placing

### Reservation Booking
- Take date, time, party size
- Confirm availability
- Collect customer name and phone number
- Provide reference number

### Menu Queries
- Answer questions about specific items
- Suggest popular dishes
- Handle dietary queries (vegetarian options, etc.)
- Quote prices

---

## Language Behaviour

- **Style**: Natural mix of Punjabi and English — the way real Canadian Punjabi restaurant staff speak
- **English words used always**: numbers, "mild/medium/spicy", "pickup/delivery", food item names, prices
- **Punjabi used for**: warmth and conversational flow — "ਹਾਂ ਜੀ", "ਠੀਕ ਹੈ ਜੀ", "ਬਿਲਕੁਲ ਜੀ"
- **Numbers**: always spoken digit by digit in English
- **Adaptation**: if the customer speaks more English, Sierra leans more English

---

## Latency Goal

**< 1.2 seconds** from end of customer speech to first agent audio output on both web and phone. This requires all three streaming layers active (STT streaming + LLM streaming + TTS streaming). See [09-latency-analysis.md](09-latency-analysis.md) for full breakdown.

---

## Reference & Diagnosis

- **[../reference/](../reference/README.md)** — captured Sarvam + LiveKit docs (TTS, STT, turn detection/interruptions, noise cancellation) so we don't re-paste them each session.
- **[../diagnosis/phone-call-quality.md](../diagnosis/phone-call-quality.md)** — root-cause analysis of the phone "slow voice" and "voice breaking / echo" problems.
