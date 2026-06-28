# Tier B — Voice quality & conversation backlog

> **Status:** PR 015–020 ✅ merged on `main`; PR 016–018 ⬜ open (phone/language); PR 021 ⬜ open (ambient volume).
> **Context:** Live test logs 2026-06-27–28 (`AJ_iN5nL8JwDa8D`, `AJ_au2zatxEoKfG`, `AJ_WdBBeaBJx2zN`, `AJ_rQKPc8CZWSTL`).
> **Start here:** `docs/HANDOFF.md`

Tier A fixed **latency + echo stability + numbered lists**. Tier B fixes **conversation correctness** before Phase 8c Clover submit.

---

## Shipped on `main` (do not rebuild)

| Item | PR | Module |
|------|-----|--------|
| Shortened prompt + W6 web variant | 015 | `prompts.py` |
| Intent + templates (price, availability, add) | 015 | `conversation.py` |
| Order phase machine + turn guidance | 015 | `order_flow.py` |
| Mid-call re-greeting guard | 015 | `conversation.py`, `agent.py` |
| Mango Shake/Lassi English TTS (not Amb) | 019 | `speech_policy.py`, `clover_voice_labels.json` |
| Chole/Bhatura/Chole Bhature Gurmukhi TTS | 019 | `speech_policy.py`, `clover_voice_labels.json` |
| Web ambient audio (web only) | 020 | `ambient_audio.py`, `agent.py` |

## In open PRs 016–017 (merge before treating as done)

| Item | PR | Module |
|------|-----|--------|
| Fixed allergies / pickup / quantity phrases | 016 | `conversation.py`, `order_flow.py` |
| English read-back template + `All good?` | 016 | `conversation.py`, `orders.py` |
| Bizbull branding (not Punjab Da Dhaba) | 016 | `menu.py`, web, deploy |
| Echo false positives (real pickup/orders) | 017 | `phone_echo.py` |
| Echo reprompt loop fix | 017 | `agent.py`, `phone_echo.py` |
| `ਹਾਂ ਜੀ` confirm at read-back | 017 | `conversation.py`, `order_flow.py` |
| Read-back before name/phone | 017 | `order_flow.py` |
| Qty+dish add intent (`one paneer…`) | 017 | `conversation.py` |

## In open PR 018 (customer language)

| Item | PR | Module |
|------|-----|--------|
| Trilingual opening greeting (phone + web) | 018 | `conversation.py`, `prompts.py` |
| `preferred_language` from script detect → turn guidance | 018 | `order_flow.py`, `agent.py` |
| Web UI English ≠ reply language; localized prompts | 018 | `prompts.py`, `conversation.py` |

---

## P0 — Still open

### B2. Menu search misses common queries
**File:** `restaurant/clover/menu.py`, `menu_provider.py`  
**Symptom:** "ਮਿੱਠੇ ਚ ਕੀ ਹੈ?" → no sweets; menu has Desserts (Gajar Halwa, Gulab Jamun, …).  
**Fix direction:** Alias map (`mithai`→desserts, `drink`→Drinks); category search tool.

### B11. False "not on menu" on availability questions
**Symptom:** Caller asks for paneer tikka / papad — items exist in Clover cache — Sierra says not available without calling `check_menu_item`.  
**Root cause:** `_availability_guidance()` does not resolve item or force tool call (unlike `_price_guidance()`).  
**Fix direction:** `order_flow.py` — resolve item from user text; inject "call check_menu_item" or yes/no template.

### Speech policy audit (deferred)
**Context:** Session 2026-06-29 audited ~61 items; PR 019 fixed 5 only (mango drinks + chole/bhature). ~20 more flagged (naan, biryani, combos, etc.) — see PR 019 "What's NOT in This PR".  
**Fix direction:** Next PR after owner review of English vs Gurmukhi list.

---

## P1 — Partially done / monitor after 017 deploy

### B3. Overlapping / mashed replies
**Status:** Mitigated by intent + phase guidance (015–017). LLM can still slip on edge turns.

### B4. Quantity before confirmation
**Status:** ✅ Quantity gate in `order_flow.py` (015). Verify on live calls.

### B5. Wrong script / language slips
**Examples:** Urdu `ਸوری`; Punjabi read-back (`ਇੱਕ`, rupees) instead of English template.  
**Fix direction:** Stronger confirming-step enforcement; TTS post-processor.

### B6. Mid-call re-greeting
**Status:** ✅ Guard in `sanitize_assistant_speech` (015).

### B7. Price reply fluff
**Status:** ✅ `format_price_reply()` template (015).

### B8. Long replies interrupted mid-TTS
**Fix:** Hard 1–2 sentence cap; search already capped at 2 items.

---

## P2 — Performance

### B9. Cold LLM latency (~1.5–3s TTFT)
**Status:** Improved by shorter prompt (015). Further trim possible.

### B10. Tool double-hop on every menu question
**Fix:** Session menu context; fast-path exact `find_item` hits.

---

## P3 — Nice to have

- Soniox STT context with menu aliases
- `metrics_collected` → `ChatMessage.metrics` migration
- `RoomInputOptions` → `RoomOptions` deprecation
- Canadian test number for benchmarks (India +91 adds PSTN hop + echo)

---

## Verification checklist (after PR 016–017 deploy)

- [ ] "Yeah, I'm looking for pickup" → not ignored as echo
- [ ] Full dish order after Sierra lists items → processed
- [ ] "I want to order" → "Will that be pickup or delivery?"
- [ ] Allergies → exact English question
- [ ] "ਹਾਂ ਜੀ" after read-back → name once, **no** repeat order
- [ ] Greeting echo → at most one reprompt, no loop
- [ ] "mithhe / sweet / dessert" → names 2 items (B2 — still failing until fixed)
- [ ] "Do you have paneer tikka?" → calls menu tool, correct yes/no (B11 — still failing until fixed)
- [ ] "Mango shake" → TTS says **Mango Shake**, not "Amb Shake" (019)
- [ ] Web call → faint ambient loop audible (020; louder after 021 or `WEB_AMBIENT_VOLUME=0.6`)
- [ ] Price: single short English dollars line
- [ ] No mid-call Sat Sri Akal

