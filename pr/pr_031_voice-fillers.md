# PR 031 — Voice fillers (intent-based, phone + web)

## Branch
`pr_031_voice-fillers`

## Status
⬜ **Open** — implemented on branch `pr_031_voice-fillers`; awaiting review.

## What This PR Does

Adds **short, human-like spoken fillers** before the LLM answers on selected turns — both **phone and web**.

Fillers bridge dead air while GPT/tools run. They use the same **sticky `preferred_language`** as existing `phrase_*` helpers (last clearly detected script: en / hi / pa / mixed). No extra API calls.

**Strategy:** intent-based (v1). A curated pool per language; Python picks one line. **Non-blocking** — filler TTS fires in a background task so the LLM path starts immediately (no added serial latency).

**Kill switch:** `FILLERS_ENABLED=0` (default off until VPS validation).

---

## Design decisions (locked)

| Decision | Choice |
|----------|--------|
| Channels | Phone **and** web (same rules) |
| Trigger | Intent-based — not latency-gated in v1 |
| Language | `OrderFlowState.preferred_language` (sticky last detected script) |
| Latency | Fire-and-forget `asyncio.create_task(session.say(...))` — **never await** before turn guidance / LLM |
| Single-item add (auto-add miss) | **ACK** filler (`"Got it."` / `"ਹਾਂ ਜੀ."`) — not processing |
| Menu / price / availability | **PROCESSING** filler (`"Let me check."` / `"menu check kardi haan."`) |
| LLM prompt changes | **None** — fillers are code-owned speech only |

---

## Filler types

| Kind | When | Max length |
|------|------|------------|
| **ACK** | Caller added or named an item; agent is about to confirm/add via LLM | ≤ 4 words |
| **PROCESSING** | Agent needs menu lookup, price, or availability | ≤ 5 words |

No **TRANSITION** fillers in v1 (e.g. "Alright so…") — too easy to double with LLM openers.

---

## Curated pools (`restaurant/fillers.py`)

### English (`CustomerLanguage.ENGLISH`)

| Kind | Pool (rotate; no immediate repeat) |
|------|-------------------------------------|
| ACK | `"Got it."`, `"Sure."`, `"Okay."` |
| PROCESSING | `"Let me check."`, `"One moment."`, `"Just a sec."` |

### Hindi (`CustomerLanguage.HINDI`)

| Kind | Pool |
|------|------|
| ACK | `"हाँ जी."`, `"ठीक है."`, `"जी."` |
| PROCESSING | `"एक minute."`, `"मैं देखती हूँ."`, `"ज़रा check करती हूँ."` |

### Punjabi (`CustomerLanguage.PUNJABI`)

| Kind | Pool |
|------|------|
| ACK | `"ਹਾਂ ਜੀ."`, `"ਠੀਕ ਹੈ ਜੀ."`, `"ਬਿਲਕੁਲ ਜੀ."` |
| PROCESSING | `"ਇੱਕ minute."`, `"ਮੈਂ ਵੇਖਦੀ ਹਾਂ."`, `"menu check kardi haan."` |

### Mixed (`CustomerLanguage.MIXED`)

Uses the **current sticky language** (`preferred_language` after `update_preferred_language`). When sticky is `MIXED`, fall back to short code-mix lines:

| Kind | Pool |
|------|------|
| ACK | `"ਹਾਂ ਜੀ — sure."`, `"Okay ji."`, `"ठीक ji."` |
| PROCESSING | `"Let me check ji."`, `"ਇੱਕ minute."`, `"One moment ji."` |

---

## When to speak a filler

### Intent → kind

| Intent | Filler kind | Notes |
|--------|-------------|-------|
| `ASK_PRICE` | PROCESSING | Before price tool/LLM |
| `ASK_AVAILABILITY` | PROCESSING | Before `check_menu_item` |
| `ADD_ITEM` | ACK | Only when auto-add **did not** run (LLM/tools path) |
| `GENERAL` | PROCESSING | Menu browse, recommendations, reservations chat |
| All others | **none** | See block list |

### Phase block list (no filler)

Fixed ladder / checkout — Sierra should speak the scripted line, not a filler:

| Phase | Reason |
|-------|--------|
| `special_instructions` | Allergies step |
| `order_type` | Pickup/delivery question |
| `delivery_address` | Address collection |
| `customer_name` | Name collection |
| `customer_phone` | Phone collection |
| `confirming` | Read-back / confirm |
| `placed` | Post-order |

Phases **`browsing`**, **`collecting_items`**, **`awaiting_more`** — fillers allowed when intent matches.

### Intent block list (no filler)

| Intent | Reason |
|--------|--------|
| `ORDER_DONE` | Leads to allergies / close — no filler |
| `CONFIRM_YES` / `CONFIRM_NO` | Ladder confirm steps |
| `PICKUP` / `DELIVERY` | Order type capture |
| `HUMAN` | Escalation — answer directly |
| `UNCLEAR` | Use existing `phrase_repeat_request` via guidance, not filler |

### Turn block list (no filler)

