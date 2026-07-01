# PR 032 — Code-owned order ladder (concise, no repeat read-back)

## Branch
`pr_032_order-ladder-concise`

## Status
⬜ **Open** — implemented on branch `pr_032_order-ladder-concise`; awaiting review.

## What This PR Does

Fixes the **checkout ladder** so Sierra sounds like a human cashier: **short, no repeated order lines, no phone price unless asked**.

Uses the same proven pattern as **auto-add** (`session.say` + `StopResponse`) — **code speaks fixed ladder steps**, LLM only handles browsing/adding/menu Q&A.

**Not** another prompt/guard PR (PR 030 lesson). One ladder step owned in code per commit if needed; ship as one PR with tests.

---

## Live call analysis (what went wrong)

**Caller order:** Sweet Lassi + Nimbu Pani → bas → no allergies → pickup → yes → name → phone → done.

| Turn | What happened | Should happen |
|------|---------------|---------------|
| 2 | LLM add + confirm (OK) + possible filler | Same — one confirm line |
| 3 | Allergies question | ✅ Correct |
| 4–5 | **Allergies asked again** | **Once only** → advance to pickup |
| 5–6 | "I said no" → confused / repeat request | Treat as **no allergies** → pickup question |
| 6 | **Full read-back + "Shall I place?"** (too early) | **Not yet** — pickup first |
| 7 | Yes → **then** pickup question | Pickup should be turn 4 |
| 8 | Read-back **again** + **$10.48 on phone** | **One read-back, no price**, after pickup |
| 9–11 | Name / phone (OK-ish) | Shorter — no re-confirm fluff |
| 12 | Generic "order is all set" — **no Punjabi goodbye / hangup?** | `place_order()` → fixed goodbye → hang-up (PR 029) |

**Order line repeated ~4×:** turn 2 confirm, turn 6 confirm+place, turn 8 read-back.

**Target call length:** ~7–8 turns (not 12).

---

## Root causes (code, not model randomness)

### 1. Allergies loop
- Turn 4 `"No, ਬਸ..."` → `ORDER_DONE` ( `_DONE_RE` matches `ਬਸ`) **before** allergy advance runs.
- `ORDER_DONE` guidance **re-injects** `ALLERGIES_QUESTION` even when `allergies_asked=True`.
- `_advance_from_user_turn` only advances allergies when `is_allergies_step_answer()` — **`ORDER_DONE` is not treated as an allergy answer**.

### 2. "I said no" → wrong intent
- `"I said no"` matches `_I_SAID_RE` → **`ADD_ITEM`** (turn 5–6).
- Phase stuck at `special_instructions`; LLM improvises read-back / place prompt.

### 3. Ladder order LLM-driven
- Intended: allergies → **pickup** → read-back → name → phone → place.
- Actual: allergies loop → early read-back → pickup → read-back again.
- `[TURN GUIDANCE]` says the right order; **LLM skips/combines steps** (PR 030 lesson).

### 4. Phone price spoken
- Prompt + guidance forbid price on phone (PR 025).
- LLM still said `"total about 10.48 dollars"`.
- `sanitize_assistant_speech()` strips price for **logging only** — **does not change TTS output** (`agent.py` conversation_item_added handler).

### 5. Read-back repetition
- LLM re-reads cart at confirming + after tools + after pickup.
- No code flag **"read-back already spoken this session"**.

### 6. Weak close
- Turn 12 suggests **`place_order()` may not have run** (no PR 029 Punjabi line / hang-up).

---

## Correct behavior (spec)

```
… add items → "Anything else?"
Caller: bas / no more
  → CODE: "Any allergies or special instructions?"     [once]

Caller: no / nahin / bas
  → CODE: "Will that be pickup or delivery?"           [once]

Caller: pickup / delivery (+ address if delivery)
  → CODE: read-back (items + type, NO price on phone) + "All good?"   [once]

Caller: yes / all good
  → CODE: name question (localized)

Caller: name
  → CODE: phone question

Caller: phone
  → tool: set_customer_info + place_order()
  → CODE: Punjabi goodbye → hang-up (PR 029)
```

LLM handles: menu search, add (when not auto-add), price **only if asked**, reservations.

---

## Fix strategy

### A. Intent fixes (same PR, small — unblocks ladder)

**`resolve_intent()` phase-aware:**

| Phase | User says | Intent |
|-------|-----------|--------|
| `special_instructions` | no / bas / nahin / "no no" | `CONFIRM_NO` (not `ORDER_DONE`, not `ADD_ITEM`) |
| `special_instructions` | "I said no" | `CONFIRM_NO` |
| `confirming` | yes (after read-back) | `CONFIRM_YES` |
| `awaiting_more` | bas / that's it | `ORDER_DONE` |

