# Sierra — Session Handoff (start here)

> **Primary doc for new conversations.** Read this first, then drill into linked files.
> Last updated: **2026-06-29** (PR 019–020 merged on `main`; PR 021 open; PR 016–018 still open).
> **VPS:** `89.117.18.192` — `/opt/livekit-sarvam/` — deploy **`main`** after PRs merge.

---

## What this project is

**Sierra** — Punjabi-English voice agent for **Bizbull Restaurant** (Canadian market).

| Channel | Number / URL | Status |
|---------|--------------|--------|
| **Phone (primary)** | `+15878175156` via Twilio → LiveKit Cloud SIP | Production testing |
| **Web** | **`https://voice.bizbull.ai`** | W1–W2 live + **web ambient audio** (PR 020) |

**Stack:** LiveKit Cloud + Soniox STT/TTS (`Maya`, `language=pa`) + GPT-4o-mini + Clover menu cache (61 items).

**Repo:** `git@github.com:Shivek-cmd/livekitcloud-soniox.git` (GitHub redirects from old `livekit-sarvam` name).

**Deploy:** Owner runs `bash scripts/vps_deploy.sh` on VPS — do **not** run two `npm` builds in parallel (OOM risk).

**Restaurant name:** **Bizbull Restaurant** everywhere (Gurmukhi: `ਬਿਜ਼ਬਲ ਰੈਸਟੋਰੈਂਟ`). Old "Punjab Da Dhaba" branding removed in PR 016 (when merged).

---

## Git / PR state (2026-06-29)

| Branch | PR doc | Status | Notes |
|--------|--------|--------|-------|
| `main` | — | ✅ through **PR 020** | Last merge: `260f183` web ambient audio |
| `pr_016_order-flow-phrases` | `pr/pr_016_order-flow-phrases.md` | ⬜ **Open** | Phrases, phase fixes, Bizbull rename |
| `pr_017_echo-and-flow-hardening` | `pr/pr_017_echo-and-flow-hardening.md` | ⬜ **Open** | Echo + intent + read-back (stacked on 016) |
| `pr_018_customer-language` | `pr/pr_018_customer-language.md` | ⬜ **Open** | Greeting + language state (stacked on 017) |
| `pr_021_web-ambient-volume` | `pr/pr_021_web-ambient-volume.md` | ⬜ **Open** | Default ambient volume **0.25 → 0.6** |

**Recently merged to `main`:**

| PR | Topic | Merge |
|----|-------|-------|
| **019** | Mango Shake/Lassi English TTS; Chole/Bhatura Gurmukhi | GitHub PR #44 → `2bf30d2` |
| **020** | Web-only `BackgroundAudioPlayer` ambient loop | GitHub PR #45 → `260f183` |

**To ship next:** merge **016 → 017 → 018** (phone/language stack), then **021** (ambient volume) → `bash scripts/vps_deploy.sh`.

PR workflow: **`pr/pr_rules.md`** — doc first, branch name = doc name, merge via GitHub.

---

## What's DONE (do not re-litigate)

### Infrastructure (Phases 1–5) ✅
- LiveKit **Cloud** (not self-hosted) — trunk Krisp NC
- Soniox + GPT stack — US-reachable
- Twilio SIP inbound + `scripts/test_call.py` outbound
- VPS deploy: `scripts/vps_deploy.sh` (pull main + menu sync + npm web build + restart)

### Voice / speech (PR 006–007, 013, 019) ✅
- **`speech_policy.py`** + **`clover_voice_labels.json`** — 61 items with `voice_line`, `speech_mode`, aliases
- English TTS overrides: Fish Pakora, tandoor items, **Mango Kulfi**, **Mango Shake**, **Mango Lassi**, Paneer Tikka, etc.
- Gurmukhi TTS: **ਛੋਲੇ**, **ਭਟੂਰਾ**, **ਛੋਲੇ ਭਟੂਰੇ ਕੌਂਬੋ**, dal/saag/desserts, etc. (PR 019 fixed chole/bhature; removed wrong English override)
- Prompt bans `1x/2x/3x`; word quantities
- Rebuild labels: `scripts/rebuild_voice_labels.py` — tests in `tests/test_speech_policy.py`

