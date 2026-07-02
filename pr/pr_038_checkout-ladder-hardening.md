# PR 038 — Checkout ladder hardening

## Problem

Live web call showed five systemic issues:

1. **Unneeded filler** — "Just a sec." on casual chitchat ("how are you?").
2. **Partial multi-item ack** — period-separated Punjabi dishes not auto-added together; only last item acknowledged.
3. **Punjabi confirm improvisation** — LLM said "ਪੁਸ਼ਟੀ ਕਰ ਦਿੰਦੀ ਹਾਂ" instead of fixed English checkout lines.
4. **Name skipped** — phone asked before name because phase stuck at `awaiting_more`.
5. **Phone digits in Hindi/Punjabi TTS** — ASCII digits read in Indic voice as "nau chaar paanch".

## Fix (principled, not transcript-hardcoded)

| Area | Change |
|------|--------|
| **Fillers** | No fillers for chitchat GENERAL or GENERAL in `browsing`. |
| **Multi-item** | Split order utterances on `.` / `।` for multi-dish Punjabi sentences. |
| **Checkout ladder** | Code-owned fixed phrases: allergies → pickup/delivery → read-back → name → phone → place. |
| **Done ordering** | `is_done_ordering()` + `confirm_no` at `awaiting_more` → `ORDER_DONE`. |
| **Phone TTS** | `format_phone_spoken()` uses English words (`nine, four, one, …`) for TTS. |
| **Goodbye dup** | `_goodbye_spoken` guard — place_order speaks once, LLM told to stay silent. |

## Deploy

```bash
cd /opt/livekit-sarvam && git fetch origin && git checkout main && git reset --hard origin/main && uv sync && systemctl restart restaurant-agent
```

## Test plan

- [ ] Chitchat "how are you" → no "Just a sec."
- [ ] Two dishes in one Punjabi sentence with danda → both auto-added, one confirm listing both
- [ ] "ਨਹੀਂ ਨਹੀਂ, ਬਹੁਤ ਹੈ" → English allergies question (not Punjabi confirm)
- [ ] After read-back yes → name asked before phone
- [ ] Phone readback heard as English words, not Hindi digits
- [ ] Order placed → goodbye spoken once only
