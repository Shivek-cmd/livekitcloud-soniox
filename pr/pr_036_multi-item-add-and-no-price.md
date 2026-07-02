# PR 036 — Multi-item add confirm + no unsolicited price (web)

## Branch
`pr_036_multi-item-add-and-no-price`

## Status
✅ **Ready for review** — implementation complete on branch `pr_036_multi-item-add-and-no-price`.

## The bug (live web transcript, 2026-07-02)

Turn 2 (2 dishes in one Punjabi sentence):
> ਹਾਂ ਜੀ, ਆਪਣੇ ਇੱਕ ਵੈਜ ਸਪ੍ਰਿੰਗ ਰੋਲ ਕਰ ਦਿਓ, ਤੇ ਆਪਣੇ ਇੱਕ ਸਰਸੋਂ ਦਾ ਸਾਗ ਕਰ ਦਿਓ।

Turn 3 (1 dish):
> ਤੇ ਆਪਣੇ 2 ਬਟਰ ਨਾਨ ਕਰ ਦਿਓ।

Sierra spoke only **"Yes — two butter naan"** — caller thought only the last dish
counted. Cart actually had all three, but **speech never confirmed the turn-2 pair**.

When caller asked what they ordered, Sierra also volunteered **"ਕੁੱਲ ਤੱਕਰੀਬਨ ਤੀਹ ਡਾਲਰ"**
despite the standing rule: **no price unless customer asks**.

## Root causes (verified locally)

1. **`parse_order_lines` finds 2 items but `can_auto_add_lines()` returns False** — Sarson da
   Saag fuzzy confidence **0.7273 < 0.8** (Spring Rolls 0.838 passes). Auto-add fast-path
   skipped → LLM path → often only confirms the latest `add_to_order` call.
2. **Segment noise** — trailing **ਕਰ ਦਿਓ**, leading **ਆਪਣੇ** / **ਹਾਂ ਜੀ** hurts matching.
3. **Web channel allows voluntary price** in prompt + `get_order_summary(include_price=True)`
   + `sanitize` only strips price on phone.

## What This PR Does

### 1. Cleaner Punjabi order segments (`order_parse.py`)

Strip courtesy prefix (**ਹਾਂ ਜੀ**, **ਆਪਣੇ**, leading **ਤੇ**) and order verb suffix
(**ਕਰ ਦਿਓ**) before menu match.

### 2. Multi-item auto-add threshold

When **2+ lines** parsed, use `AUTO_ADD_MULTI_MIN_CONFIDENCE` (default **0.72**) so one
near-match (sarson 0.727) doesn't block the whole code-owned multi confirm.

### 3. No unsolicited price in speech (phone **and** web)

- Web prompt aligned with phone: prices visible on screen but **not spoken** unless asked.
- `get_order_summary` spoken read-back always `include_price=False`.
- `sanitize_assistant_speech` strips dollar/ਡਾਲਰ totals on **both** channels.
- Turn guidance price rule applies to web too.

### 4. Sarson STT alias

Add **ਸਰਸੋਂ ਦਾ ਸਾਗ** to voice labels (STT often omits **ਰ੍** in **ਸਰ੍ਹੋਂ**).

## Behaviour changes

| Scenario | Before | After |
|---|---|---|
| Turn 2 two-dish Punjabi utterance | LLM path, no multi confirm | Code auto-add + "Yes — one X and one Y" |
| "What did I order?" on web | Items + ~$30 spoken | Items only, no dollars |
| Phone | Already no volunteer price | Unchanged |

## Files Modified

`restaurant/order_parse.py`, `agent.py`, `restaurant/prompts.py`,
`restaurant/order_flow.py`, `restaurant/conversation.py`,
`data/clover_voice_labels.json`, `tests/test_order_parse.py`, `tests/test_conversation.py`.

## How to Test

```bash
PYTHONPATH=. USE_CLOVER_MENU=1 uv run pytest tests/test_order_parse.py tests/test_conversation.py -q
```

Manual (web): order spring roll + sarson in one Punjabi sentence → Sierra confirms **both**
before "Anything else?". Ask "what did I order?" → no dollar amount.

## Post-Merge: VPS Pull Command

```bash
cd /opt/livekit-sarvam && git fetch origin && git checkout main && git reset --hard origin/main && uv sync && systemctl restart restaurant-agent
```

## Verification checklist

- [x] Turn-2 utterance → auto-add fires; both items in confirm speech
- [x] Web "what did I order?" → no price (sanitize + get_order_summary)
- [x] Phone price rule unchanged
- [x] Full suite green (minus pre-existing failures)
- [ ] Live web call: multi-item Punjabi confirm + no dollar unless asked
