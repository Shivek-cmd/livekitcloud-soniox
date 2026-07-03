# PR 045 — Checkout & contact capture hardening

## Problem (live call)

After PR 044 collecting fixes, checkout still broke:

1. **Name + phone asked together** — LLM bypassed code ladder via `set_customer_info(name, phone)`.
2. **Allergies asked twice** — LLM improvised Punjabi read-back and re-asked allergies at read-back.
3. **ਚੈਕੋ** misclassified — short read-back confirm not treated as yes.
4. **ਨਹੀਂ ਜੀ, ਕੋਈ ਗੱਲ ਨਹੀਂ** tagged `confirm_no` — means "no problem / all good".
5. **Dhanyavaad ji** — Hindi loanword spoken with English TTS instead of Gurmukhi ਧੰਨਵਾਦ.
6. **Duplicate goodbye / place_order** — tool called after order already placed.

## Fix

### Code-owned checkout speech (agent.py)

- **`set_order_type(pickup)`** — speaks English read-back immediately; tells LLM not to repeat.
- **`set_customer_info`** — name first only; rejects combined name+phone; optional `phone` param empty until name saved; speaks phone ask/confirm via TTS.
- **Checkout ladder** — read-back ack (`ਚੈਕੋ`, `ਕੋਈ ਗੱਲ ਨਹੀਂ`); force read-back if LLM set pickup without speaking; allergies asked once only.
- **LLM mute during checkout** — `StopResponse` after guidance for all code-owned phases (except price/availability/status/human detours).

### Intent & phrases (conversation.py)

- `is_readback_ack()` — ਚੈਕੋ, check, theek.
- `is_readback_all_clear()` — ਕੋਈ ਗੱਲ ਨਹੀਂ, no problem.
- `resolve_intent(phase=readback)` maps both to `CONFIRM_YES`.
- `phrase_phone_saved` — Gurmukhi ਧੰਨਵਾਦ for Punjabi/Hindi callers (not "Dhanyavaad").
- `sanitize_assistant_speech` rewrites stray Dhanyavaad → ਧੰਨਵਾਦ.

### Guidance (order_flow.py)

- Phase-specific lines: do not re-ask allergies; name-only then phone-only; read-back wait.

## Test plan

- [ ] Full phone order: items → done → allergies once → pickup → English read-back → All good → **name only** → phone → place → single goodbye
- [ ] Say **ਚੈਕੋ** at read-back → advances to name question (not stuck)
- [ ] Say **ਨਹੀਂ ਜੀ, ਕੋਈ ਗੱਲ ਨਹੀਂ** at read-back → treated as confirm yes
- [ ] Phone saved line uses **ਧੰਨਵਾਦ** not "Dhanyavaad"
- [ ] `pytest tests/test_conversation.py tests/test_order_flow.py tests/test_customer_info.py -q`
