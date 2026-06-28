# Sierra — Session Handoff (start here)

> **Primary doc for new conversations.** Read this first, then drill into linked files.
> Last updated: **2026-06-29** (PR 015 merged; PR 016–017 open on GitHub).
> **VPS:** `89.117.18.192` — `/opt/livekit-sarvam/` — deploy **`main`** after PRs merge.

---

## What this project is

**Sierra** — Punjabi-English voice agent for **Bizbull Restaurant** (Canadian market).

| Channel | Number / URL | Status |
|---------|--------------|--------|
| **Phone (primary)** | `+15878175156` via Twilio → LiveKit Cloud SIP | Production testing |
| **Web** | **`https://voice.bizbull.ai`** | W1–W2 live (Order with Sierra tab) |

**Stack:** LiveKit Cloud + Soniox STT/TTS (`Maya`, `language=pa`) + GPT-4o-mini + Clover menu cache (61 items).

**Repo:** `git@github.com:Shivek-cmd/livekitcloud-soniox.git` (GitHub redirects from old `livekit-sarvam` name).

**Deploy:** Owner runs `bash scripts/vps_deploy.sh` on VPS — do **not** run two `npm` builds in parallel (OOM risk).

**Restaurant name:** **Bizbull Restaurant** everywhere (Gurmukhi: `ਬਿਜ਼ਬਲ ਰੈਸਟੋਰੈਂਟ`). Old "Punjab Da Dhaba" branding removed in PR 016.

---

## Git / PR state (2026-06-29)

| Branch | PR doc | Status | Notes |
|--------|--------|--------|-------|
| `main` | — | ✅ through **PR 015** | Last merge: `e341262` conversation layer |
| `pr_016_order-flow-phrases` | `pr/pr_016_order-flow-phrases.md` | ⬜ **Open** | Phrases, phase fixes, Bizbull rename |
| `pr_017_echo-and-flow-hardening` | `pr/pr_017_echo-and-flow-hardening.md` | ⬜ **Open** | Echo + intent + read-back |
| `pr_018_customer-language` | `pr/pr_018_customer-language.md` | ⬜ **Open** | Greeting + language state + web parity |

**To ship:** merge **016 → 017 → 018** → `bash scripts/vps_deploy.sh`.

PR workflow: **`pr/pr_rules.md`** — doc first, branch name = doc name, merge via GitHub.

---

## What's DONE (do not re-litigate)

### Infrastructure (Phases 1–5) ✅
- LiveKit **Cloud** (not self-hosted) — trunk Krisp NC
- Soniox + GPT stack — US-reachable
- Twilio SIP inbound + `scripts/test_call.py` outbound
- VPS deploy: `scripts/vps_deploy.sh` (pull main + menu sync + npm web build + restart)

### Voice / speech (PR 006–007, 013) ✅
- **`speech_policy.py`** — Gurmukhi `voice_line` default; English overrides for Fish Pakora, Chole Bhature Combo, tandoor items, **Mango Kulfi**, etc.
- **`clover_voice_labels.json`** — 61 items with `voice_line`, `speech_mode`, aliases
- Prompt bans `1x/2x/3x`; word quantities

### Clover menu (Phase 8a–8b) ✅
- **`menu_cache_bizbull.json`** (61 items) + `USE_CLOVER_MENU=1`
- Tools: `check_menu_item`, `search_menu_items`
- **`place_order()`** logs only — **does NOT submit to Clover** (Phase 8c)

### Tier A — Phone latency (PR 008) ✅
`restaurant/session_config.py` + `turn_latency.py` — TurnDetector, **0.2–0.8s** endpointing, preemptive TTS.

### Web — Order with Sierra (PR 009–013) ✅
- **`voice.bizbull.ai`** — W1 shell + W2 live hybrid cart (`web_sync.py`)
- Web shares phone turn tuning (PR 013)

### Tier B — Conversation layer (PR 015, on `main`) ✅
Refactored from monolithic `agent.py` prompt into code-driven flow:

| Module | Role |
|--------|------|
| **`restaurant/prompts.py`** | Short phone + **W6 web** system prompts |
| **`restaurant/conversation.py`** | Intent detection, fixed templates, speech guards |
| **`restaurant/order_flow.py`** | Phase state machine + per-turn `[TURN GUIDANCE]` |
| **`agent.py`** | Wires modules, phone echo hook, tools, web_sync |
| **`tests/test_conversation.py`** | Intent + flow unit tests |

