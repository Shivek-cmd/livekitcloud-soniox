# PR 030 — Order flow quality (REVERTED)

## Status

| Field | Value |
|-------|--------|
| **Branch** | `pr_030_order-flow-quality` (reference only) |
| **Merged** | #63 (2026-06-30) |
| **On `main` now** | ❌ **No** — `main` reset to `f4837c3` (pre-PR-030) |
| **Why reverted** | Live calls worse: phase loops, LLM skipped ladder despite new rules |

---

## What this PR tried to do

1. **Strict auto-add** — `find_item_strict()`, block qty-word fuzzy matches
2. **Final confirm gate** — "Shall I place this order?" before `place_order()`
3. **Cart truth** — prompt rules + `get_order_summary()` for read-backs
4. **Alias overlay** — merge `clover_voice_labels.json` aliases at cache load (shikanji → Nimbu Pani)
5. **Phase guards** — block `set_order_type` / `set_customer_info` when too early
6. **Allergy loop fix** — detect "No, no" and stop repeating allergies question

---

## Why it was reverted

Live test transcript (2026-06-30) showed:

- Phase stuck at `awaiting_more` while Sierra asked name/phone and mixed "All good?" + "Shall I place?"
- User said yes repeatedly — `place_order()` never ran
- Tool guards blocked tools but **LLM still spoke wrong steps** from chat context
- Adding more `[TURN GUIDANCE]` lines increased complexity without fixing root cause

**Root lesson:** Order ladder must be **code-enforced at key steps** (like existing `_try_auto_add_multi` + `StopResponse`), not LLM + prompt soup.

---

## Commits that were on `main` briefly (not current)

```
6f0f0a6 Fix order flow stuck at awaiting_more when pickup/name given early
82a4ecf Fix allergies loop when caller says No no repeatedly
4796c15 Merge pull request #63 (PR 030)
b0ecbe1 Fix order flow quality: strict auto-add, final confirm gate, alias overlay
```

Branch tip may match `f9bd225` on remote — **do not deploy**.

---

## What to salvage in future small PRs

| Piece | Safe alone? | Notes |
|-------|-------------|-------|
| Shikanji aliases in `clover_voice_labels.json` | ✅ | Data-only PR |
| `find_item_strict()` for auto-add only | ✅ | No phase machine changes |
| "No, no" allergy detection | ✅ | One function in `conversation.py` |
| Final confirm gate | ⚠️ | Only with code-owned final confirm speech |
| Full phase guards + FINAL_CONFIRM enum | ❌ | Reverted — needs redesign |

---

## Recommended replacement approach (PR 031+)

Implement **one ladder step at a time** in `agent.py`:

1. After last item (`ORDER_DONE` or explicit "bas") → code speaks `ALLERGIES_QUESTION`, `StopResponse`
2. After allergy answer → code speaks `PICKUP_DELIVERY_QUESTION`
3. After `set_order_type` → code speaks read-back from cart
4. After read-back yes → code asks name, then phone
5. After phone → code speaks final confirm line → `place_order()`

Each step: minimal LLM freedom, test with `tests/test_conversation.py` + live call.

---

## How to Test (if re-attempting on a branch)

```bash
PYTHONPATH=. uv run pytest tests/test_conversation.py tests/test_order_parse.py -q
```

Live: full order → no loop → single goodbye → hang-up.

---

## Post-merge VPS (only if re-merged to main)

```bash
cd /opt/livekit-sarvam && git fetch origin && git checkout main && git reset --hard origin/main && systemctl restart restaurant-agent
```
