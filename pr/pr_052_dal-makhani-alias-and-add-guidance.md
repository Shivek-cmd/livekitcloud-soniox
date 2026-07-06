# PR 052 — Duplicate Palak Paneer: alias fix + LLM guidance

## Branch
`pr_052_dal-makhani-alias-and-add-guidance`

## Problem (live call, 2026-07-06)

Final order showed **two** Palak Paneer, but the caller only ever asked for
one:

```
Turn 2  Caller: "...ਇੱਕ ਦਾਲਮਖਨੀ ਤੇ ਇੱਕ ਪਾਲਕ ਪਨੀਰ..." (one dal makhani, one palak paneer)
        AUTO_ADD items=['ਪਾਲਕ ਪਨੀਰ'] qty=[1]   ← only Palak Paneer auto-added;
                                                   "ਦਾਲਮਖਨੀ" abstained (4x)
Turn 3  Caller: "ਦਾਲਮਖਨੀ ਵੀ ਕਿਹਾ ਮੈਂ।" (I ALSO SAID dal makhani — a correction)
        Tool calls (from Supabase call_turns.tools_called, not in server logs):
          add_to_order(item_name='palak paneer', quantity=1)
            → "SAY EXACTLY: Sure — two ਪਾਲਕ ਪਨੀਰ now."
          add_to_order(item_name='dal makhani', quantity=1)
            → "SAY EXACTLY: Yes — one ਦਾਲ ਮੱਖਣੀ."
```

Two stacked causes, traced with hard evidence (Supabase `call_turns` table,
since per-turn tool-call args aren't in the server logs — only the analytics
recorder sees them):

1. **Root cause**: "ਦਾਲਮਖਨੀ" (caller's compressed, no-space spelling) abstained
   at the deterministic auto-add matcher because `content_tokens()` splits
   purely on whitespace — a single fused query token can never token-align
   against the canonical two-token label "ਦਾਲ ਮੱਖਣੀ". Confirmed directly
   against the real local menu cache. This pushed turn 3 to free-form LLM
   handling instead of the deterministic auto-add path turn 2 used.
2. **Contributing**: once in free-form territory, the LLM re-called
   `add_to_order` for Palak Paneer (already in the cart) *in addition to*
   correctly adding the missing Dal Makhani — `add_to_order` is additive by
   design (correctly reported "two now"), so this isn't a code bug, it's an
   LLM judgment call that didn't recognize "I also said X" as "add only X."

## Fix

Two independent, complementary changes — deterministic first, LLM guidance
second as defense-in-depth (per the project's own PR 030 lesson: guidance
alone isn't reliable, so #1 is the real fix and #2 is a safety net, not relied
on alone):

### 1. `data/clover_voice_labels.json` (deterministic — same pattern as the
   existing Shikanji→Nimbu Pani backlog item)
- Added `"ਦਾਲਮਖਨੀ"` to Dal Makhani's `aliases`. An alias is tokenized and
  matched as a single unit, so the fused spelling now gets an exact,
  confidence-1.0 hit instead of abstaining — keeping this turn on the
  deterministic `AUTO_ADD` path entirely, same as turn 2, so it never reaches
  free-form LLM tool-calling in the first place.
- **Requires a menu sync after merge** to reach the runtime cache
  (`data/menu_cache_bizbull.json`) — `bash scripts/vps_deploy.sh` already
  does this, or manually: `uv run python scripts/clover_sync_menu.py`.
- Deliberately did **not** touch the matching algorithm itself
  (`restaurant/clover/match.py`) — it's a carefully tuned, multi-PR-refined
  module (PR 032/033/034); adding alias data is far lower-risk than teaching
  the scorer to align a fused token against multiple label tokens.

### 2. `restaurant/conversation.py` + `restaurant/order_flow.py` (guidance —
   defense-in-depth for other items that might still abstain for unrelated
   reasons)
- New `mentions_already_said(text)` — detects "I said / already said / also
  said / ਕਿਹਾ / ਬੋਲਿਆ / ਬੋਲੀ / ਬੋਲੇ" (deliberately a separate, narrower check
  from the existing `_I_SAID_RE` used in hard intent classification, so
  broadening it here can't affect `detect_intent()`'s ADD_ITEM/pickup-STT
  paths elsewhere).
- `_collecting_guidance()`'s single-item `ADD_ITEM` branch now adds an
  explicit line when `mentions_already_said()` is true: call `add_to_order`
  **only** for the named item, do not re-add anything already in the cart.

## What's NOT in This PR

- Does not modify `restaurant/clover/match.py`'s scoring algorithm — see
  above.
- Does not add a general "de-duplicate identical add_to_order calls" guard at
  the code level — deliberately avoided: legitimate repeat orders ("add one
  more naan" in a later turn) must still work, and a blanket idempotency
  guard risks blocking those. The guidance approach is scoped to the specific
  "correction" phrasing pattern instead.
- Does not fix Sierra ignoring her own tool's `SAY EXACTLY` output (she said
  "one Palak Paneer" when the tool said to say "two") — a separate, smaller
  issue about instruction-following fidelity, not scoped here.

## How to Test

```bash
PYTHONPATH=. pytest tests/test_conversation.py tests/test_order_flow.py tests/test_menu_match.py -q
```

`tests/test_menu_match.py::test_compressed_spelling_needs_explicit_alias`
demonstrates both the abstain (before) and the fix (after) using an isolated
in-memory menu cache — doesn't depend on the real data file.

Live (after a menu sync): order two items in one sentence where one uses a
compressed/joined spelling, then correct a dropped item with "I also said X"
phrasing — confirm no duplicate line appears in the final read-back.

## Post-Merge: VPS Pull Command
```
cd /opt/livekit-sarvam && git pull origin main && uv sync
PYTHONPATH=/opt/livekit-sarvam uv run python scripts/clover_sync_menu.py
systemctl restart restaurant-agent
```