### Clover menu (Phase 8a–8b) ✅
- **`menu_cache_bizbull.json`** (61 items) + `USE_CLOVER_MENU=1`
- Tools: `check_menu_item`, `search_menu_items`
- **`place_order()`** logs only — **does NOT submit to Clover** (Phase 8c)

### Tier A — Phone latency (PR 008) ✅
`restaurant/session_config.py` + `turn_latency.py` — TurnDetector, **0.2–0.5s** endpointing (phone + web), preemptive TTS.

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
| **`agent.py`** | Entrypoint, tools, echo hook, turn guidance, web_sync, **web ambient** |
| **`tests/test_conversation.py`** | Intent + flow unit tests |

### Web ambient audio (PR 020, on `main`) ✅
- **`restaurant/ambient_audio.py`** — LiveKit `BackgroundAudioPlayer`, **web only** (phone unchanged)
- Loops `data/audio/restaurant_ambience.mp3` if present; else builtin `OFFICE_AMBIENCE`
- Env: `WEB_AMBIENT_ENABLED`, `WEB_AMBIENT_VOLUME`, `WEB_AMBIENT_FADE_IN`, `WEB_AMBIENT_AUDIO_PATH`
- PR 020 shipped at volume **0.25**; **PR 021** raises default to **0.6** (merge + deploy to hear louder loop)
- Logs: `journalctl … | grep -i ambient`

---

## Open PRs — phone + language (NOT on `main` until merged)

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

**Tests:** `tests/test_phone_echo.py` + extended `test_conversation.py`.

### PR 018 — Customer language + greeting (stacked on 017)
- **Greeting:** `OPENING_GREETING` — trilingual hello (phone + web)
- **`preferred_language`** — script detect (pa/hi/en) → injected every `[TURN GUIDANCE]`
- **Web:** UI English ≠ reply language; localized "anything else?" / name ask
- **Fixed order steps** still English only (allergies, read-back, etc.)

**Ship order:** 016 → 017 → 018 → deploy → test phone + web language.

---

## Known issues still open

| ID | Issue | Next PR |
|----|--------|---------|
| **B-2** | Menu search misses `sweet` / `mithai` / desserts category | TBD |
| **B-11** | LLM says item "not on menu" without calling `check_menu_item` (paneer tikka, papad exist in cache) | Availability turn guidance in `order_flow.py` |
| **B-5** | LLM sometimes read-backs in Punjabi (`ਇੱਕ`, rupees) not English template | Prompt tighten / post-process |
| **B-8** | Long TTS lists get interrupted | Hard cap enforcement |
| **B-9/B-10** | Cold LLM TTFT; tool double-hop on menu | Prompt/cache optimization |
| **Speech audit** | ~20 more `voice_line` items flagged (naan, biryani, combos…) — only 5 fixed in PR 019 | TBD PR after audit review |
| **Echo (residual)** | Heavy echo on outbound India test calls — use inbound CA number | Monitor after 017 deploy |

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
| Ambient | Web background loop | ✅ PR 020 (+ volume PR 021) |

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
| `agent.py` | Entrypoint, tools, echo hook, turn guidance, web_sync, web ambient start/stop |
| `restaurant/ambient_audio.py` | Web `BackgroundAudioPlayer` config (PR 020) |
| `restaurant/clover/speech_policy.py` | Which items speak English vs Gurmukhi (PR 019) |
| `restaurant/prompts.py` | Phone + web system prompts |
| `restaurant/conversation.py` | Intents, templates, `is_confirm_yes()`, read-back format |
| `restaurant/order_flow.py` | Phase machine, `[TURN GUIDANCE]` builder |
| `restaurant/phone_echo.py` | Phone echo filter (B-1 — PR 017) |
| `restaurant/session_config.py` | Shared turn handling (phone + web) |
| `restaurant/web_sync.py` | Web order.state + cart RPCs |
| `restaurant/orders.py` | `OrderCart`, summaries |
| `restaurant/menu_provider.py` | Menu tools + Clover cache |
| `data/clover_voice_labels.json` | Per-item `voice_line` / `speech_mode` (rebuild via script) |
| `data/audio/` | Optional `restaurant_ambience.mp3` for web ambient |
| `token_server.py` | `/token`, `/menu`, `/health` |
| `web/src/` | React Order with Sierra UI (`RoomAudioRenderer` plays agent + ambient tracks) |
| `scripts/vps_deploy.sh` | Production deploy |
| `scripts/rebuild_voice_labels.py` | Re-apply speech policy to voice labels JSON |

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