### PR 018 — Customer language + greeting (stacked on 017)
- **Greeting:** `OPENING_GREETING` — trilingual hello (phone + web)
- **`preferred_language`** — script detect (pa/hi/en) → injected every `[TURN GUIDANCE]`
- **Web:** UI English ≠ reply language; localized "anything else?" / name ask
- **Fixed order steps** still English only (allergies, read-back, etc.)
Log grep: `USER:|SIERRA:|TURN_GUIDANCE|Ignoring|Session started|ORDER_PLACED|LATENCY` (TURN_GUIDANCE includes `lang=pa|hi|en`).

---

## Open PRs — phone fixes (NOT on `main` until merged)

### PR 016 — Order flow phrases
- Exact **allergies** line: `"Any allergies or special instructions?"`
- **Read-back** template: English one/two, `"All good?"`, via `format_order_readback()`
- Pickup/delivery intent fix; quantity template `"How many — one or two?"`
- **Bizbull Restaurant** branding (`menu.py`, web title, systemd)

### PR 017 — Echo + flow hardening (stacked on 016)
Live-call regressions from sessions `AJ_au2zatxEoKfG`, `AJ_WdBBeaBJx2zN`, `AJ_rQKPc8CZWSTL`:

| Fix | File |
|-----|------|
| Real speech not dropped as echo (pickup, orders) | `phone_echo.py` |
| Echo **reprompt loop** broken (one greeting reprompt max) | `agent.py`, `phone_echo.py` |
| **`ਹਾਂ ਜੀ`** → `confirm_yes` at read-back (no repeat loop) | `conversation.py`, `order_flow.py` |
| `one paneer tikka…` → `add_item` intent | `conversation.py` |
| Read-back **before** name/phone (`readback_confirmed` gate) | `order_flow.py` |
| Auto-save pickup/delivery on intent | `agent.py` |

**Tests:** `tests/test_phone_echo.py` + extended `test_conversation.py` (24 tests on PR 017 branch).

---

## Known issues still open (after 016–017 merge)

| ID | Issue | Next PR |
|----|--------|---------|
| **B-2** | Menu search misses `sweet` / `mithai` / desserts category | TBD |
| **B-5** | LLM sometimes read-backs in Punjabi (`ਇੱਕ`, rupees) not English template | Prompt tighten / post-process |
| **B-8** | Long TTS lists get interrupted | Hard cap enforcement |
| **B-9/B-10** | Cold LLM TTFT; tool double-hop on menu | Prompt/cache optimization |
| **Echo (residual)** | Heavy echo on outbound India test calls — use inbound CA number for realistic test | Monitor after 017 deploy |

See **`docs/plan/10-voice-quality-tier-b.md`** for full backlog.

---

## Phone order flow (intended, after PR 016–017)

```
Greet → browse/add items → "Anything else?" → allergies (English)
  → pickup/delivery → read-back + "All good?" (English one/two, dollars)
  → name → phone → place_order() [log only until 8c]
```

Phase enum: `restaurant/order_flow.py` → `OrderPhase`.

Fixed spoken lines (`restaurant/conversation.py`):

| Line | Constant |
|------|----------|
| Allergies | `ALLERGIES_QUESTION` |
| Pickup/delivery | `PICKUP_DELIVERY_QUESTION` |
| Quantity | `QUANTITY_QUESTION` |
| Confirm close | `CONFIRM_CLOSE` (`"All good?"`) |

---

## What's NOT done — roadmap

### Web — Order with Sierra

See **`docs/plan/11-web-order-with-sierra.md`**.

| Phase | Scope | Status |
|-------|--------|--------|
| W1–W2 | Shell + live cart | ✅ |
| **W3** | Menu highlight, modifier picker, tap-add ack | ⬜ **Next web** |
| W4 | Avatar | ⬜ |
| W5 | Hardening | ⬜ |
| W6 | Web prompt variant | ✅ (PR 015 `prompts.py`) |

### Phase 8c–8f (Clover POS)

| Phase | Scope | Status |
|-------|--------|--------|
| **8c** | Submit orders to Clover checkout API | ⬜ **Next product milestone** |
| 8d | Webhooks + 86'd items | ⬜ |
| 8e | Production pilot | ⬜ |
| 8f | Multi-tenant SaaS | ⬜ |

