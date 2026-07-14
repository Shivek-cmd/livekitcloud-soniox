# Codebase Structure

**Analysis Date:** 2026-07-14

## Directory Layout

```
.
├── agent.py                          # Root CLI entry (thin shim over worker.py)
├── token_server.py                   # Standalone token server (for local dev)
├── pyproject.toml                    # Python project manifest + dependencies
├── uv.lock                           # Locked dependency versions (uv package manager)
│
├── restaurant/                       # Main backend package
│   ├── __init__.py
│   ├── voice_stack.py               # LLM (OpenAI) + STT (Soniox) + TTS (Soniox) factories
│   ├── session_config.py            # Session tuning (VAD, turn detection, latency, noise cancellation)
│   ├── menu.py                      # Static menu definition (fallback when not using Clover)
│   ├── menu_provider.py             # Menu facade (routes to Clover or static)
│   ├── menu_browse.py               # Menu search/disambiguation logic
│   ├── orders.py                    # OrderCart + CartItem dataclasses
│   ├── customer_info.py             # Phone validation, name parsing, formatting
│   ├── text_match.py                # Regex patterns for text matching (Indic + English)
│   ├── reservations.py              # Reservation lookup (minimal, rarely used)
│   ├── llm_warmup.py                # GPT prompt cache warming (reduce cold latency)
│   │
│   ├── agent/                       # Core agent logic
│   │   ├── core.py                  # RestaurantAgent class + tool definitions (40KB)
│   │   ├── worker.py                # LiveKit entrypoint + session lifecycle
│   │   ├── gates.py                 # Pure business logic gates + OrderSessionState
│   │   ├── prompt.py                # LLM system prompt construction
│   │   ├── replies.py               # Response formatting (readback, status, goodbye)
│   │   └── language.py              # Language detection + greeting selection
│   │
│   ├── channels/                    # Channel-specific processing (phone vs web + filters)
│   │   ├── eou_watchdog.py          # End-of-utterance watchdog (rescues stuck turns)
│   │   ├── call_control.py          # Phone hangup scheduling + call status
│   │   ├── phone_echo.py            # Echo detection heuristics
│   │   ├── phone_background.py      # Background chatter detection + filtering
│   │   ├── stt_noise.py             # STT artifact detection (gibberish, false positives)
│   │   ├── ambient_audio.py         # Phone background music/ambience playback
│   │   └── web_sync.py              # Web channel RPC handlers + order state sync
│   │
│   ├── clover/                      # Clover POS integration
│   │   ├── client.py                # REST API client (low-level HTTP)
│   │   ├── menu.py                  # MenuCache class (Clover menu loader + matcher)
│   │   ├── models.py                # Clover API response DTOs
│   │   ├── order_submit.py          # Order submission + modifier matching (11KB)
│   │   ├── speech_policy.py         # Voice label policies (speak-as aliases)
│   │   ├── voice_labels.py          # Per-item pronunciation rules
│   │   ├── match.py                 # Menu item matching logic
│   │   └── seed_menu.py             # Utility to sync Clover menu to file cache
│   │
│   ├── analytics/                   # Session analytics + recording
│   │   ├── session_recorder.py      # Turn-by-turn transcript + tool logging (10KB)
│   │   ├── analytics_store.py       # Persistence to Supabase
│   │   └── turn_latency.py          # STT → LLM response time measurement
│   │
│   └── tenants/                     # Multi-tenant support
│       ├── config.py                # Tenant config + cache paths
│       └── store.py                 # Tenant data access layer
│
├── web/                             # React web UI
│   ├── package.json                 # Node dependencies (React, LiveKit)
│   ├── src/
│   │   ├── main.tsx                 # Entry point
│   │   ├── App.tsx                  # Root component
│   │   ├── App.css                  # Styles
│   │   ├── components/              # UI components
│   │   │   ├── OrderPanel.tsx       # Cart display + checkout
│   │   │   ├── SierraPanel.tsx      # Agent speech display
│   │   │   ├── OrderWithSierra.tsx  # Layout container
│   │   │   ├── LiveMenu.tsx         # Interactive menu browse
│   │   │   └── StoreTab.tsx         # Store info panel
│   │   ├── hooks/
│   │   │   └── useCart.tsx          # Cart state hook (syncs with agent RPCs)
│   │   └── lib/
│   │       └── api.ts               # HTTP client for agent RPC calls
│   └── vite.config.ts               # Vite build config
│
├── admin/                           # Admin dashboard (React)
│   ├── package.json                 # Node dependencies
│   ├── src/
│   │   ├── main.tsx                 # Entry point
│   │   ├── App.tsx                  # Root component
│   │   ├── components/              # UI components
│   │   ├── lib/                     # API client + utilities
│   │   ├── pages/                   # Admin pages (reports, settings, etc.)
│   │   └── types.ts                 # TypeScript interfaces
│   └── vite.config.ts               # Vite build config
│
├── tests/                           # Python test suite (pytest)
│   ├── test_agent_*.py              # Agent logic tests (gates, tools, replies)
│   ├── test_customer_info.py        # Phone/name validation tests
│   ├── test_menu_*.py               # Menu matching + cache tests
│   ├── test_clover_*.py             # Clover integration tests
│   ├── test_voice_*.py              # Voice stack config tests
│   ├── test_eou_watchdog.py         # End-of-speech watchdog tests
│   ├── test_session_*.py            # Session config + recorder tests
│   └── test_turn_latency.py         # Latency tracking tests
│
├── deploy/                          # Deployment config
│   ├── restaurant-agent.service     # Systemd service definition
│   └── [other deployment files]
│
├── docs/                            # Documentation
│   └── [markdown guides, API specs, etc.]
│
├── supabase/                        # Supabase configuration + migrations
│   └── [DB schema, migrations, SQL functions]
│
├── data/                            # Static data files
│   └── [menu JSON, locale files, etc.]
│
├── pr/                              # PR branches + work-in-progress
│   └── [feature branches pulled into main]
│
├── scripts/                         # Build + deployment scripts
│   ├── setup_sip.py                 # SIP gateway configuration
│   └── [other utilities]
│
├── .claude/                         # Claude Code configuration
│   ├── settings.json                # Workspace settings
│   └── [skills/, memory/, etc.]
│
├── .gsd/                            # GSD framework state
│   └── [workflow tracking, phase records]
│
└── KMS/                             # KMS + secrets (local dev only)
    └── [credential files, dev secrets]
```

