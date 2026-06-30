# Sierra — Session Handoff (start here)

> **Primary doc for new conversations.** Read this first, then drill into linked files.
> Last updated: **2026-06-29** (`main` through **PR 025** @ `7232d48`).
> **VPS:** `89.117.18.192` — `/opt/livekit-sarvam/` — deploy **`main`** after merges: `bash scripts/vps_deploy.sh`.

---

## What this project is

**Sierra** — Punjabi-English voice agent for **Bizbull Restaurant** (Canadian market).

| Channel | Number / URL | Status |
|---------|--------------|--------|
| **Phone (primary)** | `+15878175156` via Twilio → LiveKit Cloud SIP | Production testing |
| **Web** | **`https://voice.bizbull.ai`** | W1–W2 live + ambient audio (web + phone) |

**Stack:** LiveKit Cloud + Soniox STT/TTS (`Maya`, `language=pa`) + GPT-4o-mini + Clover menu cache (61 items).

**Repo:** `git@github.com:Shivek-cmd/livekitcloud-soniox.git` (GitHub redirects from old `livekit-sarvam` name).

**Deploy:** Owner runs `bash scripts/vps_deploy.sh` on VPS — do **not** run two `npm` builds in parallel (OOM risk).

**Restaurant name:** **Bizbull Restaurant** (`ਬਿਜ਼ਬਲ ਰੈਸਟੋਰੈਂਟ`).

**Opening greeting (phone + web):**
> Hi! Sierra from Bizbull here. I speak English, Hindi, and Punjabi. How can I help?

Constant: `OPENING_GREETING` in `restaurant/conversation.py` (PR 025).

---

## Git / PR state (2026-06-29)

**`main` is current through PR 025.** No open PRs blocking deploy.

| PR | Topic | Merge |
|----|-------|-------|
| **016** | Order flow phrases + Bizbull branding | ✅ #39–40 |
| **017** | Echo filter + intent + read-back hardening | ✅ #41–42 |
| **018** | Customer language + trilingual greeting (old) | ✅ #43 |
| **019** | Mango drinks English TTS; chole/bhature Gurmukhi | ✅ #44 |
| **020** | Web background ambient | ✅ #45 |
| **021** | Custom ambience mp3 + web volume tuning | ✅ |
| **022** | Phone ambient (shared loop) | ✅ |
| **023** | BVC + phone background speech filter + endpointing 0.2–0.5s | ✅ #52–53 |
| **024** | Concise add confirms + multi-item parse + soft drink TTS | ✅ #54–55 |
| **025** | Pickup STT, all-good confirm, no price on phone, new greeting, ambient 0.2 | ✅ #56–57 |

PR workflow: **`pr/pr_rules.md`** — doc first, branch name = doc name, merge via GitHub.

Full index: **`pr/README.md`**.

---

## What's DONE (do not re-litigate)

### Infrastructure (Phases 1–5) ✅
- LiveKit **Cloud** — trunk Krisp NC
- Soniox + GPT stack
- Twilio SIP inbound + `scripts/test_call.py` outbound
- VPS deploy: `scripts/vps_deploy.sh`

### Voice / speech (PR 006–007, 013, 019, 024) ✅
- **`speech_policy.py`** + **`clover_voice_labels.json`** — 61 items
- PR 019: Mango Shake/Lassi English; Chole/Bhature Gurmukhi (`ਕੌਂਬੋ` spelling)
- PR 024: Soft drink → **`ਸਾਫਟ ਡਰਿੰਕ`**
- Rebuild: `scripts/rebuild_voice_labels.py` — `tests/test_speech_policy.py`

### Clover menu (Phase 8a–8b) ✅
- **`menu_cache_bizbull.json`** + `USE_CLOVER_MENU=1`
- **`place_order()`** logs only — **does NOT submit to Clover** (Phase 8c)

### Turn latency + phone hardening (PR 008, 013, 023) ✅
- **`restaurant/session_config.py`** — TurnDetector, **0.2–0.5s** endpointing (phone + web)
- Krisp **BVC** telephony (SIP) / BVC (web)
- Phone: `PHONE_INTERRUPTION_MIN_WORDS=2`, background transcript filter
- Revert flags: `PHONE_BVC_ENABLED=0`, `PHONE_BACKGROUND_FILTER_ENABLED=0`

### Conversation layer (PR 015–018, 024–025) ✅

