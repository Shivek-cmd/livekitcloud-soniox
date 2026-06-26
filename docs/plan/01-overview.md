# Project Overview

## What We're Building

A **Punjabi restaurant voice agent** named **Sierra** for **Bizbull Restaurant** that handles:
- Food orders (pickup and delivery)
- Reservation bookings
- Menu queries and recommendations

Customers call a phone number — Sierra answers in natural Punjabi-English (the way real Canadian
Punjabi restaurant staff speak), takes the order, and confirms it. No human staff needed for routine
order-taking. (A web channel also exists; phone is the primary focus.)

The longer-term goal is a **multi-tenant SaaS**: many restaurants, each with its own number, prompt,
and voice config.

---

## Target Users

Punjabi-speaking customers ordering from Punjabi restaurants **in Canada**. Primary channel is phone.

---

## The Stack (current)

| Concern | Choice | Why |
|---|---|---|
| Real-time voice transport | **LiveKit Cloud** | Managed WebRTC + telephony; clean echo cancellation; auto edge routing |
| Phone channel | **Twilio** Elastic SIP → LiveKit Cloud SIP | Canadian numbers; SIP relay into Cloud |
| STT | **Soniox** `stt-rt-v5` | Punjabi + code-mix, US/EU/JP-hosted (low latency for Canada) |
| LLM | **OpenAI** `gpt-4o-mini` | Fast, US-hosted, strong at Punjabi/English/Hindi code-mix text |
| TTS | **Soniox** `tts-rt-v1` (voice `Maya`) | Punjabi voice, US/EU/JP-hosted, streams pre-sentence (low latency) |
| Agent runtime | Python `livekit-agents`, self-hosted on VPS, connected to LiveKit Cloud | Full control of agent logic |

All three voice providers (STT/LLM/TTS) are hosted in North-America-reachable regions, so a Canada
caller's whole pipeline stays on-continent. See `../reference/soniox-stt-tts-plugin.md`.

> **History:** the project originally used an **India-hosted** STT+LLM+TTS stack on a **self-hosted**
> LiveKit server. That caused (a) phone **echo** and (b) **latency** for Canada callers. Moving to
> **LiveKit Cloud** fixed the echo, and switching to the **Soniox + GPT** stack fixed the latency.
> The old stack and the self-hosted server are no longer used by this project.

---

## Channels

| Channel | Path | Status |
|---|---|---|
| Phone | Caller → Twilio → **LiveKit Cloud SIP** → Cloud room → Agent | **Primary** — `+15878175156` |
| Web | Browser → WebRTC → LiveKit Cloud room → Agent | Secondary (token server + React app) |

Same `agent.py` handles both.

---

## Agent Capabilities (Phase 1)

### Order Taking
- Multi-item orders, spice level per starter/main, special instructions per item
- Collect name + phone (digit by digit), confirm full order before placing

### Reservation Booking
- Date, time, party size → availability → name + phone → reference number

### Menu Queries
- Item descriptions, recommendations, dietary (veg) queries, prices on request

---

## Language Behaviour

- Natural Punjabi + English code-mix (Canadian Punjabi restaurant style)
- English always for: numbers, "mild/medium/spicy", "pickup/delivery", item names, prices
- Punjabi for warmth: "ਹਾਂ ਜੀ", "ਠੀਕ ਹੈ ਜੀ", "ਬਿਲਕੁਲ ਜੀ"
- Numbers spoken digit by digit
- Adapts toward whichever language the caller leans on

---

## Where to look next

- `02-architecture.md` — current system architecture and call flow
- `07-twilio-sip.md` — phone path (Twilio → LiveKit Cloud SIP)
- `08-web-app.md` — web channel
- `06-milestones.md` — build phases and roadmap
- `../vps-config.md` — deployment, services, SIP IDs, env, ops commands
- `../reference/` — captured Soniox + LiveKit knowledge (so we don't re-paste docs each session)