## Directory Purposes

**restaurant/:**
- **Purpose:** Main backend Python package; voice agent + order logic + integrations
- **Contains:** Agent, tools, menu lookups, Clover submission, analytics, multi-tenant config
- **Key files:** `agent/core.py` (agent class), `agent/worker.py` (entry point), `orders.py` (cart), `menu_provider.py` (facade)

**restaurant/agent/:**
- **Purpose:** Core AI conversational agent logic
- **Contains:** RestaurantAgent class, tool definitions, business rule gates, LLM prompt, response formatting
- **Key files:** `core.py` (40KB, largest file; RestaurantAgent + all tools), `gates.py` (validation rules), `prompt.py` (system message), `worker.py` (session lifecycle)

**restaurant/channels/:**
- **Purpose:** Channel-specific processing (phone vs web) + input filtering
- **Contains:** Echo/background/noise detection, phone-specific reprompts, web RPC handlers, ambient audio
- **Key files:** `eou_watchdog.py` (end-of-speech rescue), `web_sync.py` (web cart sync), `phone_echo.py` (echo detection)

**restaurant/clover/:**
- **Purpose:** POS integration (Clover Square)
- **Contains:** REST API client, menu cache loader, order submission + modifier matching, voice labels
- **Key files:** `order_submit.py` (11KB, complex order → POS mapping), `menu.py` (MenuCache loader), `client.py` (HTTP client)

**restaurant/analytics/:**
- **Purpose:** Session recording + analytics persistence
- **Contains:** Turn-by-turn transcript logging, tool call recording, latency measurement, Supabase flush
- **Key files:** `session_recorder.py` (10KB, core analytics state), `analytics_store.py` (DB persistence), `turn_latency.py` (timing)

**restaurant/tenants/:**
- **Purpose:** Multi-tenant configuration + data access
- **Contains:** Tenant settings, cache paths, voice labels per tenant, restaurant info
- **Key files:** `config.py` (TenantConfig class), `store.py` (data access methods)

**web/:**
- **Purpose:** React customer-facing web UI for web-channel calls
- **Contains:** Cart display, order management, agent speech display, menu browse, checkout
- **Entry point:** `web/src/main.tsx` (mounted to DOM)

**admin/:**
- **Purpose:** Admin dashboard for restaurant operators
- **Contains:** Order history, settings, reports, menu management
- **Entry point:** `admin/src/main.tsx` (mounted to DOM)

**tests/:**
- **Purpose:** Test suite (pytest)
- **Contains:** Unit + integration tests for agent logic, menu, customer info, Clover, session lifecycle
- **Naming:** `test_<module>.py` (mirrors source module names)

