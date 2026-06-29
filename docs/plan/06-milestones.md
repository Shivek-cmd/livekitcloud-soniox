# Milestones & Build Phases

## Phase 1 — Agent Core ✅ DONE
Working Punjabi voice conversation, agent pipeline validated.
- Python project (`uv`, `pyproject.toml`, `.env`)
- `agent.py` — STT → LLM → TTS pipeline + restaurant tools (orders, reservations, menu)
- `token_server.py` — FastAPI token + agent dispatch (web)

## Phase 2 — Web Channel ✅ DONE (expanded 2026-06-28)
- React web app at **`https://voice.bizbull.ai`** (migrated from `sarvam.bizbull.ai`, PR 009)
- Token server: `/token`, `/menu`, `/health` (Caddy → port 8001)
- **Order with Sierra** tab: W1 shell + W2 live cart (PR 011–012) — see `docs/plan/11-web-order-with-sierra.md`
- Store tab: placeholder

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

## Phase 6 — Quality Tuning

| Task | Status |
|---|---|
| **Tier A — phone latency** (TurnDetector, preemptive TTS, 0.5s endpointing) | ✅ PR 008 + PR 023 follow-up — see `docs/HANDOFF.md` |
| **Web shared latency** (same 0.5s endpointing as phone) | ✅ PR 013 + PR 023 follow-up |
| Per-turn latency logging (`LATENCY` lines) | ✅ `restaurant/turn_latency.py` |
| Natural menu offers (no 1-2-3 lists) | ✅ search cap + prompt (partial — LLM can still slip) |
| **Tier B — conversation layer** (prompts, intents, order flow in code) | ✅ PR 015 on `main` |
| **Tier B — phone hardening** (phrases, echo, confirm) | ⬜ PR 016–017 open — see `docs/HANDOFF.md` |
| **Tier B — customer language** (greeting, script detect) | ⬜ PR 018 open (stacked on 017) |
| **Speech policy fixes** (Mango drinks, chole/bhature TTS) | ✅ PR 019 on `main` |
| Punjabi voice quality pass (Soniox voices) | ⬜ |
| STT accuracy across Punjabi accents | ⬜ |
| Digit/phone-number read-back accuracy | ⬜ |
| Inbound Twilio routing → Cloud SIP for real customer calls (verify prod) | ⬜ |

## Phase 8 — Clover POS integration (planning → in progress)
Voice orders flow into restaurant Clover POS. See **`09-clover-pos.md`** for full plan.

| Sub-phase | Scope | Status |
|---|---|---|
| 8a | Sandbox probe — menu read + test atomic order | ✅ |
| 8b | Menu cache + tenant store + voice labels + menu tools | ✅ |
| 8c | Agent order placement + kitchen print | ⬜ **Next** |
| 8d | Webhooks + availability | ⬜ |
| 8e | Production pilot (one merchant, OAuth) | ⬜ |
| 8f | Multi-tenant routing (SaaS) | ⬜ |

## Phase 7 — Web "Order with Sierra" (in progress)

See **`11-web-order-with-sierra.md`**.

| Phase | Scope | Status |
|-------|--------|--------|
| W1 | Tab shell, 3-panel layout, live menu, captions | ✅ PR 011 |
| W2 | Live order panel, hybrid tap-to-add, `web_sync.py` | ✅ PR 012 |
| W3 | Menu highlight, modifier picker, tap-add ack | ⬜ **Next** |
| W4 | Avatar | ⬜ |
| W5 | Hardening | ⬜ |
| W6 | Web prompt variant | ✅ PR 015 (`restaurant/prompts.py`) |
| Ambient | Web background audio loop (web only) | ✅ PR 020 (+ volume PR 021 open) |

## Phase 9 — Other features (deferred)

| Feature | Notes |
|---|---|
| **Multi-tenant** (non-POS) | Per-restaurant voice config — partially overlaps Phase 8f |
| Order webhook to external POS | Covered by Clover in Phase 8 |
| Outbound calls | Agent proactively calls users |
| Analytics | Transcript logging, latency dashboard |
| WhatsApp channel | Via LiveKit SIP connectors |
| **Store tab** (web) | Browse/order without call — after W3–W6 |

## What NOT to build yet
- No delivery / pay-on-call / non-Clover POS — see `09-clover-pos.md` out-of-scope list
- No public Clover App Market listing until after pilot
- Inbound only (no outbound)
