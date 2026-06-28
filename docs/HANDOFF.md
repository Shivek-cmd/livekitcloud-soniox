# Sierra — Session Handoff (start here)

> **Primary doc for new conversations.** Read this first, then drill into linked files.
> Last updated: **2026-06-28** (web W1–W2 shipped, domain migration, shared latency).
> **VPS / main:** commit `0666017` on `89.117.18.192`.

---

## What this project is

**Sierra** — Punjabi-English voice agent for **Bizbull Restaurant** (Canadian market).

| Channel | Number / URL | Status |
|---------|--------------|--------|
| **Phone (primary)** | `+15878175156` via Twilio → LiveKit Cloud SIP | Production testing |
| **Web** | **`https://voice.bizbull.ai`** | W1–W2 live (Order with Sierra tab) |

**Stack:** LiveKit Cloud + Soniox STT/TTS (`Maya`, `language=pa`) + GPT-4o-mini + Clover menu cache (61 items).

**Repo:** `git@github.com:Shivek-cmd/livekitcloud-soniox.git` (GitHub may redirect from old `livekit-sarvam` name).

**Deploy:** Owner runs deploy on VPS (`bash scripts/vps_deploy.sh`) — do **not** run two `npm` builds in parallel on the small VPS (OOM risk).

---

## What's DONE (do not re-litigate)

### Infrastructure (Phases 1–5) ✅
- LiveKit **Cloud** (not self-hosted) — echo fixed, trunk Krisp NC
- Soniox + GPT stack — US-reachable, replaced India-hosted Sarvam stack
- Twilio SIP inbound + outbound test script
- VPS deploy: `scripts/vps_deploy.sh` (pull main + menu sync + **npm web build** + restart)

### Voice / speech (PR 006–007, 013) ✅
- **`speech_policy.py`** — Gurmukhi `voice_line` default; English overrides for Fish Pakora, Chole Bhature Combo, tandoor items, **Mango Kulfi**, etc.
- **`clover_voice_labels.json`** — 61 items with `voice_line`, `speech_mode`, aliases
- Prompt bans `1x/2x/3x`; word quantities (do, ik, two)
- **`phone_echo.py`** — filters acoustic echo of agent TTS on phone (still has false-positive bugs — see Tier B)

### Clover menu (Phase 8a–8b) ✅
- Sandbox probe + **`menu_cache_bizbull.json`** (61 items synced from Clover)
- **`USE_CLOVER_MENU=1`** → `menu_provider.py` uses cache; tools: `check_menu_item`, `search_menu_items`
- Voice labels merged on every deploy (`rebuild_voice_labels.py` + `clover_sync_menu.py`)
- **`place_order()`** logs only — **does NOT submit to Clover yet** (Phase 8c)

### Tier A — Phone latency (PR 008) ✅
**Problem:** Phone felt slow (~2–6s dead air). **Fix:** `restaurant/session_config.py` + `restaurant/turn_latency.py` — TurnDetector v1-mini, dynamic endpointing **0.2–0.8s**, preemptive TTS.

### Web — Order with Sierra (PR 009–013, 2026-06-28) ✅

| PR | What shipped |
|----|--------------|
| **009** | Domain **`voice.bizbull.ai`** (retired `sarvam.bizbull.ai`); relative `/token`; Caddy + deploy builds `web/dist` |
| **010** | Plan doc `docs/plan/11-web-order-with-sierra.md` |
| **011 W1** | Tab shell: **Order with Sierra** \| Store; 3-panel layout (Sierra + live menu + order stub); captions; `GET /menu` |
| **012 W2** | **Live order panel + hybrid cart** — `order.state` push, cart RPCs, tap **Add**, qty steppers; `restaurant/web_sync.py` |
| **013** | Web uses **same turn latency as phone** (0.8s max endpointing); **Mango Kulfi** says English not "amb kulfi" |

**Web architecture (current):**
```
Browser (voice.bizbull.ai)
  ├─ GET /menu, /token  → token_server (Caddy → :8001)
  ├─ LiveKit WebRTC     → agent in room
  └─ order.state + RPCs → restaurant/web_sync.py ↔ OrderCart (server truth)
```

**Key web files:** `web/src/components/OrderWithSierra.tsx`, `SierraPanel`, `LiveMenu`, `OrderPanel`, `web/src/hooks/useCart.tsx`, `token_server.py` (`/menu`).

**Store tab:** placeholder — build after W3–W6.

---

## What's NOT done — roadmap

### Web — Order with Sierra (next)

See **`docs/plan/11-web-order-with-sierra.md`**.

| Phase | Scope | Status |
|-------|--------|--------|
| **W3** | Menu highlight (`ui.focus`), modifier picker, Sierra ack on tap-add | ⬜ **Next web work** |
| W4 | Avatar (provider TBD) | ⬜ |
| W5 | Hardening (reconnect, idle timeout, rate limits) | ⬜ |
| W6 | Web prompt variant (prices on screen, tap awareness) | ⬜ |

### Phase 8c–8f (Clover POS)

| Phase | Scope | Status |
|-------|--------|--------|
| **8c** | Submit orders to Clover (atomic checkout → create → print) | ⬜ **Next product (phone + web orders)** |
| 8d | Webhooks + 86'd item availability | ⬜ |
| 8e | Production pilot (OAuth, one merchant) | ⬜ |
| 8f | Multi-tenant SaaS routing | ⬜ |

See **`docs/plan/09-clover-pos.md`**.

### Tier B — Voice quality / conversation (bugs from live calls)