**deploy/:**
- **Purpose:** Production deployment artifacts
- **Contains:** Systemd service definition, Docker config, environment templates
- **Key files:** `restaurant-agent.service` (systemd unit)

**docs/:**
- **Purpose:** Project documentation
- **Contains:** API specs, architecture notes, setup guides, troubleshooting
- **Notable files:** (see repo markdown files: refactor.md, turnwatchdog.md, etc.)

**supabase/:**
- **Purpose:** Database schema + migrations
- **Contains:** Tables, indexes, RLS policies, SQL functions for analytics storage
- **Entry point:** Migrations run during deployment

**scripts/:**
- **Purpose:** Build + operational scripts
- **Key files:** `setup_sip.py` (SIP gateway configuration dispatch)

## Key File Locations

**Entry Points:**
- `agent.py` — Root CLI entry point (systemd runs `python agent.py start`)
- `restaurant/agent/worker.py:entrypoint()` — LiveKit job handler
- `restaurant/agent/worker.py:run()` — CLI runner
- `web/src/main.tsx` — Web UI entry
- `admin/src/main.tsx` — Admin UI entry

**Configuration:**
- `restaurant/session_config.py` — Audio pipeline config (VAD, turn detection, noise cancellation)
- `restaurant/voice_stack.py` — LLM/STT/TTS provider setup (OpenAI, Soniox)
- `restaurant/tenants/config.py` — Multi-tenant settings
- `pyproject.toml` — Python dependencies
- `web/package.json`, `admin/package.json` — Node dependencies

**Core Logic:**
- `restaurant/agent/core.py` — RestaurantAgent + tool implementations
- `restaurant/agent/gates.py` — Business rule validation (order gates)
- `restaurant/orders.py` — OrderCart + CartItem
- `restaurant/menu_provider.py` — Menu facade (Clover or static)
- `restaurant/clover/order_submit.py` — Order submission to POS

**Request/Response Processing:**
- `restaurant/agent/prompt.py` — LLM system message construction
- `restaurant/agent/replies.py` — Response formatting (readback, status, goodbye)
- `restaurant/channels/web_sync.py` — Web cart RPC handlers

**Analytics & Monitoring:**
- `restaurant/analytics/session_recorder.py` — Session transcript + tool logging
- `restaurant/analytics/analytics_store.py` — Persistence to Supabase
- `restaurant/analytics/turn_latency.py` — Latency measurement

**Phone Channel Specific:**
- `restaurant/channels/eou_watchdog.py` — End-of-utterance watchdog
- `restaurant/channels/phone_echo.py` — Echo detection
- `restaurant/channels/phone_background.py` — Background chatter filter
- `restaurant/channels/stt_noise.py` — STT artifact detection
- `restaurant/channels/ambient_audio.py` — Ambient music/ambience

**Testing:**
- `tests/test_agent_gates.py` — Business logic validation tests
- `tests/test_agent_tools.py` — Tool execution tests
- `tests/test_clover_order_submit.py` — Order submission tests
- `tests/test_menu_*.py` — Menu matching + cache tests

## Naming Conventions

**Files:**

- **Python modules:** `snake_case.py` (e.g., `menu_provider.py`, `session_config.py`)
- **Test files:** `test_<module>.py` (e.g., `test_agent_core.py` matches `agent/core.py`)
- **Classes:** `PascalCase` (e.g., `RestaurantAgent`, `OrderCart`, `SessionRecorder`)
- **Functions/methods:** `snake_case` (e.g., `add_item()`, `_resolve_menu_item()`)
- **Constants:** `UPPER_SNAKE_CASE` (e.g., `DELIVERY_CHARGE`, `MAX_ITEM_QTY`)
- **Private methods:** Leading underscore `_snake_case()` (e.g., `_resolve_menu_item()`)

**Directories:**

- **Package dirs:** `snake_case/` (e.g., `restaurant/`, `agent/`, `channels/`, `analytics/`)
- **Feature dirs:** Descriptive name matching component (e.g., `clover/` for POS, `channels/` for input processing)

**TypeScript/React:**

- **Components:** `PascalCase.tsx` (e.g., `OrderPanel.tsx`, `SierraPanel.tsx`)
- **Hooks:** `use<Name>.tsx` (e.g., `useCart.tsx`)
- **Utils:** `snake_case.ts` (e.g., `api.ts`)
- **Interfaces:** `PascalCase` (e.g., `OrderState`, `CartItem`)

