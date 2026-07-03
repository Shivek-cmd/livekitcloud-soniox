# PR 044 — Collecting-phase hardening (quantity, STT noise, auto-add)

## Branch
`pr_044_collecting-phase-hardening`

## Problem (live call after PR 043)

Caller said **“ਇੱਕ Amritsari Fish”** (voice line for Fish Pakora). Sierra:

1. Added correctly but **re-asked quantity** even though “ਇੱਕ” was already in speech  
2. **“ਵਨ”** (one) on the next turn was **filtered as background**  
3. Noisy STT (**“beginner subscription… One—”**) triggered a **second add** and wrong qty at read-back  

Checkout (allergies → pickup → read-back) worked; **collecting** was still LLM-hybrid and fragile.

## Solution

| Area | Change |
|------|--------|
| **`restaurant/stt_noise.py`** | Standalone qty parsing (`van`, `one`, `ਇੱਕ`); TV/YouTube noise detection; “recently asked quantity” helper |
| **`order_parse.py`** | `auto_add_candidates()` — code-owned add for **single** high-confidence items with qty in speech, not only multi-item |
| **`order_flow.py`** | No `quantity_allowed` / “how many?” when qty already in utterance |
| **`phone_background.py`** | Never drop qty answers during collecting; filter obvious STT noise as background |
| **`agent.py`** | `_try_auto_add`, `_try_quantity_reply` (set qty, not add), `_try_reject_stt_noise`; block `add_to_order` during checkout |
| **`fillers.py`** | `ADD_ITEM` → processing filler (“let me check”) for menu lookup time |

## Flow (collecting)

```
Caller: "ਇੱਕ Amritsari Fish"
  → auto_add_candidates (qty=1, high confidence)
  → code adds + confirms + "anything else?"
  → NO quantity re-ask

Caller: "van" (after mistaken LLM quantity ask)
  → parse_standalone_quantity + agent_recently_asked_quantity
  → update_item_quantity (set, not add)

Noisy STT: "beginner subscription…"
  → is_likely_stt_noise → "sorry, say that again?"
  → NO add_to_order / auto-add
```

## Deploy

```bash
cd /opt/livekit-sarvam && git fetch origin && git checkout main && git reset --hard origin/main && uv sync && systemctl restart restaurant-agent
```

Ensure `FILLERS_ENABLED=1` on VPS for processing acks during menu lookup.

## Test plan

```bash
PYTHONPATH=. uv run pytest tests/test_stt_noise.py tests/test_phone_background.py tests/test_order_flow.py tests/test_conversation.py -q
```

- [ ] “ਇੱਕ + dish” → one add, no “how many?”  
- [ ] “van” / “one” after quantity question → qty set, not doubled  
- [ ] TV noise transcript → repeat request, cart unchanged  
- [ ] Add during readback → tool rejected  
- [ ] Normal multi-item order still works
