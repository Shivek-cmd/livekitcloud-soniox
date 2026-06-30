# PR 029 — Auto hang-up after order placed

## Status
✅ **Merged to `main`** — PR #62 · **`main` @ `f4837c3`**

## Branch
`pr_029_auto-hangup-after-order`

## What This PR Does

After a **successful** `place_order()`, Sierra speaks the fixed goodbye line, waits for TTS to finish, then **ends the call automatically** on both **phone** (SIP/Twilio) and **web** (LiveKit room).

Today the session stays open until the caller hangs up (phone) or the user clicks disconnect (web). This PR adds deterministic call cutting via LiveKit `session.shutdown()` + `job_ctx.delete_room()` — not LLM keyword detection and not `EndCallTool` alone.

**Locked v1 behavior:**
- Hang up **only** after successful `place_order()`
- Same behavior on phone + web
- Goodbye spoken inside `place_order()` via `session.say(..., allow_interruptions=False)` — no double goodbye from the LLM
- Analytics flush unchanged (existing `session_close` / shutdown hooks must still run)

## Problem

| Channel | Today |
|---------|--------|
| Phone | SIP line stays live until caller hangs up |
| Web | Room stays up until user clicks disconnect |

`place_order()` logs `ORDER_PLACED` and returns tool text; nothing calls `shutdown()` or `delete_room()`.

## Design

### Call end flow

```
place_order() succeeds
  → cart.mark_placed()
  → session.say(goodbye, allow_interruptions=False)
  → StopResponse (no extra LLM speech)
  → schedule_hangup() waits for speech handle + grace delay
  → job_ctx.delete_room()   # disconnects SIP + web participants
  → session.shutdown()
  → analytics flush (existing hooks)
```

### Why not EndCallTool-only?

LiveKit's prebuilt `EndCallTool` is fine for optional "customer said bye" flows, but the LLM may forget to call it after orders. v1 uses **code-driven** hang-up on the order path.

### Helper module

### `restaurant/call_control.py` (new)
- `hangup_after_order_enabled()` — reads env
- `async def schedule_call_hangup(session, *, reason: str)` — wait for speech, then `delete_room` + `session.shutdown()`
- Structured log: `CALL_END reason=order_placed channel=phone|web`

## Files Added

### `restaurant/call_control.py`
Hang-up scheduler; isolates LiveKit job context usage from `agent.py`.

### `tests/test_call_control.py`
Unit tests for env flags and hang-up scheduling (mock session / job context).

## Files Modified

### `agent.py`
- `place_order()`: speak goodbye via `session.say`, schedule hang-up, silent LLM turn
- `bind_job_context()` for `delete_room`
- Analytics flush on `session_close` + shutdown (idempotent)

### `restaurant/conversation.py`
- `order_placed_goodbye()` — shared Punjabi closing line

### `restaurant/prompts.py`
- Silent turn after `ORDER COMPLETE` tool result

### `restaurant/call_control.py` (new)
- `schedule_call_hangup()` / `end_call_after_goodbye()` — env-gated room delete + session shutdown

### `tests/test_call_control.py` (new)
- Env flags + hang-up scheduling unit tests

### `.env.example`
Document new env vars (see below).

### `docs/HANDOFF.md`
Note auto hang-up after order + kill switch.

## Files Deleted
None.

## What's NOT in This PR

- Auto hang-up after `book_reservation()` (defer; optional env stub only)
- Auto hang-up on `transfer_to_human()` — call must stay open
- `EndCallTool` for casual "bye" without an order
- Twilio REST hang-up API (room delete is sufficient for SIP)
- Web UI toast / custom disconnect UX (room delete ends session; optional polish later)
- Keyword-based hang-up ("thank you", "bye")

## Environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `AUTO_HANGUP_AFTER_ORDER` | `1` | Master switch — set `0` to revert to old behavior |
| `AUTO_HANGUP_GRACE_SEC` | `1.0` | Buffer after goodbye TTS before room delete |

**Quick revert on VPS:** `AUTO_HANGUP_AFTER_ORDER=0` → `systemctl restart restaurant-agent`

## Edge cases

| Case | Behavior |
|------|----------|
| `place_order()` fails (cart not ready) | No hang-up |
| Transfer to human | No hang-up |
| Customer hangs up first | Normal disconnect (unchanged) |
| Goodbye interrupted | v1: `allow_interruptions=False` — order is final |
| Analytics | Must persist call on auto hang-up (verify in test plan) |

## How to Test

```bash
uv run pytest tests/test_call_control.py -q
```

### Phone
1. Inbound call `+15878175156`
2. Complete order through confirm + name + phone
3. Hear Punjabi goodbye → line should drop within ~2–3 s (no manual hang-up)

```bash
journalctl -u restaurant-agent -f | grep -E 'ORDER_PLACED|CALL_END|Flushing session analytics'
```

### Web
1. `voice.bizbull.ai` → place order
2. Hear goodbye → session ends → UI returns to Start Call

### Regression
- [ ] Transfer request — call stays open
- [ ] Incomplete cart — `place_order` rejected, call stays open
- [ ] Admin dashboard — call appears after auto hang-up
- [ ] `AUTO_HANGUP_AFTER_ORDER=0` — old behavior (manual disconnect)

## Post-Merge: VPS Pull Command

```bash
cd /opt/livekit-sarvam
git pull origin main
uv sync
systemctl restart restaurant-agent
```
