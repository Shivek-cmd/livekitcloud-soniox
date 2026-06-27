# Sierra — Session Handoff (start here)

> **Primary doc for new conversations.** Read this first, then drill into linked files.
> Last updated: **2026-06-27** (end of Tier A phone latency + voice polish day).
> **VPS / main:** commit `dd8c5e2` deployed on `89.117.18.192`.

---

## What this project is

**Sierra** — Punjabi-English voice agent for **Bizbull Restaurant** (Canadian market).

| Channel | Number / URL | Status |
|---------|--------------|--------|
| **Phone (primary)** | `+15878175156` via Twilio → LiveKit Cloud SIP | Production testing |
| **Web (secondary)** | `sarvam.bizbull.ai` | Works; faster latency config than phone |

**Stack:** LiveKit Cloud + Soniox STT/TTS (`Maya`, `language=pa`) + GPT-4o-mini + Clover menu cache (61 items).

**Repo:** `git@github.com:Shivek-cmd/livekitcloud-soniox.git` (GitHub may redirect from old `livekit-sarvam` name).

---

## What's DONE (do not re-litigate)

### Infrastructure (Phases 1–5) ✅
- LiveKit **Cloud** (not self-hosted) — echo fixed, trunk Krisp NC
- Soniox + GPT stack — US-reachable, replaced India-hosted Sarvam stack
- Twilio SIP inbound + outbound test script
- VPS deploy: `scripts/vps_deploy.sh`, git SSH on VPS

### Voice / speech (PR 006–007) ✅
- **`speech_policy.py`** — Gurmukhi `voice_line` default; English only for Fish Pakora, Chole Bhature Combo, tandoor items, etc.
- **`clover_voice_labels.json`** — 61 items with `voice_line`, `speech_mode`, aliases
- Prompt bans `1x/2x/3x`; word quantities (do, ik, two)
- **`phone_echo.py`** — filters acoustic echo of agent TTS on phone (still has false-positive bugs — see Tier B)

### Clover menu (Phase 8a–8b) ✅
- Sandbox probe + **`menu_cache_bizbull.json`** (61 items synced from Clover)
- **`USE_CLOVER_MENU=1`** → `menu_provider.py` uses cache; tools: `check_menu_item`, `search_menu_items`
- Voice labels merged on every deploy (`rebuild_voice_labels.py` + `clover_sync_menu.py`)
- **`place_order()`** logs only — **does NOT submit to Clover yet** (Phase 8c)

### Tier A — Phone latency (PR 008, 2026-06-27) ✅
**Problem:** Phone felt slow (~2–6s dead air) and robotic. Root cause was deliberate slow config from PR 005 echo fix (`min_endpointing_delay=1.0`, `preemptive_generation=False`, STT-only turns).

**Fix:** New **`restaurant/session_config.py`** + **`restaurant/turn_latency.py`**

| Before (PR 005 phone) | After (Tier A, current) |
|----------------------|-------------------------|
| `turn_detection="stt"` | `inference.TurnDetector(version="v1-mini")` |
| `min_endpointing_delay=1.0` | Dynamic endpointing **0.2–0.8s** |
| `preemptive_generation=False` | **True** + `preemptive_tts=True` |
| `allow_interruptions=False` | **Adaptive** interruptions (`min_words=1`) |
| Greeting sleep 4s | **2.0s** (configurable) |
| No latency metrics | **`LATENCY` log lines** per turn |

**Bundled Silero VAD:** LiveKit Agents 1.6.x auto-loads `inference.VAD(model="silero")` when using TurnDetector — **no** `livekit-plugins-silero` package.

**Verified on test calls (2026-06-27):** No echo loop; `eou_delay` mostly **0.5–0.9s** (was 2.5s); natural 2-item menu offers (no numbered lists); user reported call feels good at **0.8s max_delay**.

---

## What's NOT done — roadmap

### Phase 8c–8f (Clover POS — next product work)

| Phase | Scope | Status |
|-------|--------|--------|
| **8c** | Submit orders to Clover (atomic checkout → create → print) | ⬜ **Next** |
| **8d** | Webhooks + 86'd item availability | ⬜ |
| **8e** | Production pilot (OAuth, one merchant) | ⬜ |
| **8f** | Multi-tenant SaaS routing | ⬜ |

See **`docs/plan/09-clover-pos.md`** for full design. **`docs/plan/06-milestones.md`** for phase tracker.

### Tier B — Voice quality / conversation (bugs from live calls)

See **`docs/plan/10-voice-quality-tier-b.md`** for full backlog. Top items:

1. **`phone_echo.py` false positives** — real questions that repeat dish names Sierra just said get dropped (`StopResponse` → dead air)
2. **Menu search gaps** — `search_menu("mithhe")` / `("sweet")` / category queries fail; LLM says "not found" when desserts exist
3. **Quantity too early** — asks "ਕਿੰਨਾ?" before customer confirms they want the item
4. **Order flow not enforced in code** — 280-line prompt only; LLM still mashups (price + combo + spice in one turn)
5. **Prompt size** — ~3800+ tokens → cold LLM **~1.5–3s TTFT** on first turns
6. **No TTS post-processor** — LLM can still output Roman dish names, quotes, numbered lists despite prompt
7. **Mid-call re-greeting** after missed turns
8. **Long TTS replies cut off** when user interrupts (~8s audio)