## Where to Add New Code

**New Feature / Business Logic:**

1. **Conversation flow change (what LLM should say):**
   - Modify `restaurant/agent/prompt.py` (system message)
   - Add tool if needed (modify `restaurant/agent/core.py` class)
   - Update tests in `tests/test_agent_tools.py` or new test file

2. **Order validation / gate (when order can proceed):**
   - Edit `restaurant/agent/gates.py` (add rule to place_order_blockers or readback_blockers)
   - Tool implementation checks gate → returns reason string
   - Add tests in `tests/test_agent_gates.py`

3. **Menu lookup / matching:**
   - Change: `restaurant/menu_provider.py` (facade logic)
   - Or: `restaurant/clover/match.py` (Clover-specific matching)
   - Or: `restaurant/menu_browse.py` (search logic)
   - Tests: `tests/test_menu_*.py`

4. **Customer info validation (phone, name, address):**
   - Edit: `restaurant/customer_info.py`
   - Tests: `tests/test_customer_info.py`

5. **Session state / tracking:**
   - Modify: `restaurant/agent/gates.py` (OrderSessionState dataclass)
   - Modify: `restaurant/analytics/session_recorder.py` (if analytics needed)
   - Tests: `tests/test_agent_gates.py` or `tests/test_session_recorder.py`

**New Channel / Input Filter:**

1. Create file: `restaurant/channels/<name>.py`
2. Hook in: `restaurant/agent/core.py:on_user_turn_completed()` (add check, raise StopResponse if blocked)
3. Tests: `tests/test_<name>.py`

**New POS Integration (beyond Clover):**

1. Create directory: `restaurant/<pos_name>/` (parallel to `clover/`)
2. Implement: client, menu cache, order submission
3. Update `restaurant/menu_provider.py` to route based on env var
4. Update `restaurant/orders.py` if cart schema changes needed

**New Web RPC:**

1. Add handler in: `restaurant/channels/web_sync.py:register()` (session.on("rpc_call", ...))
2. Handler validates, calls tool (or direct method), returns JSON response
3. Tests: `tests/test_web_sync.py` (if not exists, create it)

**New Reporting / Analytics View:**

1. Add column/table to: `supabase/migrations/` (SQL schema)
2. Write persistence code: `restaurant/analytics/analytics_store.py`
3. Session recorder collects data: `restaurant/analytics/session_recorder.py` (finalize payload)
4. Tests: `tests/test_session_recorder.py`

**Web UI Enhancement:**

1. **New component:** Create `web/src/components/<Name>.tsx`
2. **Hook state:** Extend `web/src/hooks/useCart.tsx` if needed
3. **API call:** Add method in `web/src/lib/api.ts`
4. **Integration:** Import + use in `web/src/App.tsx` or parent component

**Admin UI Enhancement:**

1. **New page:** Create `admin/src/pages/<page_name>.tsx`
2. **Add link:** Update `admin/src/App.tsx` router
3. **API client:** Use/extend `admin/src/lib/api.ts`

## Special Directories

**restaurant/tenants/:**
- **Purpose:** Multi-tenant configuration + data access
- **Generated:** No (config files are checked in)
- **Committed:** Yes (tenant config is source control)
- **Usage:** Access via `get_default_tenant()` or `get_tenant(name)` to look up restaurant name, Clover credentials, cache path, voice labels, ambient audio settings

**.gsd/:**
- **Purpose:** GSD framework state (workflow tracking, phase records)
- **Generated:** Yes (GSD commands create/update)
- **Committed:** Yes (state tracked in git for continuity)
- **Usage:** Read-only for developers; GSD agent updates during work

**.claude/:**
- **Purpose:** Claude Code workspace config (skills, memory, settings)
- **Generated:** Partially (memory created by Claude, settings by user)
- **Committed:** Yes (skills and settings checked in)
- **Usage:** Customizations for this project (Claude Code shortcuts, local settings)

**tests/:**
- **Naming:** `test_<module>.py` mirrors `restaurant/<module>.py`
- **Organization:** One file per source module or feature area
- **Fixtures:** Inline in test files (not a separate fixtures/ dir)
- **Run:** `pytest tests/` or `pytest tests/test_<name>.py`

**.env:**
- **Purpose:** Local development environment variables (NOT committed)
- **Contains:** LiveKit URL, Clover API keys, Soniox keys, Supabase URL (see `.env.example`)
- **Never committed:** .gitignore excludes `.env*`

---

*Structure analysis: 2026-07-14*
