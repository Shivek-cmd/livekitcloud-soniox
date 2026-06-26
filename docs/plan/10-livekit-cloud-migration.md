# Plan 10 — LiveKit Cloud Migration (echo fix + production multi-tenant)

## Why we're doing this
Live VPS logs proved the phone "voice breaking" is **telephony line echo**: the agent
hears its own voice reflected back over the SIP/PSTN path (confirmed on BOTH speakerphone
and handset). Self-hosted LiveKit has no production-grade echo cancellation for telephony.
LiveKit Cloud provides **Krisp `BVCTelephony`** — a voice-cancellation model purpose-built
for SIP/phone participants — which is the real fix.

Secondary win: Cloud removes the self-hosted fragility we already hit (nameless-worker
dispatch collisions, no GitHub auth on the box, manual systemd/docker juggling) and gives
managed SIP, a telephony dashboard, and per-call PCAPs for debugging.

## Key facts that shape the plan
- **We keep Sarvam.** Punjabi STT/LLM/TTS stay on the Sarvam plugins (treated as "external
  models"). LiveKit Inference is NOT used → $0 inference through LiveKit. Our Sarvam bill is
  unchanged.
- **The echo fix is cheap:** Krisp `BVCTelephony` is voice-isolation priced at ~$0.0012/min
  (100 min free on Build, 1,000 min included on Ship).
- **Multi-tenant does NOT need one deployment per restaurant.** A single agent deployment
  serves all tenants by reading `restaurant_id` (and prompt/menu/number config) from the
  dispatch/job metadata per call. (The soniox error we saw — "No restaurant_id in job
  metadata" — is literally this pattern.)

## Cost summary (per-minute, our setup)
| Component | $/min |
|---|---|
| Agent session (Cloud hosting) | 0.010 |
| Third-party SIP via Twilio (LiveKit side) | 0.004 |
| Twilio's own per-min (separate bill) | ~0.008 |
| Krisp BVCTelephony (echo fix) | 0.0012 |
| Sarvam STT/LLM/TTS | unchanged |
| **LiveKit + telephony subtotal** | **~0.023/min** |

Plans: **Build $0** (test), **Ship $50/mo** (launch), **Scale $500/mo** (many tenants).

---

## Phase 0 — FREE echo test (Build tier, no card, VPS untouched)
Goal: prove BVCTelephony kills the echo before paying or migrating anything.

1. **Create a free LiveKit Cloud project** at cloud.livekit.io (Build plan, $0).
2. Grab the project **URL**, **API key**, **API secret** from the project settings.
3. Point a number at the Cloud project (either option):
   - **Option A (simplest):** use the 1 free LiveKit Cloud number; call it directly.
   - **Option B (reuse Twilio):** create an inbound SIP trunk on Cloud and point the Twilio
     trunk's SIP URI at the Cloud SIP host. Keeps our existing number.
4. **Run the same agent against Cloud** (new env vars only — no code logic change):
   - `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET` → Cloud values.
5. **Enable the echo fix** (one line):
   - In `agent.py` `session.start(...)` add `BVCTelephony()` noise cancellation, AND/OR set
     `krisp_enabled: true` on the Cloud inbound trunk.
6. **Test call** → success = the "Sierra hears herself / parrots herself" loop is gone.

Decision gate: echo gone → proceed to Phase 1. Echo remains → pivot to ai-coustics, $0 spent.

## Phase 1 — Production migration (Ship tier)
1. Upgrade the proven project to **Ship ($50/mo)**.
2. Move telephony fully to Cloud (Cloud numbers, or Twilio→Cloud SIP for existing numbers).
3. Deploy the agent to Cloud (managed) with `agent_name="restaurant-agent"` (explicit
   dispatch already done in PR 020).
4. Keep BVCTelephony on for every call.
5. Point the web token server / frontend at the Cloud URL.
6. Keep the VPS as a hot fallback for one week, then decommission.

## Phase 2 — Multi-tenant SaaS structure (future)
- One agent deployment; per-call `restaurant_id` in dispatch metadata.
- Per-number → tenant mapping (inbound trunk / dispatch rule per restaurant number).
- Per-tenant prompt, menu, voice, hours loaded from a tenant store keyed by `restaurant_id`.
- Concurrency: Ship = 20 concurrent sessions; Scale = up to 600.

## Rollback
The self-hosted VPS stack stays fully intact during Phase 0 and Phase 1. If anything
regresses, calls route back to the VPS by reverting the Twilio SIP URI. No destructive steps
until the Cloud path is verified end-to-end.

## What I need from you to start Phase 0
- A LiveKit Cloud project created (Build, free), and its **URL + API key + API secret**.
- Confirmation of test number choice: **Option A (free LiveKit number)** or **Option B
  (reuse Twilio number)**.