---

## Key files (where logic lives)

| File | Role |
|------|------|
| `agent.py` | Entrypoint, tools, echo hook, turn guidance inject, web_sync |
| `restaurant/prompts.py` | Phone + web system prompts |
| `restaurant/conversation.py` | Intents, templates, `is_confirm_yes()`, read-back format |
| `restaurant/order_flow.py` | Phase machine, `[TURN GUIDANCE]` builder |
| `restaurant/phone_echo.py` | Phone echo filter (B-1 — PR 017) |
| `restaurant/session_config.py` | Shared turn handling (phone + web) |
| `restaurant/web_sync.py` | Web order.state + cart RPCs |
| `restaurant/orders.py` | `OrderCart`, summaries |
| `restaurant/menu_provider.py` | Menu tools + Clover cache |
| `restaurant/menu.py` | Static fallback menu + `RESTAURANT_NAME` |
| `token_server.py` | `/token`, `/menu`, `/health` |
| `web/src/` | React Order with Sierra UI |
| `scripts/vps_deploy.sh` | Production deploy |
| `scripts/test_call.py` | Outbound Twilio test (India = extra echo/latency) |

---

## Ops cheat sheet

```bash
# SSH
ssh root@89.117.18.192

# Deploy (after main updated)
bash /opt/livekit-sarvam/scripts/vps_deploy.sh

# Outbound test (expect more echo than inbound)
cd /opt/livekit-sarvam
PYTHONPATH=/opt/livekit-sarvam uv run python scripts/test_call.py +919413752688

# Watch conversation
journalctl -u restaurant-agent -f | grep -E 'USER:|SIERRA:|TURN_GUIDANCE|Ignoring|Session started|ORDER_PLACED|LATENCY'

# Health
systemctl is-active restaurant-agent restaurant-token caddy
curl -s https://voice.bizbull.ai/health
```

### Env vars (`/opt/livekit-sarvam/.env`)

| Variable | Default | Purpose |
|----------|---------|---------|
| `USE_CLOVER_MENU` | 1 | Required on VPS |
| `PHONE_ENDPOINTING_MAX` | 0.8 | Turn end delay |
| `PHONE_GREETING_SETTLE_SEC` | 2.0 | Pause after greeting (phone) |
| `PHONE_AEC_WARMUP_SEC` | 1.0 | AEC warmup (phone) |

Restart after `.env` change: `systemctl restart restaurant-agent`.

---

## PR history (recent)

| PR | Topic | Merged |
|----|-------|--------|
| 013 | Web shared latency + Mango Kulfi TTS | ✅ |
| 014 | Handoff docs sync | ✅ |
| 015 | Conversation layer + W6 web prompt | ✅ `e341262` |
| 016 | Order flow phrases + Bizbull branding | ⬜ Open |
| 017 | Echo filter + intent/flow hardening | ⬜ Open (stacked on 016) |

Full index: **`pr/README.md`**.

---

## Test numbers

| Item | Value |
|------|-------|
| Twilio (inbound/production test) | `+15878175156` |
| Dev mobile (outbound test) | `+919413752688` — India PSTN, **more echo** than inbound |
| Web | `https://voice.bizbull.ai` |
| LiveKit Cloud | `bizbull-restaurant-cyeyyw0l.livekit.cloud` |

---

## Recommended next session priorities

1. **Merge PR 016 + 017** → deploy VPS → run phone checklist in `pr/pr_017_echo-and-flow-hardening.md`
2. **Tier B-2** — menu search aliases (`sweet`, `mithai`, `dessert`)
3. **Web W3** — menu highlight, modifier picker
4. **Phase 8c** — Clover order submit from `place_order()`

---

## Doc map

| Doc | When to read |
|-----|--------------|
| **This file** | Every new conversation |
| `pr/pr_016_order-flow-phrases.md` | Phrase/phase fixes (open) |
| `pr/pr_017_echo-and-flow-hardening.md` | Echo + confirm fixes (open) |
| `docs/plan/10-voice-quality-tier-b.md` | Voice bug backlog + status |
| `docs/plan/11-web-order-with-sierra.md` | Web W3–W6 |
| `docs/plan/09-clover-pos.md` | Clover 8c+ |
| `docs/vps-config.md` | VPS, Caddy, SIP |
| `pr/pr_rules.md` | How to open PRs |