| Condition | Reason |
|-----------|--------|
| Echo or background filtered turn | Avoid echo loops (`phone_echo.py`) |
| Auto-add succeeded (`StopResponse`) | Already spoke confirm + anything else |
| `_hangup_started` | Post-order goodbye path |
| `FILLERS_ENABLED=0` | Kill switch |
| Agent already `speaking` or `thinking` | Skip — preemptive gen already active (best-effort check) |

---

## Injection point

```
on_user_turn_completed (agent.py)
  → phone echo / background filters → StopResponse (no filler)
  → pickup/delivery cart sync
  → _real_user_turns += 1
  → _try_auto_add_multi → if StopResponse, exit (no filler)
  → _maybe_speak_filler(intent)   ← NEW (async task, non-blocking)
  → _inject_turn_guidance → LLM
```

```python
async def _speak_filler(self, line: str) -> None:
    if not self._session:
        return
    try:
        await self._session.say(line, allow_interruptions=True)
        self.note_agent_speech(line)
    except Exception:
        logger.exception("Filler speech failed")

def _maybe_speak_filler(self, intent: UserIntent) -> None:
    line = pick_filler(
        intent=intent,
        phase=self._flow.state.phase,
        lang=self._flow.state.preferred_language,
        recent=self._recent_fillers,
    )
    if not line:
        return
    logger.info("FILLER intent=%s lang=%s text=%s", intent.value, ...)
    self._recent_fillers.append(line)
    asyncio.create_task(self._speak_filler(line))
```

**Latency contract:** `_maybe_speak_filler` returns in microseconds. LLM preemptive generation is not delayed.

---

## Echo / analytics safety

- Every spoken filler goes through **`note_agent_speech()`** after TTS (same as echo reprompt / auto-add).
- Log line: `FILLER intent=… phase=… lang=… text="…"`.
- Optional: `SessionRecorder` event `filler_spoken` (defer if scope creep — log-only in v1).

---

## Files Added

### `restaurant/fillers.py`
- `FillerKind` enum (`ACK`, `PROCESSING`)
- Language pools (constants)
- `fillers_enabled()` — reads `FILLERS_ENABLED`
- `pick_filler(intent, phase, lang, recent) -> str | None`
- `should_use_filler(...)` — intent + phase + enable gate
- Session anti-repeat: last 3 fillers (`deque`, max 3)

### `tests/test_fillers.py`
- Pool selection per language
- Blocked phases / intents return `None`
- Anti-repeat does not pick same line twice in a row
- `MIXED` sticky fallback
- `fillers_enabled()` env parsing

## Files Modified

### `agent.py`
- `_recent_fillers: deque[str]` on `RestaurantAgent`
- `_speak_filler`, `_maybe_speak_filler`
- Call `_maybe_speak_filler(intent)` after auto-add attempt, before `_inject_turn_guidance`

### `.env.example`
- `FILLERS_ENABLED=0` — set `1` on VPS after test call

## Files Deleted
None.

---

## What's NOT in This PR

- Latency-gated fillers (cancel if LLM responds in &lt;300ms) — PR 032+ if needed
- LLM prompt changes ("start with hmm…")
- Fillers on fixed ladder steps (allergies, pickup, read-back) — future code-owned ladder PRs
- Transition fillers ("Alright so…")
- Backchannel while user is still speaking
- `SessionRecorder` schema changes (log-only unless trivial)
- Phone-only thinking keyboard sound (`WEB_AMBIENT_THINKING`)

---

## How to Test

```bash
# Unit
PYTHONPATH=. uv run pytest tests/test_fillers.py -q

# Regression
PYTHONPATH=. uv run pytest tests/test_language.py tests/test_conversation.py -q
```

### Manual — phone (`FILLERS_ENABLED=1`)

1. "Do you have paneer tikka?" → hear processing filler → availability answer. Log: `FILLER intent=ask_availability`.
2. "One butter chicken" (single item, no auto-add) → ACK filler → add confirm. No filler on 2+ item auto-add turn.
3. Full order through allergies/pickup/name → **no** fillers on those phases.
4. Echo / background noise turn → **no** filler.

### Manual — web

Same scenarios on `https://voice.bizbull.ai`.

### Latency check

```bash
journalctl -u restaurant-agent -f | grep -E 'FILLER|LATENCY'
```

- `user_stop→speaking` median should **not** increase materially vs baseline (filler runs parallel to LLM).
- Filler must appear **before or with** first LLM speech, not after a long gap.

---

## Post-Merge: VPS Pull Command

```bash
cd /opt/livekit-sarvam && git fetch origin && git checkout main && git reset --hard origin/main && uv sync && systemctl restart restaurant-agent
```

Enable after one clean test call:

```bash
# In /opt/livekit-sarvam/.env
FILLERS_ENABLED=1
systemctl restart restaurant-agent
```

---

## Verification checklist

- [ ] `tests/test_fillers.py` passes
- [ ] No filler on auto-add multi-item path
- [ ] No filler on echo/background filtered turns
- [ ] No filler during `confirming` / `customer_name` / etc.
- [ ] Punjabi caller → Gurmukhi filler; Hindi → Devanagari; English → English
- [ ] `LATENCY` logs show LLM not blocked by filler await
- [ ] Phone: no new echo loops after 5+ turn call
- [ ] Web: filler audible, captions show filler line