| Module | Role |
|--------|------|
| **`restaurant/prompts.py`** | Phone + web system prompts; **phone: no price unless asked** |
| **`restaurant/conversation.py`** | Intents, `resolve_intent(phase)`, `is_confirm_yes`, templates, speech guards |
| **`restaurant/order_flow.py`** | Phase machine + per-turn `[TURN GUIDANCE]` |
| **`restaurant/order_parse.py`** | Multi-item parse (`one X and one Y`) + auto-add gate (PR 024) |
| **`restaurant/phone_echo.py`** | Phone echo filter |
| **`restaurant/phone_background.py`** | Background chatter drop (PR 023) |
| **`agent.py`** | Tools, auto-add fast-path, echo/background hooks, web_sync |
| **`tests/test_conversation.py`**, **`tests/test_order_parse.py`** | Unit tests |

**PR 024 — add flow:** cashier-style confirms (`Yes — one X and one Y`); `add_to_order` returns `SAY EXACTLY:`; auto-add 2+ items when no required modifiers.

**PR 025 — phone flow fixes:**
- Pickup STT: `ਇੱਕ ਕੱਪ` / `ਇੱਕ ਅੱਪ` → pickup at `order_type` phase (`is_likely_pickup_stt`)
- Read-back yes: `ਆਲ ਗੁੱਡ`, `ਹਾਂ ਜੀ, all good` → name step (no repeat loop)
- **No price/dollars/totals on phone** unless customer asks (`ASK_PRICE`); read-back has items + pickup only

### Ambient audio (PR 020–022, 024–025) ✅
- **`restaurant/ambient_audio.py`** — web **and** phone loop (`restaurant_ambience.mp3` or builtin)
- **Default volume: 0.2** web + phone (code default; override via env)
- Web disconnect may log benign shutdown warnings (`could not find publication to remove`) — ignore on tab close

### Web — Order with Sierra (PR 009–013) ✅
- **`voice.bizbull.ai`** — W1 shell + W2 live hybrid cart (`web_sync.py`)

---

## Phone order flow (current, on `main`)

```
Greet → browse/add items → "Anything else?" → allergies (English)
  → pickup/delivery → read-back + "All good?" (NO price on phone)
  → name → phone → place_order() [log only until 8c]
```

Phase enum: `restaurant/order_flow.py` → `OrderPhase`.

Fixed spoken lines (`restaurant/conversation.py`):

| Line | Constant |
|------|----------|
| Greeting | `OPENING_GREETING` |
| Allergies | `ALLERGIES_QUESTION` |
| Pickup/delivery | `PICKUP_DELIVERY_QUESTION` |
| Quantity | `QUANTITY_QUESTION` |
| Confirm close | `CONFIRM_CLOSE` (`"All good?"`) |

---

## Known issues / backlog

| ID | Issue | Next |
|----|--------|------|
| **B-2** | Menu search misses `sweet` / `mithai` / desserts category | TBD PR |
| **B-11** | LLM says item "not on menu" without calling `check_menu_item` | Availability guidance |
| **B-5** | LLM sometimes read-backs in Punjabi quantities on phone | Monitor after 025 |
| **B-8** | Long TTS lists get interrupted | Hard cap |
| **Speech audit** | ~20 more `voice_line` items (naan, biryani, combos…) | TBD |
| **3-item Punjabi lists** | Comma + `te` lists (3 combos) not parsed as 3 items | Future if needed |
| **Web shutdown noise** | Ambient track cleanup warnings on tab close | Benign; optional cleanup PR |

See **`docs/plan/10-voice-quality-tier-b.md`**.

---

## What's NOT done — roadmap

### Web — Order with Sierra (`docs/plan/11-web-order-with-sierra.md`)

| Phase | Scope | Status |
|-------|--------|--------|
| W1–W2 | Shell + live cart | ✅ |
| **W3** | Menu highlight, modifier picker, tap-add ack | ⬜ **Next web** |
| W4–W5 | Avatar, hardening | ⬜ |
| W6 | Web prompt variant | ✅ |

### Phase 8c–8f (Clover POS)

| Phase | Scope | Status |
|-------|--------|--------|
| **8c** | Submit orders to Clover checkout API | ⬜ **Next product milestone** |
| 8d–8f | Webhooks, pilot, multi-tenant | ⬜ |

---

## Key files

