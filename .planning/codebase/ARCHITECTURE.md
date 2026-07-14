<!-- refreshed: 2026-07-14 -->
# Architecture

**Analysis Date:** 2026-07-14

## System Overview

```text
┌─────────────────────────────────────────────────────────────┐
│                     User Input (Speech)                      │
│         Phone (SIP) or Web (Browser WebRTC)                 │
└─────────────────┬──────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────┐
│               LiveKit Audio Bridges                          │
│  `restaurant/channels/*.py` (echo, background, noise)       │
│  `restaurant/session_config.py` (VAD, endpointing)          │
└─────────────────┬──────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────┐
│            Speech-to-Text (STT) Pipeline                    │
│  Soniox STT (English/Punjabi/Hindi code-mixing)             │
│  VAD + Endpoint Detection + Noise Cancellation              │
│  `restaurant/voice_stack.py` (build_stt)                    │
└─────────────────┬──────────────────────────────────────────┘
                  │
                  ▼
┌──────────────────────────────────┬──────────────────────────┐
│  Turn Filtering & Hygiene        │  Core Agent Loop         │
│  `restaurant/agent/core.py`      │  `restaurant/agent/core.py`
│  on_user_turn_completed()        │  RestaurantAgent class   │
│  - Echo detection                │  - Tool definitions      │
│  - Background filtering          │  - Cart validation       │
│  - STT noise filtering           │  - Language tracking     │
└──────────────────────────────────┴──────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────┐
│              LLM Processing (OpenAI GPT)                     │
│  Structured tool calling with full chat context             │
│  Prompt built from session state + business rules           │
│  `restaurant/agent/prompt.py` (build_system_prompt)         │
│  `restaurant/agent/core.py` (@function_tool decorators)     │
└─────────────────────────────────────────────────────────────┘
                  │
                  ▼
┌──────────────────────────────────────────────────────────────┐
│            Tool Execution & Validation                       │
│                                                               │
│  Resolution Choke Point:                                     │
│  `_resolve_menu_item()` → all menu lookups go through here   │
│                                                               │
│  Item Tools (mutate OrderCart):                              │
│  - add_item() → menu_provider.find_item()                    │
│  - set_item_quantity()                                       │
│  - update_item_note()                                        │
│  - remove_item()                                             │
│                                                               │
│  Order Metadata Tools:                                       │
│  - set_order_type() (pickup/delivery)                        │
│  - set_delivery_address()                                    │
│  - set_customer_contact() (name + phone)                     │
│  - record_allergies()                                        │
│                                                               │
│  Readback & Checkout:                                        │
│  - get_order_readback() → gates.readback_blockers()          │
│  - place_order() → gates.place_order_blockers()              │
│                                                               │
│  Business Rules (Pure, Stateless):                           │
│  `restaurant/agent/gates.py`                                 │
│  - place_order_blockers() — gating logic                     │
│  - readback_blockers() — validation                          │
│  - OrderSessionState — per-session tracking                  │
└──────────────────────────────────────────────────────────────┘
                  │
                  ▼
┌──────────────────────────────────────────────────────────────┐
│            Menu & POS Integration                            │
│                                                               │
│  Menu Facade:                                                │
│  `restaurant/menu_provider.py` — abstraction layer           │
│  - find_item() — lookup with disambiguation                  │
│  - item_has_spice_level()                                    │
│  - required_modifier_groups()                                │
│                                                               │
│  Backend Options:                                            │
│  1. Static Menu: `restaurant/menu.py`                        │
│  2. Clover Cache: `restaurant/clover/menu.py`                │
│     (USE_CLOVER_MENU env toggles at runtime)                 │
│                                                               │
│  Clover Order Submission:                                    │
│  `restaurant/clover/order_submit.py`                         │
│  - submit_cart_to_clover()                                   │
│  - Order ID + ETA returned to cart                           │
└──────────────────────────────────────────────────────────────┘
                  │
                  ▼
┌──────────────────────────────────────────────────────────────┐
│            Response Generation & Audio                       │
│                                                               │
│  LLM Reply → Post-Processing:                                │
│  `restaurant/agent/replies.py`                               │
│  - sanitize_assistant_speech()                               │
│  - format_order_readback()                                   │
│  - format_order_status()                                     │
│  - order_placed_goodbye()                                    │
│                                                               │
│  Text-to-Speech:                                             │
│  Soniox TTS (same provider as STT, low latency)              │
│  `restaurant/voice_stack.py` (build_tts)                     │
│                                                               │
│  Ambient Audio (Phone Only):                                 │
│  `restaurant/channels/ambient_audio.py`                      │
│  Soothing background track, settable per tenant              │
└──────────────────────────────────────────────────────────────┘
                  │
                  ▼
┌──────────────────────────────────────────────────────────────┐
│            Synchronization & Analytics                       │
│                                                               │
│  Web Channel Only (RPC + State Sync):                        │
│  `restaurant/channels/web_sync.py`                           │
│  - register() — bind cart/checkout RPCs                      │
│  - publish_order_state() — push to browser                   │
│  - Web UI listens and updates cart in real-time              │
│                                                               │
│  All Sessions (Analytics Collection):                        │
│  `restaurant/analytics/session_recorder.py`                  │
│  - Collects STT transcripts, tool calls, latency             │
│  - Fires on session close + explicit flush                   │
│                                                               │
│  Turn Latency Tracking:                                      │
│  `restaurant/analytics/turn_latency.py`                      │
│  - Measures STT → LLM response time                          │
│  - Records per-turn metrics                                  │
│                                                               │
│  Persistence:                                                │
│  `restaurant/analytics/analytics_store.py`                   │
│  - persist_session() → Supabase storage                      │
└──────────────────────────────────────────────────────────────┘
```

## Component Responsibilities

| Component | Responsibility | File |
|-----------|----------------|------|
| **RestaurantAgent** | Main orchestrator; defines tools; tracks session state; owns cart mutation | `restaurant/agent/core.py` |
| **OrderCart** | Shopping cart data structure; subtotal/total computation; revision tracking | `restaurant/orders.py` |
| **OrderSessionState** | Per-session state: language, allergies, readback confirmation, user turn count | `restaurant/agent/gates.py` |
| **MenuProvider** | Menu lookup facade; abstraction over Clover or static menu | `restaurant/menu_provider.py` |
| **SessionRecorder** | Collects transcripts, tool calls, latency; finalizes + persists analytics | `restaurant/analytics/session_recorder.py` |
| **WebSync** | Web-channel RPC registration; pushes cart state to browser in real-time | `restaurant/channels/web_sync.py` |
| **EouWatchdog** | End-of-utterance detection watchdog; rescues stuck turns | `restaurant/channels/eou_watchdog.py` |
| **Gates (Business Rules)** | Pure validation logic; blocks order placement/readback; unmutable | `restaurant/agent/gates.py` |
| **Channel Filters** | Phone-only: echo, background, STT noise detection/recovery | `restaurant/channels/*.py` |

## Pattern Overview

**Overall:** Hybrid AI ordering system with LLM-driven conversation but code-owned cart.

**Key Characteristics:**
- **LLM drives conversation flow:** Full chat context, structured tool calling (GPT)
- **Code validates every mutation:** Cart only accepts validated menu items + business rules enforce gates
- **Multi-tenant ready:** Tenant config in `restaurant/tenants/config.py`; menu + audio vary per restaurant
- **Channel-aware:** Phone and web are first-class; different audio processing, different RPCs
- **Resilient to failures:** Ambient audio, echo/background recovery, end-of-speech watchdog, warm-up caching
- **Audit trail:** Every tool call logged; session analytics captured at close

## Layers

**LiveKit + Audio Bridge:**
- Purpose: Manage real-time bidirectional audio; connect to SIP gateways or WebRTC clients
- Location: `restaurant/session_config.py` (configuration); `restaurant/voice_stack.py` (STT/TTS setup)
- Contains: VAD configuration, noise cancellation plugin binding, endpoint sensitivity tuning
- Depends on: LiveKit Agents SDK, Soniox, Krisp noise cancellation plugins
- Used by: Worker entrypoint; all sessions

**Channel Hygiene Layer:**
- Purpose: Filter noisy/false transcripts before LLM sees them; phone-specific recovery
- Location: `restaurant/channels/` (echo, background, stt_noise, eou_watchdog, call_control)
- Contains: Echo detection heuristics, background chatter filters, STT artifact detection
- Depends on: User transcript, recent agent lines, channel (phone vs web)
- Used by: `RestaurantAgent.on_user_turn_completed()`

**LLM + Conversation Management:**
- Purpose: Maintain chat context; call tools in response to user intent
- Location: `restaurant/agent/core.py` (RestaurantAgent class); `restaurant/agent/prompt.py` (system prompt)
- Contains: Tool definitions, turn hooks, language detection, echo reprompt scheduling
- Depends on: LiveKit AgentSession, OpenAI GPT SDK, livekit.agents.function_tool
- Used by: Worker entrypoint; every user turn

**Tool Execution & Validation:**
- Purpose: Mutate cart, orders, metadata; refuse invalid operations
- Location: `restaurant/agent/core.py` (tool implementations); `restaurant/agent/gates.py` (rules)
- Contains: add_item, set_item_quantity, remove_item, set_order_type, set_customer_contact, place_order
- Depends on: OrderCart, OrderSessionState, MenuProvider, CloverOrderSubmit
- Used by: LLM (via function_tool mechanism); Web sync (RPC handlers)

**Menu & POS:**
- Purpose: Resolve dish names to menu payloads; submit orders to Clover POS
- Location: `restaurant/menu_provider.py` (facade); `restaurant/clover/order_submit.py` (submission)
- Contains: Menu matching logic, modifier resolution, Clover API client, order status tracking
- Depends on: Static menu.py or Clover cache (MenuCache); Clover REST API
- Used by: Tool execution (_resolve_menu_item); place_order tool

**Analytics & Recording:**
- Purpose: Capture session lifecycle; log tool usage; measure latency; persist to database
- Location: `restaurant/analytics/session_recorder.py` (turn-by-turn); `restaurant/analytics/analytics_store.py` (persistence)
- Contains: Turn begin/end, transcript logging, tool logging, cart snapshots, latency attachment
- Depends on: Supabase client, persistent file storage (local during call, flushed to DB)
- Used by: Worker entrypoint (session attach); turn hook (completion logging)

## Data Flow

### Primary Request Path (User Turn)

1. **Inbound Audio** (`restaurant/agent/worker.py:entrypoint`)
   - LiveKit delivers raw audio to Soniox STT stream
   - VAD + endpoint detection (Silero VAD, sensitivity configurable)

2. **Transcript Ready** (agent session event: `user_input_transcribed`)
   - Worker logs: `recorder.begin_user_turn(transcript, language)`
   - RestaurantAgent receives transcript + language hints

3. **Turn Hygiene** (`restaurant/agent/core.py:on_user_turn_completed`)
   - Check: is_likely_phone_echo() → StopResponse (no LLM)
   - Check: is_likely_background_speech() → StopResponse (no LLM)
   - Check: is_likely_stt_noise() → StopResponse + reprompt
   - Update preferred language from transcript content
   - Increment real_user_turns counter

4. **LLM Processing** (agent.on_message → GPT)
   - Session feeds transcript + chat history to LLM
   - LLM sees tool schemas for: add_item, set_order_type, get_order_readback, place_order, etc.
   - LLM may call 0 or more tools in the same turn

5. **Tool Execution** (`restaurant/agent/core.py` tool implementations)
   - **add_item:** _resolve_menu_item() → OrderCart.add_item() (if valid)
   - **set_order_type:** Validate pickup/delivery → cart.order_type = value
   - **get_order_readback:** Check gates.readback_blockers() → format response
   - **place_order:** Check gates.place_order_blockers() → submit_cart_to_clover() → Order ID
   - Each tool invalidates_readback() on cart change
   - Each tool calls _sync_web() (no-op on phone)

6. **Response Generation** (LLM response text)
   - RestaurantAgent.on_message fires conversation_item_added event
   - Worker captures: sanitize_assistant_speech() → recorder.append_sierra()
   - Text sent to Soniox TTS for speech synthesis
   - Session plays audio back to caller (allow_interruptions flag per context)

7. **Turn Completion** (`restaurant/analytics/session_recorder.py:complete_turn`)
   - Snapshot cart state + metadata
   - Log to local analytics file
   - Turn latency tracker measures time STT → LLM response

### Web Channel Variant

On non-phone sessions:
- After session start, WebSync registers RPC handlers (cart read, item add/remove/qty)
- LLM can still call tools normally (same code path)
- **Also:** Web RPCs bypass LLM and call tools directly (synchronous, validated)
- After any cart mutation (LLM tool OR web RPC), WebSync.publish_order_state() pushes JSON to browser
- Browser UI updates cart display, item counts, total in real-time

### Session Lifecycle Hook

```
entrypoint() called
  → connect() to LiveKit room
  → wait for participant
  → detect channel (phone vs web)
  → start SessionRecorder
  → build_agent_session (VAD + TurnDetector)
  → attach TurnLatencyTracker, EouWatchdog
  → create RestaurantAgent instance
  → schedule llm_warmup (prime GPT prompt cache)
  → session.on("close") → flush_analytics
  → session.on("user_input_transcribed") → recorder.begin_user_turn
  → session.on("conversation_item_added") → recorder.append_sierra
  → session.say(OPENING_GREETING)
  → [if phone] sleep(settle_seconds), check echo, reprompt
  → [if web] WebSync.register() + publish_order_state()
  → session.start() ← blocks until session closes
  → flush_analytics() + cleanup
```

**State Management:**
- **OrderCart:** Mutated by tools; revision auto-increments on every change; passed to readback/place gates
- **OrderSessionState:** Tracks: language, allergies_recorded, readback_revision/confirmed, real_user_turns
- **SessionRecorder:** Accumulates transcript + tool calls in-memory; written to file on turn boundaries; flushed to DB on close
- **Recent agent lines:** Sliding 6-line buffer used for echo detection (tools may re-speak recent agent output)

## Key Abstractions

**MenuProvider Facade:**
- Purpose: Decouple agent logic from menu source (Clover vs static)
- Examples: `find_item(query)`, `disambiguation_options(query)`, `item_has_spice_level(item_name)`
- Pattern: USE_CLOVER_MENU env var toggles at startup; caches Clover MenuCache object or falls back to static `restaurant/menu.py`
- Implementation: `restaurant/menu_provider.py` — routes calls to Clover or static menu based on availability

**OrderCart:**
- Purpose: Single source of truth for order state; revision-gated readbacks
- Examples: `add_item(item_dict, qty, note)`, `remove_item(name)`, `to_state_dict()`
- Pattern: Revision counter increments on every mutation (not just quantity changes); tools invalidate readback on change; gates check readback.revision == cart.revision
- Implementation: `restaurant/orders.py` dataclass with computed properties (is_empty, subtotal, total)

**Gates (Pure Business Logic):**
- Purpose: Unmutable, testable validation logic — LLM cannot bypass
- Examples: `place_order_blockers(cart, state)` → list[str] of reasons, or [] if OK to place
- Pattern: Gates return reason strings (not booleans) so LLM is told exactly what to do next
- Implementation: `restaurant/agent/gates.py` — pure functions, no I/O

**SessionRecorder:**
- Purpose: Audit trail — every transcript, tool call, latency measurement captured
- Examples: `begin_user_turn(text)`, `append_sierra(agent_reply)`, `log_tool(name, args, result)`, `finalize(cart, lang)`
- Pattern: Stateful object accumulating per-session data; written to local file during call; persisted to DB at close
- Implementation: `restaurant/analytics/session_recorder.py` — manages session_id, room_name, recordings dict

## Entry Points

**Worker Entrypoint:**
- Location: `restaurant/agent/worker.py:entrypoint(ctx: JobContext)`
- Triggers: Called by LiveKit SDK when a job is assigned (SIP call or web session)
- Responsibilities:
  1. Connect to LiveKit room
  2. Wait for participant (caller)
  3. Detect channel (SIP prefix or attribute check)
  4. Create RecorderSession + RestaurantAgent
  5. Bind plumbing (session, recorder, job context)
  6. Attach event listeners (transcript, agent speech, close)
  7. Start session + await until close
  8. Flush analytics + shutdown

**CLI Entry:**
- Location: `agent.py` (root) + `restaurant/agent/worker.py:run()`
- Triggers: `python agent.py start` (systemd service)
- Responsibilities: Parse env, call `cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, ...))`, block until shutdown

**Web Sync RPCs (Web Channel Only):**
- Location: `restaurant/channels/web_sync.py:register()`
- Triggers: Browser calls HTTP POST to agent with cart mutations (fetch API)
- Responsibilities: Validate request, call tool (add_item, set_qty, remove_item), return updated cart JSON

## Architectural Constraints

- **Single-threaded event loop:** All async code runs in one Python asyncio loop per session; no worker threads except noise-cancellation plugin
- **Global state (module-level):** 
  - `restaurant/menu_provider.py:_cache` — Clover MenuCache, lazily loaded once per agent startup
  - `restaurant/tenants/config.py` — default tenant config, singleton pattern
- **Circular imports:** None known; clear module layering (agent depends on orders/gates/channels; channels don't depend back)
- **No persistence within agent:** OrderCart is in-memory only; persistence happens via analytics_store.persist_session() to Supabase
- **Synchronous menu lookups:** _resolve_menu_item() is sync (menu.py is pure, Clover cache is pre-loaded); blocks briefly during add_item
- **STT/TTS are async:** Soniox STT streams live; TTS queued to live audio buffer (no waiting for full synthesis before playback)

## Anti-Patterns

### LLM Inventing Menu Items

**What happens:** Old code had LLM insert freeform item names into cart; prices/IDs missing → Clover submission fails

**Why it's wrong:** Clover API enforces item IDs + price match; human fallout when order shows wrong item/price; audit trail breaks

**Do this instead:** All add_item calls go through _resolve_menu_item() choke point. LLM never writes cart directly. If not found, LLM is told exactly why (AMBIGUOUS or NOT FOUND) with options for next step. See `restaurant/agent/core.py:_resolve_menu_item()` and `restaurant/agent/core.py:add_item()` lines 292–334.

### Readback Confirmation Drift

**What happens:** LLM reads back old cart, customer says "yes", but LLM changed cart in between (quantitative change). Order placed with wrong content.

**Why it's wrong:** Customer confirmed different items than what gets placed; money path guarantee violated; audit/billing disputes

**Do this instead:** OrderSessionState tracks readback_revision (cart.revision when readback was generated). place_order_blockers() refuses unless readback_revision == cart.revision. Any tool call invalidates_readback() immediately. See `restaurant/agent/gates.py` and `restaurant/agent/core.py` lines 420, 449.

### Blocking on Channel Detection

**What happens:** Old code guessed channel from participant attributes late in the flow; greeting already sent; audio tuning wrong for actual channel type

**Why it's wrong:** Wrong VAD settings, wrong ambient audio, wrong greeting echo recovery timing

**Do this instead:** Channel detection happens first thing in entrypoint (phone vs web check). Session config, recorder, and agent are all built with is_phone=True/False. All downstream code branches on self.is_phone, not detecting at call time. See `restaurant/agent/worker.py` lines 56–66.

## Error Handling

**Strategy:** Defensive; fail-safe to human-readable error messages; retry gracefully for transient failures.

**Patterns:**

- **Menu resolution:** If not found, don't guess; tell LLM exactly what to do next (ask customer, call search_menu, or try again)
- **Order gates:** Tool returns text reason; LLM is guided on next step; no exceptions leaked to LLM
- **Clover submission:** CloverOrderSubmitError caught; order is NOT marked placed; session continues (LLM can retry or apologize)
- **Analytics flush:** try/except wrapper; logs exception but doesn't crash session (best-effort persistence)
- **Web RPC errors:** Return 400 + error detail; client retries or shows user message

## Cross-Cutting Concerns

**Logging:** 
- `logging.basicConfig` sets INFO level + timestamp format in `restaurant/agent/worker.py:main`
- Each module has `logger = logging.getLogger(__name__)` for filtering by source
- Keys: room_name, session_id, channel, participant_identity logged early in session
- Tool calls logged via `_record_tool(name, args, result)`

**Validation:**
- Menu items: _resolve_menu_item() → match confidence + disambiguation check
- Customer info: `restaurant/customer_info.py:is_valid_customer_name()` + extract_phone_digits()
- Spice levels: _canonical_spice() maps free-form input to 4 official levels
- Order gates: place_order_blockers() enforces completeness before placement

**Authentication:**
- No per-caller auth; LiveKit room isolation provides multi-session safety
- Tenant is sourced from config (env default), not from caller attributes
- Clover API auth via env-var API key (clover/client.py)

---

*Architecture analysis: 2026-07-14*
