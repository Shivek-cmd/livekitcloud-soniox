# PR 039 — Contact capture + read-back loop fix

## Problem

End-of-call failure mode from live transcript:

1. Name `"ਨਾਮ ਮera ਸ਼ਿਵੇਕ ਹੈ"` not parsed → never saved to cart.
2. Phone `94137 52688` given while phase stuck at `special_instructions` → code capture only ran in `customer_phone` phase → **LLM repeat loop**.
3. Read-back repeated 3+ times at `confirming` because `readback_confirmed` never set after LLM off-script read-back.

## Fix

| Area | Change |
|------|--------|
| **Name parse** | Punjabi/Hindi patterns: `ਨਾਮ ਮera X`, `mera naam X`. |
| **Phase-agnostic capture** | After `items_complete`, save name/phone from any checkout phase — not only `customer_phone`. |
| **Phone before name** | If digits heard without name → code asks name once (no LLM repeat spiral). |
| **Off-script read-back** | `confirm_yes` / all good after LLM read-back → mark confirmed, ask name (no re-read). |
| **Read-back once** | `readback_spoken` flag + turn guidance: never repeat read-back after name/contact started. |

## Deploy

```bash
cd /opt/livekit-sarvam && git fetch origin && git checkout main && git reset --hard origin/main && uv sync && systemctl restart restaurant-agent
```

## Test plan

- [ ] Full order → allergies → read-back yes → `ਨਾਮ ਮera X ਹੈ` → name saved → phone → placed (no repeat loop)
- [ ] Phone given before name → Sierra asks name once, not "phir se bol sakte hain" x3
- [ ] After read-back confirmed, Sierra never repeats the order list
- [ ] Logs show `CAPTURE name=` and `CAPTURE phone=` even when analytics phase ≠ `customer_phone`
