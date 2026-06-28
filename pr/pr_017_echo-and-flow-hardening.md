# PR 017 — Echo filter + order flow hardening

## Branch
`pr_017_echo-and-flow-hardening`

## Status
⬜ **Open** — not merged to `main` as of 2026-06-29. Latest commit on branch: includes PR 016 + 017.

## What This PR Does

Fixes live phone failures from test sessions **2026-06-28**:

| Session | Symptoms |
|---------|----------|
| `AJ_au2zatxEoKfG` | Echo dropped pickup + full order; garbled pickup question; pickup asked twice |
| `AJ_rQKPc8CZWSTL` / `AJ_WdBBeaBJx2zN` | Echo reprompt loop; `ਹਾਂ ਜੀ` repeat read-back; Punjabi read-back not English template |

### `restaurant/phone_echo.py` (B-1)
- Bypass echo filter for meaningful intents (pickup, delivery, add_item, price, confirm_yes, etc.).
- Stricter token-overlap; 2+ unique user words vs agent line → real speech.
- Recovery-phrase echo (`go ahead`, `ਮੈਂ ਸੁਣ ਰਹੀ`) + truncated agent-line prefix → drop silently.
- Exact agent repeat still filtered.

### `restaurant/conversation.py`
- `is_confirm_yes()` — `ਹਾਂ ਜੀ`, `haan ji`, `All good`, lone `ਜੀ`.
- Quantity+dish orders → `add_item`; allergies denial patterns.
- `is_want_to_order_only()` → fixed pickup/delivery line.

### `restaurant/order_flow.py`
- `readback_confirmed` gate — name/phone only after `"All good?"` yes.
- Confirm yes → ask name, **never** repeat read-back.
- English-only read-back guidance at confirming step.

### `agent.py`
- Pass intent into echo filter; auto-set `cart.order_type` on pickup/delivery.
- **One** post-greeting echo reprompt only — no recovery reprompt spiral.
- `set_order_type` tool text: read-back before name/phone.

### Tests
- `tests/test_phone_echo.py` — live log regressions
- `tests/test_conversation.py` — extended (24 tests total on branch)

## Files Modified

- `restaurant/phone_echo.py`
- `restaurant/conversation.py`
- `restaurant/order_flow.py`
- `agent.py`
- `tests/test_phone_echo.py`
- `tests/test_conversation.py`
- Plus all PR 016 files (stacked branch)

## Depends on

PR **016** (phrases + branding) — same branch stack.

## Post-Merge: VPS

```bash
bash /opt/livekit-sarvam/scripts/vps_deploy.sh
journalctl -u restaurant-agent -f | grep -E 'USER:|SIERRA:|TURN_GUIDANCE|Ignoring|Session started'
```

## Verification checklist

- [ ] "Yeah, I'm looking for pickup" → **not** `Ignoring phone echo turn`
- [ ] Full dish order after Sierra lists paneer → processed, not "go ahead ji"
- [ ] "I want to order" → "Will that be pickup or delivery?"
- [ ] Allergies → `"Any allergies or special instructions?"`
- [ ] "not not at all" after allergies → advances flow
- [ ] Read-back uses English one/two + "All good?" (monitor — LLM may still slip to Punjabi)
- [ ] **"ਹਾਂ ਜੀ"** after read-back → asks name **once**, does **not** repeat order
- [ ] Greeting echo → at most one "go ahead" reprompt, **no** 30s loop
- [ ] Name/phone only after read-back confirmed

## Still open after this PR

- **B-2** menu search (`sweet`, `mithai`)
- LLM Punjabi read-back drift (B-5)
- Phase **8c** Clover submit

See `docs/HANDOFF.md` and `docs/plan/10-voice-quality-tier-b.md`.
