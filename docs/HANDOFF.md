# Sierra — Session Handoff (start here)

> **Primary doc for new AI sessions.** Read this first, then linked files.
> **Last updated:** 2026-06-30 · **`main` @ `f4837c3`** (PR 029 merge).
> **VPS:** `89.117.18.192` — `/opt/livekit-sarvam/` — deploy: `bash scripts/vps_deploy.sh`

---

## What this project is

**Sierra** — Punjabi-English voice agent for **Bizbull Restaurant** (Canadian market).

| Channel | Number / URL | Status |
|---------|--------------|--------|
| **Phone (primary)** | `+15878175156` via Twilio → LiveKit Cloud SIP | Live testing |
| **Web** | `https://voice.bizbull.ai` | W1–W2 live + ambient |
| **Admin** | `https://admin.bizbull.ai` | Call analytics (PR 027) |

**Stack:** LiveKit Cloud + Soniox STT/TTS (`Maya`, `language=pa`) + GPT-4o-mini + Clover menu cache (~61 items).

**Repo:** `https://github.com/Shivek-cmd/livekitcloud-soniox.git` (GitHub redirects from old `livekit-sarvam` remote name).

**Restaurant name:** **Bizbull Restaurant** (`ਬਿਜ਼ਬਲ ਰੈਸਟੋਰੈਂਟ`).

**Opening greeting (phone + web, PR 028):**
> Hi! I'm Sierra, your virtual assistant. I speak English, Hindi, and Punjabi. How can I help you?

Constant: `OPENING_GREETING` in `restaurant/conversation.py`.

---

## Git / PR state (2026-06-30)

### `main` is at `f4837c3`

| PR | Topic | Status |
|----|-------|--------|
| **027** | Admin analytics — Supabase + `SessionRecorder` + admin.bizbull.ai | ✅ #60 |
| **028** | Virtual assistant greeting (no Bizbull in intro) | ✅ #61 |
| **029** | Auto hang-up after successful `place_order()` | ✅ #62 |
| **030** | Order flow quality (strict auto-add, final confirm, phase guards) | ❌ **Merged then reverted** — see below |

**PR workflow:** `pr/pr_rules.md` — doc first → branch = doc name → merge via GitHub.

**Full index:** `pr/README.md`.

### PR 030 — what happened (important for new sessions)