**`is_allergies_step_answer()`:** treat bare `"yes"` at `special_instructions` as "no allergies" only when context fits — prefer explicit no; add `"no, no, no"` / repeated no pattern (salvage from PR 030).

**`_advance_from_user_turn`:** when `phase=special_instructions` and `allergies_asked` and `(CONFIRM_NO or ORDER_DONE with bas/no)`, call `mark_special_instructions_done()`.

### B. Code-owned ladder steps (`agent.py`)

New helper: `_try_ladder_step(turn_ctx, user_text, intent) -> bool` — returns True if handled (raises `StopResponse`).

| Trigger | Code speaks | Phase advance |
|---------|-------------|---------------|
| `ORDER_DONE` + cart not empty + not yet asked | `ALLERGIES_QUESTION` | `items_complete`, `allergies_asked=True` |
| Allergy answer (no/none) | `PICKUP_DELIVERY_QUESTION` | `special_instructions_done` |
| `PICKUP`/`DELIVERY` + type set in cart | `format_order_readback(include_price=False)` on phone | stay until read-back yes |
| Read-back yes | `phrase_name_for_order(lang)` | `readback_confirmed=True` |
| Name captured (tool or detect) | phone prompt | — |
| Phone captured | `place_order()` path | placed |

Each step: `session.say(line)`, `note_agent_speech`, system message `[LADDER] Already spoken: "..."`, **`raise StopResponse()`**.

### C. Phone price — enforce, don't hope

1. **Code-owned read-back** uses `include_price=False` on phone (already in `format_order_readback`).
2. **TTS guard:** when `is_phone`, run `sanitize_assistant_speech` on LLM output **before** it reaches TTS if LiveKit hook exists; else strip price regex and re-speak via wrapper on `conversation_item_added` — investigate `Agent` speech pipeline in `agent.py` entrypoint.
3. Minimum: if LLM output contains `_PRICE_SPEECH_RE` on phone, **replace line** with read-back template without price (log `PRICE_STRIPPED`).

### D. Read-back once flag

`OrderFlowState.readback_spoken: bool = False` — set when code speaks read-back; guidance + code skip second read-back.

### E. Punjabi two-item auto-add (optional same PR or 033)

Turn 2 used LLM tools, not auto-add — `"ਤੇ"` (and) may not parse in `order_parse.py`. Fix parser so 2-item Punjabi hits `_try_auto_add_multi` → one confirm, faster.

---

## Files Added

### `tests/test_ladder.py`
- Intent: `"No, bas"` at `special_instructions` → `CONFIRM_NO`
- Intent: `"I said no"` at `special_instructions` → `CONFIRM_NO`
- Allergy no → phase advances to `order_type`
- Phone read-back string has no `dollars`
- Read-back spoken once (flag)

## Files Modified

### `restaurant/conversation.py`
- `resolve_intent()` phase rules for ladder phases
- `"no, no, no"` allergy pattern
- Optional: export price-strip helper for TTS path

### `restaurant/order_flow.py`
- `readback_spoken` flag
- Stop re-issuing `ALLERGIES_QUESTION` when `allergies_asked` + user said no/bas
- Remove duplicate read-back guidance when flag set

### `agent.py`
- `_try_ladder_step()` after auto-add, before filler/LLM
- Wire allergy → pickup → read-back → name as code-owned steps (incremental)

### `agent.py` (entrypoint)
- Apply phone price strip to assistant speech before TTS if hook available

## Files Deleted
None.

---

## What's NOT in This PR

- New filler types (PR 031 done)
- Clover submit (8c)
- Strict auto-add / fuzzy menu (separate PR)
- Web price behavior change (web may still show price on screen)

---

## How to Test

```bash
PYTHONPATH=. uv run pytest tests/test_ladder.py tests/test_conversation.py -q
```

### Live script (phone)

1. Order 2 items Punjabi → one confirm, no repeat.
2. `"ਨਹੀਂ ਜੀ ਬਸ"` → allergies **once** → `"No"` → pickup question (not allergies again).
3. `"Pickup"` → read-back **without dollars** → `"All good?"` **once**.
4. Yes → name → phone → Punjabi goodbye → call ends.

```bash
journalctl -u restaurant-agent -f | grep -E 'LADDER|PRICE_STRIPPED|place_order|ORDER_PLACED|FILLER'
```

---

## Post-Merge: VPS

```bash
cd /opt/livekit-sarvam && git fetch origin && git checkout main && git reset --hard origin/main && uv sync && systemctl restart restaurant-agent
```

---

## Verification checklist

- [ ] Allergies never asked twice on "no / bas"
- [ ] "I said no" does not trigger add_item at special_instructions
- [ ] Pickup before read-back
- [ ] Read-back spoken once; no dollar amount on phone
- [ ] `place_order` + goodbye + hang-up on completed order
- [ ] Call completes in ≤8 turns for simple 2-item pickup order