See **`docs/plan/10-voice-quality-tier-b.md`**. Top items:

1. **`phone_echo.py` false positives** — real questions dropped → dead air
2. **Menu search gaps** — `search_menu("mithhe")` / `("sweet")` fails; desserts exist
3. **Quantity too early** — asks "ਕਿੰਨਾ?" before customer confirms item
4. **Order flow not enforced in code** — prompt-only; LLM mashups
5. **Prompt size** — cold LLM ~1.5–3s TTFT
6. **Mid-call re-greeting** after missed turns

---

## Key files (where logic lives)

| File | Role |
|------|------|
| `agent.py` | System prompt, tools, phone echo hook, web_sync bind, entrypoint |
| `restaurant/session_config.py` | **Shared** turn handling (phone + web); phone-only AEC warmup |
| `restaurant/web_sync.py` | Web: `order.state` publish + cart RPCs |
| `restaurant/orders.py` | `OrderCart`, `to_state_dict()`, cart mutators |
| `restaurant/turn_latency.py` | Per-turn `LATENCY` logging |
| `restaurant/voice_stack.py` | Soniox STT/TTS + GPT builders |
| `restaurant/phone_echo.py` | Echo filter (needs Tier B fix) |
| `restaurant/menu_provider.py` | Menu tools + `catalog()` + `find_item_by_id()` |
| `restaurant/clover/speech_policy.py` | `voice_line` / `speech_mode` per dish |
| `token_server.py` | `/token`, `/menu`, `/health` |
| `web/src/` | React app (`@livekit/components-react`) |
| `scripts/vps_deploy.sh` | Pull main + labels + menu sync + **npm build** + restart |
| `scripts/test_call.py` | Outbound Twilio test call to your phone |

---

## Turn / latency tuning (phone **and** web)

Both channels share `_turn_handling()` in `session_config.py`. Env vars in `/opt/livekit-sarvam/.env`:

| Variable | Default | Purpose |
|----------|---------|---------|
| `PHONE_ENDPOINTING_MAX` | **0.8** | Max wait after speech before turn ends |
| `PHONE_ENDPOINTING_MIN` | 0.2 | Min endpointing delay |
| `PHONE_PREEMPTIVE_GENERATION` | true | Start LLM before turn fully confirmed |
| `PHONE_PREEMPTIVE_TTS` | true | Start TTS early |
| `PHONE_GREETING_SETTLE_SEC` | 2.0 | Phone only — pause after greeting |
| `PHONE_AEC_WARMUP_SEC` | 1.0 | Phone only — AEC warmup |
| `USE_CLOVER_MENU` | 1 | Load Clover cache (required on VPS) |

After `.env` change: `systemctl restart restaurant-agent`.

---

## Ops cheat sheet

```bash
# SSH
ssh root@89.117.18.192

# Deploy (pull main, sync menu, rebuild web, restart agent + token)
bash /opt/livekit-sarvam/scripts/vps_deploy.sh

# Test call (outbound to your phone)
cd /opt/livekit-sarvam
PYTHONPATH=/opt/livekit-sarvam uv run python scripts/test_call.py +919413752688

# Watch conversation + latency
journalctl -u restaurant-agent -f | grep -E 'USER:|SIERRA:|LATENCY|Ignoring|ORDER_PLACED|web-sync'

# Services
systemctl is-active restaurant-agent restaurant-token caddy

# Live URLs
curl -s https://voice.bizbull.ai/health
curl -s https://voice.bizbull.ai/menu | head -c 200
```

---

## PR history (recent)

| PR | Topic | Merged |
|----|-------|--------|
| 008 | Tier A phone latency + 0.8 endpointing | ✅ |
| 009 | Web domain → `voice.bizbull.ai` | ✅ |
| 010 | Web Order-with-Sierra plan doc | ✅ |
| 011 | Web W1 — tabs + 3-panel + live menu + captions | ✅ |
| 012 | Web W2 — live order + hybrid tap-to-add | ✅ |
| 013 | Web shared latency + Mango Kulfi TTS fix | ✅ (`0666017`) |

PR docs in **`pr/`** folder. **`pr/pr_rules.md`** for workflow.

---

## Test numbers & accounts

| Item | Value |
|------|-------|
| Twilio test number | `+15878175156` |
| Dev test mobile | `+919413752688` (India — adds PSTN latency) |
| Web app | `https://voice.bizbull.ai` |
| LiveKit Cloud | `bizbull-restaurant-cyeyyw0l.livekit.cloud` |
| VPS path | `/opt/livekit-sarvam/` |

---

## Recommended next session priorities

1. **Web W3** — menu highlight (`ui.focus`), modifier picker, tap-add voice ack
2. **Tier B-1** — `phone_echo.py` false positives
3. **Tier B-2** — menu search aliases (`sweet`, `mithai`, `dessert`)
4. **Phase 8c** — Clover order submit from `place_order()`

---

## Doc map

| Doc | When to read |
|-----|--------------|
| **This file** | Every new conversation |
| `docs/plan/11-web-order-with-sierra.md` | Web product plan + W3–W6 |
| `docs/plan/06-milestones.md` | Phase status |
| `docs/plan/09-clover-pos.md` | Clover integration design |
| `docs/plan/10-voice-quality-tier-b.md` | Known voice bugs + fixes |
| `docs/vps-config.md` | VPS, deploy, env, SIP, Caddy |
| `docs/plan/02-architecture.md` | System diagram |
| `pr/pr_011` … `pr/pr_013` | Recent web PR details |
