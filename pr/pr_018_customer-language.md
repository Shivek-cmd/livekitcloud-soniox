# PR 018 — Customer language + trilingual greeting

## Branch
`pr_018_customer-language`

## Status
⬜ **Open** — stacked on PR 017 (includes 016–017).

## What This PR Does

Production language handling for phone **and** web:

1. **New greeting (both channels)** — `OPENING_GREETING` in `conversation.py`, played from `agent.py`:
   > Hello! I'm Sierra from Bizbull Restaurant. I can help you in English, Hindi, or Punjabi — how may I help you today?

2. **Script-based language detection** — `detect_customer_language()` + `preferred_language` on order flow state (en / hi / pa / mixed).

3. **Per-turn `[TURN GUIDANCE]`** — `language_turn_guidance()` tells LLM conversational language; **fixed order steps stay English**.

4. **Web prompt fix (W6)** — English UI does not force English replies; match phone behavior.

5. **Localized conversational phrases** (not fixed fillers):
   - `phrase_anything_else()`, `phrase_name_for_order()`, `phrase_repeat_request()`

6. **Echo filter** — updated greeting tail phrases for new hello.

**Latency:** no extra API calls — Python script detect + one guidance line per turn.

## Files Modified

- `restaurant/conversation.py` — greeting, language detect, phrases
- `restaurant/order_flow.py` — `preferred_language`, inject language guidance
- `restaurant/prompts.py` — web language rule, greeting note
- `agent.py` — `OPENING_GREETING`, log `lang=` in TURN_GUIDANCE
- `restaurant/phone_echo.py` — new greeting echo fragments
- `tests/test_language.py`

## Still English-only (by design)

- `ALLERGIES_QUESTION`, `PICKUP_DELIVERY_QUESTION`, `QUANTITY_QUESTION`, read-back + `All good?`
- Phone digit read-back

## Post-Merge: VPS

```bash
bash /opt/livekit-sarvam/scripts/vps_deploy.sh
```

## Verification

- [ ] Phone + web: new trilingual hello
- [ ] User speaks Punjabi → `lang=pa` in logs + Gurmukhi conversational replies
- [ ] User speaks Hindi → `lang=hi` + Devanagari replies
- [ ] Web: speak Punjabi with English menu visible → not all-English replies
- [ ] Allergies / read-back steps still exact English templates

## Depends on

PR **016–017** — merge stack or merge 018 to `main` after 017.