PR 030 was merged (#63), then two follow-up commits landed on `main`, then **`main` was reset to `f4837c3`** (2026-06-30) because live calls got **worse**, not better:

- More phase rules + tool guards did not stop the LLM from **skipping steps in speech** (pickup → name → read-back combined).
- Phase stuck at `awaiting_more` in analytics while Sierra kept asking “All good?” / “Shall I place?” in loops.
- **Lesson:** guidance-only fixes are not enough; next approach should use **code-owned speech** at ladder steps (like existing multi-item auto-add), not more prompt rules.

**Do not re-apply PR 030 blindly.** Read `pr/pr_030_order-flow-quality.md` for full scope and revert rationale.

Branch `pr_030_order-flow-quality` may still exist on remote for reference — **do not deploy it**; **`main` is source of truth**.

---

## What's DONE (do not re-litigate)

### Infrastructure ✅
- LiveKit Cloud + Krisp NC on trunk
- Soniox + GPT-4o-mini
- Twilio SIP inbound; `scripts/test_call.py` outbound
- VPS: `scripts/vps_deploy.sh`, `scripts/setup_sip.py`

### Voice / speech (PR 006–007, 013, 019, 024) ✅
- `speech_policy.py` + `data/clover_voice_labels.json`
- Mango drinks English TTS; chole/bhature Gurmukhi; soft drink → `ਸਾਫਟ ਡਰਿੰਕ`
- Rebuild: `scripts/rebuild_voice_labels.py` — `tests/test_speech_policy.py`

### Clover menu (Phase 8a–8b) ✅
- `data/menu_cache_bizbull.json` + `USE_CLOVER_MENU=1` on VPS
- **`place_order()` logs only** — does **NOT** submit to Clover (Phase 8c)

### Turn latency + phone hardening (PR 008, 013, 023) ✅
- `restaurant/session_config.py` — TurnDetector, 0.2–0.5s endpointing
- Krisp BVC telephony (SIP) / BVC (web)
- Phone: `PHONE_INTERRUPTION_MIN_WORDS=2`, background transcript filter

### Conversation layer (PR 015–018, 024–025) ✅

| Module | Role |
|--------|------|
| `restaurant/prompts.py` | Phone + web system prompts; phone: no price unless asked |
| `restaurant/conversation.py` | Intents, `resolve_intent(phase)`, templates, speech guards |
| `restaurant/order_flow.py` | Phase machine + per-turn `[TURN GUIDANCE]` |
| `restaurant/order_parse.py` | Multi-item parse + auto-add gate (2+ items, fuzzy match) |
| `restaurant/call_control.py` | Auto hang-up after order (PR 029) |
| `agent.py` | Tools, auto-add fast-path, analytics, web_sync |

**PR 024:** Cashier confirms (`Yes — one X and one Y`); auto-add 2+ clear items when no required modifiers.

**PR 025:** Pickup STT (`ਇੱਕ ਕੱਪ` → pickup); read-back yes → name; **no price on phone** unless asked.

**PR 029:** Punjabi goodbye via `place_order()` → `delete_room` + `session.shutdown()`. Kill switch: `AUTO_HANGUP_AFTER_ORDER=0`.

### Admin analytics (PR 027) ✅
- Supabase schema: `supabase/migrations/001_initial_analytics.sql`
- `SessionRecorder` in agent; flush on **session close + shutdown**
- Admin React app at **admin.bizbull.ai**
- Env: `SUPABASE_URL`, `SUPABASE_SERVICE_KEY` (see `.env.example`)

### Ambient audio (PR 020–022, 025) ✅
- `restaurant/ambient_audio.py` — web + phone loop, default volume **0.2**

### Web (PR 009–013) ✅
- `voice.bizbull.ai` — W1 shell + W2 live hybrid cart (`web_sync.py`)

---

## Phone order flow (current on `main`)

**Intended ladder** (LLM-guided — not fully code-enforced):

```
Greet → browse/add items → "Anything else?" → allergies (English)
  → pickup/delivery → read-back + "All good?" (NO price on phone)
  → name → phone → place_order() [log only until 8c]
  → Punjabi goodbye → call ends (PR 029)
```

Phase enum: `restaurant/order_flow.py` → `OrderPhase`.

Fixed spoken lines (`restaurant/conversation.py`):

| Step | Constant |
|------|----------|
| Greeting | `OPENING_GREETING` |
| Allergies | `ALLERGIES_QUESTION` |
| Pickup/delivery | `PICKUP_DELIVERY_QUESTION` |
| Quantity | `QUANTITY_QUESTION` |
| Confirm close | `CONFIRM_CLOSE` (`"All good?"`) |

---

## Known live issues (from 2026-06-30 testing)

These are **real on current `main`** — do not assume fixed:

| ID | Issue | Notes |
|----|--------|-------|
| **Fuzzy auto-add** | `find_item()` token match can map wrong items (`"one"` → random dish; STT typos → wrong item) | PR 030 tried strict match — reverted with rest of PR |
| **LLM skips ladder** | After add, may ask pickup/name before allergies or combine "All good?" + "Shall I place?" | Needs **code-owned steps**, not more prompts |
| **Turn 2 Punjabi multi-item** | Single utterance with `te` may not auto-add if strict parse fails; phase stays `browsing` | `order_parse.py` |
| **B-2** | Menu search misses `sweet` / `mithai` | Alias/data PR |
| **B-11** | LLM says "not on menu" without `check_menu_item` | Availability guidance |
| **B-5** | Punjabi quantities on phone read-back | Monitor |
| **Shikanji** | STT → Nimbu Pani needs alias in `clover_voice_labels.json` | Data fix, small PR |

See `docs/plan/10-voice-quality-tier-b.md` for full Tier B backlog.

---

## What's NOT done — roadmap

| Area | Scope | Status |
|------|--------|--------|
| **Order flow hardening** | Code-owned speech at allergies / pickup / read-back / final confirm | ⬜ **Next voice priority** — small PRs, one step each |
| **Web W3** | Menu highlight, modifier picker, tap-add ack | ⬜ |
| **Phase 8c** | Submit orders to Clover checkout API | ⬜ **Next product milestone** |
| **8d–8f** | Webhooks, pilot, multi-tenant | ⬜ |

Web plan: `docs/plan/11-web-order-with-sierra.md`  
Clover plan: `docs/plan/09-clover-pos.md`  
Admin plan: `docs/plan/12-admin-analytics-supabase.md`

---

## Key files

| File | Role |
|------|------|
| `agent.py` | Entrypoint, tools, auto-add, analytics flush, hang-up |
| `restaurant/conversation.py` | Intents, templates, greeting, read-back |
| `restaurant/order_flow.py` | Phase machine, `[TURN GUIDANCE]` |
| `restaurant/order_parse.py` | Multi-item parser + auto-add gate |
| `restaurant/call_control.py` | Post-order hang-up |
| `restaurant/session_recorder.py` | Analytics capture |
| `restaurant/clover/menu.py` | Menu cache + fuzzy `find_item()` |
| `data/clover_voice_labels.json` | Per-item `voice_line` + aliases |
| `data/menu_cache_bizbull.json` | Clover cache (VPS, not always in git) |

---

## Ops cheat sheet

```bash
# SSH
ssh root@89.117.18.192

# Deploy (always from main)
cd /opt/livekit-sarvam
git fetch origin
git checkout main
git reset --hard origin/main
systemctl restart restaurant-agent
git log -1 --oneline
# Or full deploy (sync menu, rebuild web/admin):
bash scripts/vps_deploy.sh

# Outbound test call
uv run python scripts/test_call.py +1YOURNUMBER

# Logs
journalctl -u restaurant-agent -f | grep -E 'USER:|SIERRA:|TURN_GUIDANCE|AUTO_ADD|ORDER_PLACED|Session'

# Health
systemctl is-active restaurant-agent restaurant-token caddy
curl -s https://voice.bizbull.ai/health
```

### Important env vars (VPS `.env`)

| Variable | Default | Purpose |
|----------|---------|---------|
| `USE_CLOVER_MENU` | 1 | Required on VPS |
| `AUTO_HANGUP_AFTER_ORDER` | 1 | Hang up after order |
| `PHONE_AMBIENT_VOLUME` / `WEB_AMBIENT_VOLUME` | 0.2 | Ambient loudness |
| `SUPABASE_URL` / `SUPABASE_SERVICE_KEY` | — | Analytics (PR 027) |

Full list: `docs/vps-config.md`.

---

## Test numbers

| Item | Value |
|------|-------|
| Twilio inbound | `+15878175156` |
| Dev mobile (outbound script default) | `+919413752688` |
| Web | `https://voice.bizbull.ai` |
| Admin | `https://admin.bizbull.ai` |
| LiveKit Cloud | `bizbull-restaurant-cyeyyw0l.livekit.cloud` |

---

## Recommended next session priorities

1. **Confirm VPS on `f4837c3`** — `git log -1` on server
2. **One ladder step in code** — e.g. code-owned allergies question after `ORDER_DONE` (speak + advance phase without LLM improvisation)
3. **Small data PR** — shikanji / common STT aliases → Nimbu Pani
4. **Strict auto-add only** — separate tiny PR if desired (do not bundle with phase machine changes)
5. **Phase 8c** — Clover submit when ordering path stable

---

## Doc map

| Doc | When to read |
|-----|--------------|
| **This file** | Every new conversation |
| `pr/README.md` | Full PR index + current session |
| `pr/pr_030_order-flow-quality.md` | Reverted PR — lessons learned |
| `pr/pr_rules.md` | How to open PRs |
| `docs/vps-config.md` | VPS, Caddy, SIP, env |
| `docs/plan/10-voice-quality-tier-b.md` | Voice bug backlog |
| `docs/plan/11-web-order-with-sierra.md` | Web W3+ |
| `docs/plan/12-admin-analytics-supabase.md` | Admin / Supabase |