| File | Role |
|------|------|
| `agent.py` | Entrypoint, tools, auto-add, echo/background, web_sync, ambient |
| `restaurant/ambient_audio.py` | Background loop web + phone (volume 0.2 default) |
| `restaurant/conversation.py` | Intents, `resolve_intent`, templates, greeting, read-back |
| `restaurant/order_parse.py` | Multi-item utterance parser (PR 024) |
| `restaurant/order_flow.py` | Phase machine, `[TURN GUIDANCE]` |
| `restaurant/prompts.py` | System prompts (phone no-price rule) |
| `restaurant/session_config.py` | Turn handling, BVC, endpointing |
| `restaurant/phone_echo.py` | Echo filter |
| `restaurant/phone_background.py` | Background speech filter |
| `restaurant/clover/speech_policy.py` | English vs Gurmukhi TTS policy |
| `data/clover_voice_labels.json` | Per-item `voice_line` |
| `docs/vps-config.md` | VPS env reference |

---

## Ops cheat sheet

```bash
# SSH
ssh root@89.117.18.192

# Deploy (after main updated)
bash /opt/livekit-sarvam/scripts/vps_deploy.sh

# Outbound test (more echo than inbound CA number)
cd /opt/livekit-sarvam
uv run python scripts/test_call.py +919413752688

# Live conversation logs
journalctl -u restaurant-agent -f | grep -E 'USER:|SIERRA:|TURN_GUIDANCE|AUTO_ADD|ambient|Ignoring|Session started|ORDER_PLACED|LATENCY'

# Health
systemctl is-active restaurant-agent restaurant-token caddy
curl -s https://voice.bizbull.ai/health
```

### Env vars (`/opt/livekit-sarvam/.env`) — important defaults

| Variable | Code default | Purpose |
|----------|--------------|---------|
| `USE_CLOVER_MENU` | 1 | Required on VPS |
| `PHONE_ENDPOINTING_MAX` | 0.5 | Turn end delay (phone + web) |
| `PHONE_ENDPOINTING_MIN` | 0.2 | Min turn end delay |
| `WEB_AMBIENT_VOLUME` | **0.2** | Web ambient loudness |
| `PHONE_AMBIENT_VOLUME` | **0.2** | Phone ambient loudness |
| `PHONE_BVC_ENABLED` | 1 | Krisp BVC on inbound audio |
| `PHONE_BACKGROUND_FILTER_ENABLED` | 1 | Drop background transcripts |
| `PHONE_INTERRUPTION_MIN_WORDS` | 2 | Barge-in threshold (phone) |

Full list: **`docs/vps-config.md`**.

Restart after `.env` change: `systemctl restart restaurant-agent`.

---

## Test numbers

| Item | Value |
|------|-------|
| Twilio (inbound) | `+15878175156` |
| Dev mobile (outbound) | `+919413752688` — India PSTN, more echo |
| Web | `https://voice.bizbull.ai` |
| LiveKit Cloud | `bizbull-restaurant-cyeyyw0l.livekit.cloud` |

---

## Recommended next session priorities

1. **Deploy `main`** if VPS behind — confirm PR 024–025 live (greeting, no price, pickup STT)
2. **Live phone retest** — combo order → pickup → `ਆਲ ਗੁੱਡ` → name; no dollars in speech
3. **B-11** — force menu tool on availability turns
4. **Tier B-2** — menu search aliases (`sweet`, `mithai`, `dessert`)
5. **Web W3** — menu highlight, modifier picker
6. **Phase 8c** — Clover order submit from `place_order()`

---

## Doc map

| Doc | When to read |
|-----|--------------|
| **This file** | Every new conversation |
| `pr/README.md` | Full PR index |
| `pr/pr_024_natural-concise-multi-item.md` | Multi-item + concise confirms (merged) |
| `pr/pr_025_pickup-confirm-no-price-readback.md` | Pickup STT, all-good, no price, greeting (merged) |
| `pr/pr_023_phone-background-speech.md` | BVC + background filter (merged) |
| `docs/vps-config.md` | VPS, Caddy, SIP, env vars |
| `docs/plan/10-voice-quality-tier-b.md` | Voice bug backlog |
| `docs/plan/11-web-order-with-sierra.md` | Web W3–W6 |
| `docs/plan/09-clover-pos.md` | Clover 8c+ |
| `pr/pr_rules.md` | How to open PRs |