---

## Key files (where logic lives)

| File | Role |
|------|------|
| `agent.py` | System prompt, tools, phone echo hook, entrypoint |
| `restaurant/session_config.py` | **Phone vs web** `AgentSession` + turn handling |
| `restaurant/turn_latency.py` | Per-turn `LATENCY` logging |
| `restaurant/voice_stack.py` | Soniox STT/TTS + GPT builders |
| `restaurant/phone_echo.py` | Echo filter (needs Tier B fix) |
| `restaurant/menu_provider.py` | Menu tools facade; search capped at 2 items |
| `restaurant/clover/speech_policy.py` | `voice_line` / `speech_mode` per dish |
| `restaurant/clover/menu.py` | Cache load, find, search |
| `data/menu_cache_bizbull.json` | Clover menu truth (61 items) |
| `data/clover_voice_labels.json` | Gurmukhi labels + voice_line |
| `scripts/vps_deploy.sh` | Pull main + sync menu + restart |

---

## Menu → speech pipeline (how Sierra reads the menu)

```
Caller speech → Soniox STT → GPT → tools (check_menu_item / search_menu_items)
    → menu cache + voice labels → voice_line in tool text
    → GPT writes reply (Gurmukhi + English code-mix)
    → Soniox TTS (language=pa) speaks LLM text as-is
```

**Not** a separate TTS menu reader. **Script matters:** Gurmukhi for most dishes; English `voice_line` only for items in `ENGLISH_VOICE_KEYS` in `speech_policy.py`.

---

## Phone session tuning (env vars)

Set in `/opt/livekit-sarvam/.env` — no code change needed:

| Variable | Default | Purpose |
|----------|---------|---------|
| `PHONE_ENDPOINTING_MAX` | **0.8** | Max wait after speech before turn ends (lower = snappier, more cut-off risk) |
| `PHONE_ENDPOINTING_MIN` | 0.2 | Min endpointing delay |
| `PHONE_PREEMPTIVE_GENERATION` | true | Start LLM before turn fully confirmed |
| `PHONE_PREEMPTIVE_TTS` | true | Start TTS early |
| `PHONE_GREETING_SETTLE_SEC` | 2.0 | Pause after greeting before listening |
| `PHONE_AEC_WARMUP_SEC` | 1.0 | AEC warmup on phone |
| `PHONE_INTERRUPTION_MIN_WORDS` | 1 | Min STT words to count as barge-in |
| `USE_CLOVER_MENU` | 1 | Load Clover cache (required on VPS) |

After `.env` change: `systemctl restart restaurant-agent`.

---

## Ops cheat sheet

```bash
# SSH
ssh -i ~/.ssh/livekit_vps root@89.117.18.192

# Deploy
bash /opt/livekit-sarvam/scripts/vps_deploy.sh

# Test call (outbound to your phone)
cd /opt/livekit-sarvam
PYTHONPATH=/opt/livekit-sarvam uv run python scripts/test_call.py +919413752688

# Watch conversation + latency
journalctl -u restaurant-agent -f | grep -E 'USER:|SIERRA:|LATENCY|Ignoring|EOU metrics'

# Services
systemctl status restaurant-agent restaurant-token
```

---

## PR history (recent)

| PR | Topic | Merged |
|----|-------|--------|
| 005 | Clover prompt + phone echo fix | ✅ |
| 006 | Voice speech policy + phone echo tuning | ✅ |
| 007 | TTS Gurmukhi default, ban 2x | ✅ |
| **008** | **Tier A latency + menu list style + 0.8 endpointing** | ✅ (`f63829e` → `dd8c5e2`) |

PR docs in **`pr/`** folder. **`pr/pr_rules.md`** for workflow.

---

## Test numbers & accounts

| Item | Value |
|------|-------|
| Twilio test number | `+15878175156` |
| Dev test mobile | `+919413752688` (India — adds PSTN latency vs Canadian caller) |
| LiveKit Cloud | `bizbull-restaurant-cyeyyw0l.livekit.cloud` |
| VPS path | `/opt/livekit-sarvam/` |

---

## Recommended next session priorities

1. **Tier B-1:** Fix `phone_echo.py` — don't drop turns with price/availability questions that overlap agent dish names
2. **Tier B-2:** Menu search aliases (`sweet`, `mithai`, `dessert`, `starter`, `drink`) + category search
3. **Phase 8c:** Clover atomic order submit from `place_order()`
4. Optional: Shorter prompt or state machine for order flow

---

## Doc map

| Doc | When to read |
|-----|--------------|
| **This file** | Every new conversation |
| `docs/plan/06-milestones.md` | Phase status |
| `docs/plan/09-clover-pos.md` | Clover integration design |
| `docs/plan/10-voice-quality-tier-b.md` | Known voice bugs + fixes |
| `docs/vps-config.md` | VPS, deploy, env, SIP |
| `docs/plan/02-architecture.md` | System diagram |
| `pr/pr_008_tier-a-phone-latency.md` | What Tier A changed |
| `docs/reference/` | LiveKit, Soniox, Clover captured docs |
