# Tier B — Voice quality & conversation backlog

> **Status:** Not started (Tier A latency ✅ done 2026-06-27).
> **Context:** Live test call logs from 2026-06-27 (`AJ_iN5nL8JwDa8D`, `dd8c5e2` deploy).
> **Start here after Tier A:** `docs/HANDOFF.md`

Tier A fixed **latency + echo stability + numbered lists**. Tier B fixes **conversation correctness** and **production demo quality** before Phase 8c Clover submit.

---

## P0 — Breaks real calls

### B1. False echo filter drops real user speech
**File:** `restaurant/phone_echo.py`  
**Symptom:** User asks price for dish Sierra just named → log `Ignoring phone echo turn` → **14s dead air** → user says "hello" → re-greeting / garbled recovery.  
**Cause:** Token overlap between user question and `_recent_agent_lines` (not acoustic echo).  
**Fix direction:** Require higher overlap threshold for longer utterances; ignore echo filter when user message contains price keywords (`price`, `rate`, `kina`, `ਕੀਮਤ`, `ਪ੍ਰਾਈਜ਼`); or only apply echo filter within N seconds of greeting.

### B2. Menu search misses common queries
**File:** `restaurant/clover/menu.py`, `menu_provider.py`  
**Symptom:** "ਮਿੱਠੇ ਚ ਕੀ ਹੈ?" → Sierra says no sweets found; menu has Desserts category (Gajar Halwa, Gulab Jamun, Kheer, …).  
**Cause:** Search tokenizes `mithhe` / `sweet` / category names poorly; GPT may pass wrong query.  
**Fix direction:** Query alias map (`mithai`→desserts, `drink`→Drinks category, `starter`→Starters); `search_by_category()` tool; pass Gurmukhi aliases in search haystack.

### B3. Overlapping / mashed replies
**Symptom:** User asks price; Sierra answers combo availability + quantity + spice for sweets in one cut-off sentence, then price separately.  
**Cause:** Prompt-only flow; no turn intent routing.  
**Fix direction:** Lightweight intent tags or state machine (ASK_PRICE vs ASK_AVAILABILITY vs ADD_ITEM); one question per turn enforced in code.

---

## P1 — Demo quality

### B4. Quantity before confirmation
**Symptom:** After "yes we have gajar halwa" → immediate "ਕਿੰਨਾ ਚਾਹੀਦਾ?" before customer said they want it.  
**Fix:** Step A prompt + code gate: only ask quantity after explicit "add it" / "haan add karo" / item chosen from list.

### B5. Wrong script / language slips
**Examples from logs:**
- Urdu `ਸوری` instead of Punjabi `ਮਾਫ ਕਰਨਾ`
- Romanized `ਕੋੰਬੋ` instead of English `Chole Bhature Combo` or Gurmukhi `voice_line`
- Spice question for desserts ("ਮਿੱਠੇ ਚ ਕਿਸ ਤਿੱਖੇ")

**Fix:** TTS post-processor substituting `voice_line`; prompt tightening; validate modifier groups before spice ask.

### B6. Mid-call re-greeting
**Symptom:** After missed turn, Sierra says `ਸਤ ਸ੍ਰੀ ਅਕਾਲ!` again.  
**Fix:** Prompt + guard in agent: never greet after turn 1; recovery phrase instead ("Sorry ji, go ahead").

### B7. Price reply fluff
**Symptom:** *"ਕੀਮਤ ਦੱਸਣ ਨਾਲ ਹਮੇਸ਼ਾ ਖੁਸ਼ੀ ਹੁੰਦੀ ਹੈ…"* instead of prompt rule: one English line *"That's about seven dollars ji."*  
**Fix:** Template from `check_menu_item` price when `ASK_PRICE` intent detected.

### B8. Long replies interrupted mid-TTS
**Symptom:** ~8s starter list → user barges in → cut-off sentence in logs.  
**Fix:** Hard 1–2 sentence cap in code; shorter search results (already capped at 2).

---

## P2 — Performance

### B9. Cold LLM latency (~1.5–3s TTFT)
**Cause:** ~3800–5000 token system prompt; first turn no cache.  
**Fix:** Shorten prompt; move order flow to code; split static menu rules from per-turn context.

### B10. Tool double-hop on every menu question
**Cause:** GPT → tool → GPT on most dish turns (~7s total).  
**Fix:** Session menu context after first search; fast-path for exact `find_item` hits.

---

## P3 — Nice to have

- Soniox STT context with menu aliases (noted in PR 005 as future)
- Migrate from deprecated `metrics_collected` to `ChatMessage.metrics`
- `RoomInputOptions` → `RoomOptions` (livekit-agents deprecation warning)
- Canadian test number for latency benchmarks (India +91 adds PSTN hop)

---

## Verification checklist (after Tier B)

- [ ] Ask price for dish Sierra just offered → answered in **<3s**, never ignored as echo
- [ ] "mithhe / sweet / dessert" → names 2 items naturally
- [ ] No quantity question until customer picks an item
- [ ] No mid-call Sat Sri Akal
- [ ] Price: single short English dollars line
- [ ] No numbered lists, no quotes around dish names
