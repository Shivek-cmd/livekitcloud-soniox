# Milestones & Build Phases

## Phase 1 — Agent Core ✅ DONE
Working Punjabi voice conversation, agent pipeline validated.
- Python project (`uv`, `pyproject.toml`, `.env`)
- `agent.py` — STT → LLM → TTS pipeline + restaurant tools (orders, reservations, menu)
- `token_server.py` — FastAPI token + agent dispatch (web)

## Phase 2 — Web Channel ✅ DONE
- React web app ("Start Call" + voice UI), served via Caddy at `sarvam.bizbull.ai`
- Token server dispatches the agent on each web call

## Phase 3 — Phone Channel (Twilio SIP) ✅ DONE
- Twilio number `+15878175156` → SIP → LiveKit
- `scripts/setup_sip.py` (trunk + dispatch) and `scripts/test_call.py` (outbound tester)

## Phase 4 — Echo Fix (LiveKit Cloud migration) ✅ DONE
**Problem:** phone **echo / voice breaking** — the self-hosted setup had no usable echo cancellation
(Krisp is Cloud-only). **Fix:** migrated to **LiveKit Cloud**. Verified on a real call: clean,
multi-turn Punjabi conversation, no self-echo barge-in. Trunk-level Krisp NC enabled.

## Phase 5 — Latency Fix (Soniox + GPT stack) ✅ DONE
**Problem:** latency for Canada callers — the previous STT/LLM/TTS were India-hosted (~3 US↔India
round-trips per turn). **Fix:** replaced the whole India-hosted stack with **Soniox STT + GPT LLM +
Soniox TTS** (US/EU/JP-hosted) and enabled `preemptive_generation`. Soniox `Maya` voice chosen for
Punjabi. The old India-hosted provider was **fully removed** from code, docs, and the VPS.

## Phase 6 — Quality Tuning (in progress)
| Task | Status |
|---|---|
| Punjabi voice quality pass (Soniox voices) | ⬜ |
| Latency profiling — measure TTFA end-to-end | ⬜ |
| STT accuracy across Punjabi accents | ⬜ |
| Digit/phone-number read-back accuracy | ⬜ |
| Inbound Twilio routing → Cloud SIP for real customer calls (verify prod) | ⬜ |

## Phase 7 — Features (deferred)
| Feature | Notes |
|---|---|
| **Multi-tenant** | Per-restaurant number, prompt, voice config (the SaaS goal) |
| Order persistence | Save orders to a database |
| Order webhook | Notify POS/kitchen on new order |
| Outbound calls | Agent proactively calls users |
| Analytics | Transcript logging, latency dashboard |
| WhatsApp channel | Via LiveKit SIP connectors |

## What NOT to build yet
- No database / persistence — deferred
- No order webhook — deferred
- No multi-tenant architecture yet — but `voice_stack.py` is structured to make per-tenant voice
  config easy when we get there
- Inbound only (no outbound)