# Watch conversation + ambient
journalctl -u restaurant-agent -f | grep -E 'USER:|SIERRA:|TURN_GUIDANCE|ambient|Ignoring|Session started|ORDER_PLACED|LATENCY'

# Health
systemctl is-active restaurant-agent restaurant-token caddy
curl -s https://voice.bizbull.ai/health
```

### Env vars (`/opt/livekit-sarvam/.env`)

| Variable | Default | Purpose |
|----------|---------|---------|
| `USE_CLOVER_MENU` | 1 | Required on VPS |
| `PHONE_ENDPOINTING_MAX` | 0.5 | Turn end delay (phone + web) |
| `PHONE_ENDPOINTING_MIN` | 0.2 | Min turn end delay (phone + web) |
| `PHONE_GREETING_SETTLE_SEC` | 2.0 | Pause after greeting (phone) |
| `PHONE_AEC_WARMUP_SEC` | 1.0 | AEC warmup (phone) |
| `WEB_AMBIENT_ENABLED` | 1 | Web background loop on/off |
| `WEB_AMBIENT_VOLUME` | 0.6 (after PR 021) | Ambient loudness 0.0–1.0 |
| `WEB_AMBIENT_FADE_IN` | 1.0 | Fade-in seconds |
| `WEB_AMBIENT_AUDIO_PATH` | (optional) | Custom mp3/wav path |

Restart after `.env` change: `systemctl restart restaurant-agent`.

---

## PR history (recent)

| PR | Topic | Merged |
|----|-------|--------|
| 015 | Conversation layer + W6 web prompt | ✅ |
| 016 | Order flow phrases + Bizbull branding | ⬜ Open |
| 017 | Echo filter + intent/flow hardening | ⬜ Open |
| 018 | Trilingual greeting + customer language | ⬜ Open |
| **019** | Mango drink English + chole/bhature Gurmukhi TTS | ✅ `2bf30d2` |
| **020** | Web-only background ambient audio | ✅ `260f183` |
| **021** | Ambient default volume 0.6 | ⬜ Open |

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

1. **Merge PR 021** → deploy → confirm web ambient at volume 0.6
2. **Merge PR 016 + 017 + 018** → deploy → test phone + web language
3. **B-11** — force `check_menu_item` on availability turns (paneer tikka false negative)
4. **Tier B-2** — menu search aliases (`sweet`, `mithai`, `dessert`)
5. **Speech audit** — remaining English/Gurmukhi `voice_line` fixes (see session notes in tier B doc)
6. **Web W3** — menu highlight, modifier picker
7. **Phase 8c** — Clover order submit from `place_order()`

---

## Doc map

| Doc | When to read |
|-----|--------------|
| **This file** | Every new conversation |
| `pr/README.md` | Full PR index + merge status |
| `pr/pr_016_order-flow-phrases.md` | Phrase/phase fixes (open) |
| `pr/pr_019_speech-policy-mango-chole.md` | Mango/chole TTS (merged) |
| `pr/pr_020_web-background-ambient.md` | Web ambient (merged) |
| `pr/pr_021_web-ambient-volume.md` | Ambient volume (open) |
| `docs/plan/10-voice-quality-tier-b.md` | Voice bug backlog + status |
| `docs/plan/11-web-order-with-sierra.md` | Web W3–W6 |
| `docs/plan/09-clover-pos.md` | Clover 8c+ |
| `docs/vps-config.md` | VPS, Caddy, SIP, ambient env |
| `pr/pr_rules.md` | How to open PRs |
