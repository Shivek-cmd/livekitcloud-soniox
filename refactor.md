# Conversation Architecture Rebuild — Plan + Session Handoff

> **Read this first if you're a new session picking up the rebuild.**
> Written 2026-07-10. `main` @ `27c2d74` (PR #95 merge, engine rebuild stages 1–4).
> **Numbering correction (2026-07-11):** PR 059 was taken by the web-UI theme PR (#96),
> so the staged PRs below shift by one: salvage = **060**, brain = **061**,
> cutover = **062**, reorg = **063**. Read "PR 059" as 060, etc.
> Companion docs: `docs/HANDOFF.md` (project-wide state), `pr/pr_rules.md` (workflow), `restaurant/engine/README.md` (the engine being replaced).

---

## Part I — Session handoff context (why this plan exists)

### The situation

Sierra has **two complete conversation systems** in the tree, and neither is right:

1. **Old path — DEPLOYED.** `deploy/restaurant-agent.service` runs root `agent.py` (1534 lines: 13 function tools + a huge regex "checkout ladder" in `on_user_turn_completed`) + `restaurant/order_flow.py` + intent regexes in `restaurant/conversation.py`. The LLM drives conversation AND mutates the cart while parallel regex authorities fight it. This produced the "one fish → two invented dishes with invented quantity" live bug. **PR 030 tried to fix it with more prompt rules; live calls got worse; it was reverted** (see `docs/HANDOFF.md` "PR 030 — what happened").
2. **New engine — BUILT, NEVER WIRED.** `restaurant/engine/` (stages 1–4, 27 passing tests): deterministic phase machine, LLM demoted to a stateless JSON extractor. Bulletproof cart, but robotic and has real gaps found in audit: drops items added during checkout phases (`core.py:168` — adds only handled in COLLECTING/CLARIFY), 10-digit-only phone loop (`core.py:359`), no retry ceiling, extractor blind to cart ("make it two of those" unresolvable), no filler → latency regression, Hindi promised in greeting but unimplemented in renderer. **Nothing imports it except its own tests; there is no shadow-mode toggle; it never answered a call.**

### The decision (made with the user in this session)

Replace **both** with one hybrid: **LLM owns the conversation, code owns the cart.**

- A natural function-calling LiveKit agent (full chat context) drives: greet → items loop ("anything else?") → allergies → customization (spice/modifiers) → pickup/delivery (+address) → name/phone → readback → place.
- The LLM can only touch the order through **validating/resolving tools**: ambiguous dish → tool returns candidate options and refuses; unknown → NOT FOUND; missing spice/required modifier → tool refuses with what's needed. The LLM can never write an arbitrary item/price into the cart.
- **Readback text and the Clover order are always generated from the code cart, never from the LLM's memory** — the readback stays an independent check against ground truth. `place_order` is hard-gated in code.
- Why not pure-context LLM (user asked): readback generated from the same context that holds the order verifies nothing — a drifted quantity survives to the kitchen ticket. Why not keep the engine: PR 030's lesson cuts both ways — prompt-only rules fail, but a phase machine that fights natural conversation fails UX. Validation-at-the-tool-boundary is the piece the old design never had.

### User decisions (locked)

| Question | Decision |
|---|---|
| Per-item confirmation | **Natural echo per add + ONE hard code-generated final readback** (no per-item "yes?" gate) |
| Codebase reorg | **Full restructure**: `restaurant/agent/`, `restaurant/channels/`, `restaurant/analytics/` (git mv, history preserved) |
| Delivery | **Staged PRs** per `pr/pr_rules.md` — doc first, branch = doc name, never on main. Next PR number: **059** |

### Plan-level decisions (taken here; revisit if wrong)

- **Allergies = hard `place_order` gate** (`record_allergies` must run) — "never asks allergies" is a recorded prod bug; prompt-only rules proved regressive.
- **Required modifiers (incl. Spice Level) enforced at add-time** — tool refuses incomplete items; cart completeness is an invariant, asked at the natural moment, and `order_submit.py`'s note→modifier mapping expects the note at submit.
- **"No preference" spice → Medium** (in prompt; make configurable later).
- **`fillers.py` deleted** (env-gated OFF in prod; hard-coupled to `UserIntent`/`OrderPhase`; restore path noted in PR doc).
- **Static-menu fallback (`USE_CLOVER_MENU=0`) stays** — `menu_provider` abstracts it for free.
- **Web tap-to-add may insert spice-less items** — readback exposes the note; revisit after shadow logs.

### Gotchas a new session MUST know (verified by exploration)

1. **You cannot delete `conversation.py` wholesale.** Kept modules top-level-import it: `fillers.py:11`, `phone_background.py:8`, `stt_noise.py:7`; and lazily: `orders.py:52,78,94` (formatters), `menu_provider.py:136` (`is_availability_question`), `customer_info.py:210,222,263` (circular). Salvage first (PR 059), delete later (PR 061).
2. **`engine/` is a clean delete** — only its own tests import it. `engine/live.py` also imports `conversation.OPENING_GREETING`/`detect_customer_language` (dies with the package).
3. **`"Spice Level"` is a magic string** matched literally in 4 places (`clover/models.py describe()`, `menu.py catalog()`, `order_submit.py:126`, `menu_provider.py:339`). Define once in `gates.py`, don't rename.
4. **`submit_cart_to_clover` is SYNCHRONOUS urllib** (`clover/order_submit.py:304`). Must be called via `asyncio.to_thread` from async tool code (old agent + engine live.py both block the loop today).
5. **Systemd runs `python agent.py start`** (`deploy/restaurant-agent.service`) and **`scripts/setup_sip.py` dispatches on `agent_name="restaurant-agent"`** — keep both the filename and the agent name; root `agent.py` becomes a thin shim.
6. **`web_sync.py` reads `agent.cart`** (`to_state_dict`, `add_item`, `set_quantity_by_id`, `remove_by_id`) — the new agent must expose `.cart: OrderCart`, and web RPC mutations must bump `cart.revision` (forces re-readback).
7. **`token_server.py` `/menu`** depends only on `menu_provider.catalog()` — keep that working; web/admin have zero Python coupling to the agent.
8. **`session_recorder.finalize(cart, flow)`** reads `flow.state.preferred_language` — signature changes to `finalize(cart, *, preferred_language)`.
9. Matcher confidence landscape: `MenuCache.find_item_scored` abstains < `MENU_MATCH_MIN_CONF` (0.55); old add gate `ADD_CLARIFY_MIN_CONF` = 0.7 (keep); `menu_provider.disambiguation_options(name, limit=3)` (`menu_provider.py:253`) is the ambiguity→options primitive; `required_modifier_groups()` (`:285`), `item_has_spice_level()` (`:333`).
10. Menu data: `data/menu_cache_bizbull.json` — 61 items; "Spice Level" on 38 (Mild/Medium/Spicy/Extra Spicy); required groups exist (e.g. "Choose Curry" min_required>0). Voice pronunciation via `data/clover_voice_labels.json` overlay at `MenuCache.load`.
11. Env flags that matter: `USE_CLOVER_MENU`, `CLOVER_SUBMIT_ORDERS` (0 = shadow/log-only — the rollout gate), `CLOVER_PRINT_ORDERS`, `MENU_MATCH_MIN_CONF`, `ADD_CLARIFY_MIN_CONF`, `AUTO_HANGUP_AFTER_ORDER`, `SESSION_ANALYTICS_ENABLED`, `FILLERS_ENABLED` (dies with fillers.py).
12. Rollout doctrine (docs + engine README): **shadow mode → ONE pilot restaurant → rest.** Never flip `CLOVER_SUBMIT_ORDERS=1` without reviewing recorded calls in admin analytics first.

---

## Part II — The plan

## 1. Target tree (K=keep, N=new, M=moved `git mv`, R=rewritten/modified, D=deleted)

```
agent.py                          R  ~10-line shim: re-export entrypoint from restaurant.agent.worker,
                                     cli.run_app(agent_name="restaurant-agent")  ← systemd + setup_sip.py unchanged
token_server.py                   K  (menu_provider.catalog() untouched)
restaurant/
├── agent/                        N  ── the new brain ──
│   ├── __init__.py               N
│   ├── worker.py                 N  entrypoint(): plumbing carried 1:1 from old agent.py:1386-1534
│   ├── core.py                   N  RestaurantAgent(Agent): .cart, .state, tools, hygiene-only turn hook
│   ├── gates.py                  N  OrderSessionState + pure gate functions (place_order_blockers, readback staleness)
│   ├── prompt.py                 N  build_system_prompt(is_phone) — salvaged persona/language/no-price rules + new FLOW section
│   ├── replies.py                N  salvaged formatters: format_add/remove/update_tool_reply, format_order_readback,
│   │                                format_order_status, _cart_items_str, order_placed_goodbye, slim sanitize_assistant_speech
│   └── language.py               N  OPENING_GREETING, CustomerLanguage, detect_customer_language, update_preferred_language
├── channels/                     M  ── channel hygiene ── (PR 062)
│   ├── phone_echo.py             M+R  drop UserIntent coupling
│   ├── phone_background.py       M+R  drop UserIntent param
│   ├── stt_noise.py              M+R  inline looks_like_order_phrasing + _QTY_WORDS/_extract_qty
│   ├── ambient_audio.py          M
│   ├── call_control.py           M
│   └── web_sync.py               M   (needs agent.cart: OrderCart — new agent exposes it)
├── analytics/                    M  (PR 062)
│   ├── session_recorder.py       M+R  finalize(cart, *, preferred_language: str | None)
│   ├── analytics_store.py        M
│   └── turn_latency.py           M
├── clover/                       K  untouched: menu.py (MenuCache), match.py (phonetic matcher+abstain),
│                                    order_submit.py (sync Clover submit), speech_policy.py, client.py, models.py, …
├── tenants/                      K  untouched (get_default_tenant, SQLite store)
├── menu.py                       K  static fallback + DELIVERY_CHARGE constants
├── menu_provider.py              R  sever ONE lazy import (inline is_availability_question regex, :136); rest untouched
├── menu_browse.py                K  (menu_provider:188 depends on it)
├── orders.py                     R  formatters imported from restaurant.agent.replies; + revision:int counter
├── customer_info.py              R  sever 3 lazy circular imports back into conversation (:210,:222,:263)
├── text_match.py                 K
├── voice_stack.py                K  (Soniox STT/TTS, gpt-4o-mini)
├── session_config.py             K  (TurnDetector, endpointing, BVC, preemptive TTS)
├── llm_warmup.py                 R  import restaurant.agent.prompt.build_system_prompt
├── reservations.py               K
│
├── conversation.py               D  (1039 lines — after salvage)
├── order_flow.py                 D  (540 lines)
├── order_parse.py                D  (after _QTY_WORDS/_extract_qty move to stt_noise)
├── prompts.py                    D  (after salvage into agent/prompt.py)
├── fillers.py                    D
└── engine/                       D  entire package (core, extractor, renderer, resolver, live) — self-contained
```

## 2. The new agent in depth

### 2.1 `restaurant/agent/gates.py` — state + hard gates (pure, LLM-free, unit-testable)

```python
SPICE_GROUP = "Spice Level"   # the magic string, defined once (order_submit.py uses the same literal)

@dataclass
class OrderSessionState:
    preferred_language: CustomerLanguage = CustomerLanguage.ENGLISH  # sticky; goodbye + recorder only
    allergies_recorded: bool = False
    allergy_note: str = ""
    readback_revision: int | None = None    # cart.revision at last get_order_readback()
    readback_confirmed: bool = False
    real_user_turns: int = 0
```

- `place_order_blockers(cart, state) -> list[str]` — empty means go. Checks in order:
  no items · order_type unset · delivery without address · invalid name (`customer_info.is_valid_customer_name`)
  · phone not exactly 10 digits (`extract_phone_digits`; strip leading `1` on 11) · allergies not recorded
  · `not (state.readback_confirmed and state.readback_revision == cart.revision)`.
- `invalidate_readback(state)` — reset confirmed flag; called on **every** cart mutation.
- `OrderCart` gains `revision: int = 0`; every mutating path bumps it — **including `web_sync.py` RPC adds** — so a mid-checkout web add forces re-readback.

### 2.2 `restaurant/agent/core.py` — `RestaurantAgent` + tool schema

Holds `self.cart = OrderCart(delivery_charge=tenant.delivery_charge)`, `self.state = OrderSessionState()`, `self.is_phone`, `bind_*` methods (session/recorder/web_sync/job_context), `note_agent_speech` (echo-filter feed), `_record_tool`, `_sync_web`. Constructible without a session → tools directly unit-testable.

**Single resolution choke point** (all item tools route through it):

```python
def _resolve_menu_item(self, query) -> tuple[dict | None, str | None]:
    item = menu_provider.find_item(query)                      # matcher abstains < MENU_MATCH_MIN_CONF (0.55)
    if item and item.get("unavailable"): return None, "…not available right now. Offer an alternative."
    if item and item["match_confidence"] >= ADD_CLARIFY_MIN_CONF:   # keep 0.7 env gate
        return item, None
    options = menu_provider.disambiguation_options(query, limit=3)  # menu_provider.py:253
    if options:  return None, "AMBIGUOUS — '<q>' could mean: <opts>. Ask which one. Do NOT add anything yet."
    return None, "NOT FOUND — '<q>' is not on our menu. Never invent a dish."
```

The LLM can never write a name/price into the cart: adds go through the resolved `to_cart_dict()` payload only.

**Tools** (all `@function_tool` async methods; every mutation → bump `cart.revision`, `invalidate_readback`, `_sync_web`, `_record_tool`):

| # | Tool | Validation / behavior |
|---|------|----------------------|
| 1 | `add_item(item_query, quantity=1, spice_level=None, note="")` | qty clamp 1–20; `_resolve_menu_item`; **refuse** if `required_modifier_groups(id)` unmet ("NEEDS INFO — ask, then re-call with note") or `item_has_spice_level(name)` and no `spice_level` ("NEEDS SPICE — Mild/Medium/Spicy/Extra Spicy"). Spice validated against the 4 values; written into the note in the shape `order_submit._match_spice_modifier` maps. Returns `format_add_tool_reply` (no price). |
| 2 | `set_item_quantity(item_query, quantity)` | exact set, never additive; ≤0 removes; cart-line match by name substring → resolved id. |
| 3 | `remove_item(item_query)` | cart-line match; `format_remove_tool_reply`. |
| 4 | `set_item_spice(item_query, spice_level)` | "make the butter chicken spicy" corrections; validates; rewrites note. |
| 5 | `check_menu_item(name)` | wraps `menu_provider.check_item` (veg/desc; price INTERNAL semantics preserved). |
| 6 | `search_menu(query)` | wraps `menu_provider.search_menu` ("at most TWO in one casual sentence" rule preserved). |
| 7 | `record_allergies(response)` | sets `allergies_recorded=True`; non-"no" note stored + threaded to Clover submit note. |
| 8 | `set_order_type("pickup"\|"delivery")` | literal-validated; reply steers next step (address vs contact). |
| 9 | `set_delivery_address(address)` | min-length sanity; refuses empty/one-word. |
| 10 | `set_customer_contact(name=None, phone=None)` | `parse_customer_name`/`is_valid_customer_name` (refuse junk); `extract_phone_digits` must be 10 (accept 11 with leading 1 → strip); success returns `format_phone_spoken` English-word digits. **Not** gated on readback (contact precedes readback in the new flow; blockers enforce completeness regardless). |
| 11 | `get_order_readback()` | **the only source of readback text** — refuses with blocker text if anything's missing; else builds `format_order_readback(cart)` (channel price policy), sets `readback_revision = cart.revision`, returns "READ THIS BACK VERBATIM, then ask: Is that correct?" |
| 12 | `confirm_readback()` | refuses if `readback_revision != cart.revision` ("cart changed — read back again"); else `readback_confirmed=True`. |
| 13 | `place_order()` | runs `place_order_blockers`; any blocker returned verbatim. Clear → `await asyncio.to_thread(submit_cart_to_clover, cart, tenant=…, session_id=…, channel=…)`; honors `clover_submit_enabled()` shadow gate; Clover failure → spoken failure path, **never** a false "order's in"; `cart.mark_placed`; speaks `order_placed_goodbye(order_type, lang)` via `session.say`; schedules `call_control` auto-hangup (phone); returns "ORDER COMPLETE" sentinel (prompt: no further speech). |
| 14 | `transfer_to_human(reason)` | carried over. |
| 15–16 | `check_table_availability` / `book_reservation` | carried over, wrap `reservations.py`. |
| 17 | `get_order_summary()` | mid-call status from `cart.summary()`; phone no-price policy. |

**`on_user_turn_completed` — channel hygiene ONLY, no ladder:**
1. `phone_echo` rejection (+ existing greeting-tail reprompt scheduling) → `StopResponse`
2. `phone_background` chatter rejection (UserIntent param removed)
3. `stt_noise` rejection
4. `state.preferred_language = update_preferred_language(…)` (sticky; the LLM handles in-conversation language naturally from the transcript)
5. `real_user_turns += 1`; recorder turn hook.
Nothing else — no intent regexes, no auto-add, no ladder says, no turn-guidance injection.

### 2.3 `restaurant/agent/prompt.py`

Salvage verbatim from `prompts.py` (hard-won call lessons): persona, LANGUAGE block (Gurmukhi/Devanagari never Roman Indic; quantities as words never "2x"; phone digits as English words; checkout lines in English), voice_line/speech_mode rule, phone no-price block, web block, TRANSFER, NEVER list, ORDER COMPLETE sentinel. Drop all `[TURN GUIDANCE]` machinery.

New FLOW section (guidance — the *gates* are in code):

```
ORDER FLOW (natural, one question per turn):
greet → take items (after each add, "anything else?") → done → allergies (record_allergies)
→ pickup or delivery (set_order_type; delivery → set_delivery_address) → name, then phone (set_customer_contact)
→ get_order_readback, read it VERBATIM → on yes: confirm_readback, then place_order.
Handle changes at ANY point — after any cart change you must re-run get_order_readback before placing.
TRUST TOOL RESULTS: if a tool says AMBIGUOUS / NEEDS / NOT FOUND / a blocker, relay it and ask —
never work around it, never state items or totals from memory. "No preference" on spice = Medium.
```

Keep signature `build_system_prompt(*, is_phone: bool) -> str` so `llm_warmup.py` needs only an import change.

### 2.4 `restaurant/agent/worker.py` — entrypoint, carried 1:1 from `agent.py:1386-1534`

ctx.connect + wait_for_participant; `is_phone` detection (`sip_` prefix / `sip.callStatus`); `_sip_caller_phone`; `SessionRecorder` start + idempotent analytics flush on close/shutdown (now `finalize(cart, preferred_language=state.preferred_language.value)`); `TurnLatencyTracker.attach`; `schedule_llm_warmup(is_phone, tools=agent.tools)`; `build_agent_session` / `build_room_options`; ambient audio start/stop; `WebSync(room, agent)` on web; `user_input_transcribed` / `conversation_item_added` recorder hooks with slim `sanitize_assistant_speech`; `session.say(OPENING_GREETING)`; phone greeting settle + echo reprompt. Root `agent.py` shim keeps `agent_name="restaurant-agent"` and filename.

## 3. Migration in dependency-safe order = the staged PRs

### PR 059 — `pr_059_salvage-and-decouple` (zero behavior change; old agent keeps running)
1. Create `restaurant/agent/{__init__,language,replies,gates}.py`. Copy from `conversation.py`: greeting/language (:23-89) → `language.py`; formatters (:839-927) + `order_placed_goodbye` (:29) + slim `sanitize_assistant_speech` (:988) → `replies.py`. `conversation.py` re-imports these names as aliases → deployed agent byte-for-byte unchanged.
2. `orders.py`: formatters imported from `restaurant.agent.replies`; `customer_info` import top-level; add `revision` counter (bump in add/remove/update/set_quantity_by_id/remove_by_id).
3. `customer_info.py`: inline `_DELIVERY_RE/_PICKUP_RE/_QTY_ITEM_RE`; replace `menu_item_hint_in_text` with `menu_provider.extract_dish_query` — all 3 lazy conversation imports severed.
4. `stt_noise.py`: absorb `looks_like_order_phrasing` (conversation) + `_QTY_WORDS`/`_extract_qty` (order_parse).
5. `phone_background.py` / `phone_echo.py`: remove `UserIntent` from signatures (plain flags / internal regex).
6. `menu_provider.py:136`: inline the availability-question regex privately.
7. `session_recorder.py`: `finalize(cart, *, preferred_language: str | None = None)`; old agent.py call site updated.
8. Delete `restaurant/fillers.py` + `tests/test_fillers.py` (restore path noted in PR doc).

### PR 060 — `pr_060_hybrid-agent-brain` (new brain, unwired; no deletions)
`restaurant/agent/core.py`, `prompt.py`, `worker.py` + the full new test suite (§5). Old agent still the deployed entrypoint.

### PR 061 — `pr_061_agent-cutover-and-teardown`
Root `agent.py` → shim; `llm_warmup.py` import re-pointed; **delete** `conversation.py`, `order_flow.py`, `order_parse.py`, `prompts.py`, `restaurant/engine/` + their tests; rewrite broken keeper tests (§5); e2e verification (§6); deploy in shadow mode (`CLOVER_SUBMIT_ORDERS=0`).

### PR 062 — `pr_062_package-reorg`
`git mv` into `channels/` and `analytics/`; mechanical import updates across restaurant/, tests, scripts. No logic changes.

## 4. Exact deletion & modification lists

**Deleted source:** `restaurant/conversation.py`, `restaurant/order_flow.py`, `restaurant/order_parse.py`, `restaurant/prompts.py`, `restaurant/fillers.py`, `restaurant/engine/` (all files + README); old body of root `agent.py` (file kept as shim).
**Deleted tests:** `test_engine.py`, `test_engine_renderer.py`, `test_engine_resolver.py`, `test_conversation.py`, `test_order_flow.py`, `test_order_parse.py`, `test_fillers.py`, `test_item_availability.py`.
**Modified:** `agent.py`, `orders.py`, `customer_info.py`, `stt_noise.py`, `phone_background.py`, `phone_echo.py`, `menu_provider.py`, `session_recorder.py`, `llm_warmup.py`.
**New:** `restaurant/agent/*` (7 files) + new tests.
**Untouched keepers:** `clover/*`, `tenants/*`, `menu.py`, `menu_browse.py`, `text_match.py`, `voice_stack.py`, `session_config.py`, `reservations.py`, `ambient_audio.py`, `call_control.py`, `turn_latency.py`, `analytics_store.py`, `web_sync.py`, `token_server.py`, `data/*`, `web/`, `admin/`, all of `scripts/`, `deploy/` (both systemd units unchanged).

## 5. Test plan

**New (tools are plain async methods on a session-less agent — no LLM needed):**
- `tests/test_agent_tools.py` — add happy path (resolved to_cart_dict, no LLM price); AMBIGUOUS → options + cart unchanged; NOT FOUND; unavailable; spice refusal → retry with spice_level succeeds; required-group ("Choose Curry") refusal; qty clamp; exact-set quantity; remove; contact rejects 9-digit / junk name, accepts 10 and 11-with-leading-1; order type / address validation.
- `tests/test_agent_gates.py` — `place_order_blockers` matrix (each precondition individually missing); **readback staleness**: mutate cart after `get_order_readback` → `confirm_readback` refused → re-readback → place OK; revision bumps on every mutation incl. web-RPC path.
- `tests/test_agent_replies.py` / `tests/test_agent_language.py` — ported cases from `test_conversation.py` / `test_language.py` for salvaged formatters + `detect_customer_language`.
- `tests/test_agent_place_order.py` — monkeypatched `submit_cart_to_clover`: to_thread path, shadow-mode gate, goodbye + hangup scheduling, sentinel return, Clover error → spoken failure (no false "order's in").
**Rewritten keepers:** `test_customer_info.py`, `test_text_match.py`, `test_stt_noise.py`, `test_phone_echo.py`, `test_phone_background.py`, `test_session_recorder.py`, `test_llm_warmup.py`, `test_orders.py`, `test_menu_match.py` (against `clover.match` directly), `test_menu_browse.py`, `test_language.py`.
**Untouched keepers:** `test_ambient_audio`, `test_call_control`, `test_clover_order_submit`, `test_menu_cache_load`, `test_voice_labels`, `test_speech_policy`, `test_session_config`.

## 6. End-to-end verification

1. `python -m pytest tests/ -q` green at each PR boundary.
2. `USE_CLOVER_MENU=1 CLOVER_SUBMIT_ORDERS=0 python agent.py console` — scripted call: ambiguous "fish" (must ask, not add) · spice refusal → answer · late add after readback (must force re-readback) · 9-digit phone (must re-ask) · "no allergies" · full readback → place → shadow log shows correct Clover payload.
3. `scripts/test_call.py` outbound SIP call against a deployed worker (phone channel: echo filter, greeting settle, hangup).
4. `curl :8001/menu` — token_server catalog unchanged.
5. Web channel: tap-to-add then voice checkout — revision gate forces fresh readback.
6. Rollout: pilot restaurant in shadow (`CLOVER_SUBMIT_ORDERS=0`), review N real recorded calls in admin analytics, then flip the env var. Rollback = `git revert` + `scripts/vps_deploy.sh` (env untouched).

---

## Part III — Resuming this work in a new session

- **Where you are:** check which PRs of 059–062 have merged (`git log --oneline`, `ls pr/`). Each PR has a doc `pr/pr_0NN_*.md` per `pr/pr_rules.md` (doc first, branch = doc name, Files Added/Modified/Deleted enumerated, never commit to main).
- **Run tests:** `python -m pytest tests/ -q` (pytest may need `pip install pytest` — not in pyproject deps).
- **Deployed reality:** VPS `89.117.18.192`, `/opt/livekit-sarvam/`, deploy `bash scripts/vps_deploy.sh`; systemd `restaurant-agent.service` runs `python agent.py start`. Phone `+15878175156` (Twilio → LiveKit SIP). Web `voice.bizbull.ai`, admin `admin.bizbull.ai`.
- **Do not** re-apply PR 030, re-wire `restaurant/engine/` (it's being deleted), or flip `CLOVER_SUBMIT_ORDERS=1` before reviewing shadow-mode calls.
- **Audit findings that motivated this** (from the 2026-07-10 session): engine drops adds during checkout phases; 10-digit-only phone loop; no retry ceiling/escalation anywhere; extraction guarantee only tested against FakeResolver; sync Clover submit blocks the event loop; success spoken even on Clover failure; readback rejection re-asks allergies; Hindi promised but unimplemented; extractor blind to cart. The new tool design addresses each (blockers, 11-digit strip, tool refusals with reasons, to_thread, failure path, revision-gated readback, LLM-native context).
