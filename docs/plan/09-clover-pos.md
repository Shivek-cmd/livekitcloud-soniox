# Clover POS Integration — Plan

> Status: **Planning** (no code yet).  
> Reference knowledge: [`../reference/clover-*.md`](../reference/README.md)  
> Last updated: 2026-06-27

## Goal

Connect **Sierra** (voice agent) to **Clover POS** so that:

1. **Menu** comes from the restaurant's live Clover inventory (not hardcoded `restaurant/menu.py`).
2. **Orders** placed on a phone or web call land in Clover — visible on Register, kitchen printer, Merchant Dashboard.
3. The foundation supports **multi-tenant SaaS** (many restaurants, each with own Clover merchant + phone number).

This is the product differentiator: voice without POS is a demo; voice **with** POS is sellable infrastructure.

---

## POS 101 — for newcomers

If you've never worked with restaurant POS, read this first. The architecture diagram below will
make more sense after this section.

### What is a POS?

**POS = Point of Sale** — the system a restaurant uses to run the business day-to-day:

- **Menu** — what they sell, prices, modifiers ("extra spicy", "no onion")
- **Orders** — what a customer ordered, pickup or delivery
- **Kitchen** — ticket printed so cooks know what to make
- **Payments** — card/cash at the counter (often separate from order-taking)
- **Reports** — sales, taxes, inventory

Examples: **Clover**, Toast, Square, Lightspeed. The restaurant already has one; they won't replace
it for Sierra. **Sierra plugs into what they already use.**

### Where does Clover sit?

Clover is the **restaurant's brain for orders and menu**:

```
                    CLOVER (restaurant's POS)
┌─────────────────────────────────────────────────────────┐
│  Merchant Dashboard (web)  — owner manages menu, reports │
│  Register app (iPad/device) — staff rings up orders      │
│  Kitchen printer            — cooks see tickets          │
│  Clover cloud               — syncs everything           │
└─────────────────────────────────────────────────────────┘
         ▲                              ▲
         │ staff taps items             │ our API writes orders
         │                              │
    Walk-in customer              SIERRA (phone/web AI)
```

When staff take an order on the Clover Register, it goes to the same cloud database as when **Sierra**
submits an order via API. The kitchen doesn't care who typed it — they see one ticket.

### Where does Sierra sit?

Sierra is **not** a POS. Sierra is the **front door** — the customer talks to it on the phone or web.
Sierra's job:

1. **Understand** what the customer wants (voice → text → AI)
2. **Look up** real menu items from Clover (prices, modifiers, availability)
3. **Build** a cart during the conversation
4. **Confirm** with the customer ("2 paneer tikka, medium spicy, delivery to…")
5. **Submit** the order into Clover so the restaurant's normal workflow takes over

```
  Customer                    SIERRA                      CLOVER
  ────────                    ──────                      ──────
  "I'd like                   hears Punjabi/English
   chole bhature               finds item in menu
   for delivery"        →      asks address, phone   →     creates order
                              confirms total               prints kitchen ticket
                              "Order confirmed!"           shows on Register
```

### Pickup vs delivery (in POS terms)

Both are the **same order** in Clover, with different **order types**:

| | Pickup | Delivery |
|---|---|---|
| Customer gets food | Comes to restaurant | Restaurant/driver brings to address |
| Clover needs | Name, phone, items | Name, phone, **address**, items |
| Order type | e.g. `Pick-up` | e.g. `Delivery` |
| Payment v1 | Pay when they arrive | Pay at door (cash/card) — **no phone payment yet** |

Delivery is harder for voice because the AI must capture an **address accurately** (street, city,
postal code) and read it back digit-by-digit / word-by-word. That's extra conversation design, not
extra Clover magic — Clover stores the address on the **customer** record.

### What we are NOT building (v1)

- **We are not replacing Clover Register** — staff still use Clover for walk-ins.
- **We are not processing cards on the phone yet** — no card numbers on the call (PCI complexity).
- **We are not building a delivery fleet app** — no driver GPS; the restaurant uses their own drivers
  or DoorDash-style integrations outside Sierra.

### The three layers (simple mental model)

```
┌─────────────────────────────────────────────────────────────┐
│  LAYER 1 — CHANNEL (how customer reaches us)                 │
│  Phone (Twilio) · Web (browser)                                │
└────────────────────────────┬────────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────┐
│  LAYER 2 — SIERRA (voice AI on our VPS)                      │
│  Listen · think · speak · cart · confirm                     │
└────────────────────────────┬────────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────┐
│  LAYER 3 — CLOVER (restaurant POS in the cloud)              │
│  Menu truth · order record · kitchen print · (payments later)│
└─────────────────────────────────────────────────────────────┘
```

When you sell to many restaurants (SaaS), **Layer 2** is shared code; **Layer 3** is a different
Clover account per restaurant (different menu, different OAuth tokens).

---

## v1 scope (locked for planning)

### In scope

| Area | v1 behaviour |
|---|---|
| Order type | **Pickup and delivery** — two Clover `orderType`s per tenant |
| Delivery | Collect + confirm **delivery address by voice**; link to Clover **customer** record |
| Locations | **Single Clover merchant** per tenant (one physical restaurant) |
| Order API | **Atomic orders** — checkout preview → create → print |
| Payment | **Deferred** — pay on call later; v1 orders are unpaid (pay at door / on pickup) |
| Menu | Read from Clover Inventory API; cached locally per tenant |
| Menu updates | Webhooks (`I`, `IG`, `IM`, `IC`) + TTL fallback refresh |
| Customer | Create or link by phone number before order submit |
| Kitchen | `print_event` after successful order create |
| Environment | **Sandbox first** → one **production pilot** (Bizbull or friendly restaurant) |
| Channels | Phone + web (same agent, same Clover path) |

---

## Menu lookup & latency (availability without slow API calls)

**No — Sierra does not call Clover on every item question or every turn.** That would add
~200–500ms+ per lookup and destroy the voice experience.

### Three-speed model

```
┌─────────────────────────────────────────────────────────────────┐
│  FAST (every turn) — local menu cache, no network               │
│  "Do you have paneer tikka?" → lookup in RAM/DB cache → instant │
│  available / hidden / 86'd flag from last sync                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ webhooks or TTL (background)
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  MEDIUM (background) — refresh cache from Clover                │
│  Item updated in Clover → webhook → update cache row            │
│  Or: every 15–30 min full/incremental sync if no webhook        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ once per order, when customer confirms
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  SLOW (once per order) — Clover checkout API                    │
│  atomic_order/checkouts → Clover validates ids + live availability│
│  If item 86'd since cache → error here → Sierra apologizes,     │
│  offers alternative (never charged wrong order)                 │
└─────────────────────────────────────────────────────────────────┘
```

### What happens when customer asks for an item

| Step | What runs | Latency |
|---|---|---|
| Customer: "paneer tikka hai?" | `check_menu_item` tool → **local cache** | ~1ms |
| Customer: "add 2 paneer tikka" | `add_to_order` → validate id + `available` in **cache** | ~1ms |
| Customer: "ok place it" | `get_order_summary` → **cache** | ~1ms |
| Customer: "yes" | **Clover checkout** then **create order** | ~300–800ms (one time) |

Voice loop (STT → LLM → TTS) stays on the same path as today. Clover API only at **submit time**.

### How cache stays fresh enough

| Mechanism | Purpose |
|---|---|
| **Load at call start** | Tenant menu already in memory for this restaurant (from DB cache) |
| **Clover webhooks** (`I`, `IG`, `IM`) | Item price change, item hidden, modifier update → patch cache within seconds |
| **TTL fallback** | e.g. re-sync every 15–30 min if webhook missed |
| **Checkout API** | Final truth before money/kitchen — catches stale cache edge case |

**Acceptable staleness:** if owner 86's an item on Register, webhook updates cache in ~seconds.
Worst case without webhook: item might be offered until next TTL or until checkout fails — then
Sierra says "sorry, that's not available anymore."

### What we store in menu cache (per item)

Enough to answer voice without Clover round-trip:

- Clover `item_id` (for order submit)
- `clover_name`, `price` (cents), category
- `available`, `hidden`, stock quantity (if `autoManage`)
- Modifier groups + modifier ids, min/max rules
- **`speak_as`** — Gurmukhi label for Soniox TTS (e.g. `ਛੋਲੇ ਭਟੂਰੇ`; Clover only has English name)
- **`aliases`** — Roman/Hindi STT match keys ("chhole bhature", "paneer tikka")

See [../reference/clover-inventory-menu.md](../reference/clover-inventory-menu.md#punjabi-tts--clover-name-vs-gurmukhi-speech-label) for why Roman Clover names must not be spoken by TTS.

Same pattern as today: `find_item()` in `menu.py` is instant — we replace the **source** of that
data with synced Clover cache, not the **lookup speed**.

### Large menus

Full menu may be 100+ items — we don't dump all into every LLM prompt. Tools search cache by name/
category (like `check_menu_item` today). Soniox STT `context` can include top item names for better
recognition — also from cache, loaded once per call.

### Latency budget (target)

| Segment | Target |
|---|---|
| STT + LLM + TTS (one turn) | Already tuned (~1–3s total) |
| Menu tool (cache hit) | < 50ms |
| Clover checkout + create (end of call) | < 1s acceptable — customer expects brief pause before "order confirmed" |

**We are explicitly designing for this.** Sandbox build uses the same cache architecture as production.

---

### Out of scope (explicit deferrals)

- Payment on call (Clover Ecommerce API, 3DS, Interac) — **later phase**
- Delivery driver dispatch / GPS tracking (Sierra only submits order to Clover)
- Minimum order / delivery zone validation (v1: simple address capture; rules can be added per tenant)
- Multi-location chains under one tenant account
- Sierra-initiated inventory changes (86 items from voice)
- Clover Dining (table/seating app)
- Refunds, voids, order edits after submit
- Clover App Market public listing (pilots use **private app** — see Decisions)
- Non-Clover POS (Toast, Square, etc.)

---

## Architecture (target)

```
┌──────────────── PHONE / WEB ────────────────────────────────────────┐
│  Caller → Twilio / Browser → LiveKit Cloud → Agent Worker (VPS)      │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    ▼               ▼               ▼
              Soniox STT      OpenAI LLM      Soniox TTS
                    │               │               │
                    └───────────────┼───────────────┘
                                    │
                    Agent tools (cart, menu lookup, place_order)
                                    │
                                    ▼
              ┌─────────────────────────────────────────┐
              │  POS layer (new) — per-tenant             │
              │  restaurant/clover/                       │
              │    client.py      — REST + auth           │
              │    menu_cache.py  — catalog + aliases     │
              │    orders.py      — atomic checkout/create│
              │    customers.py   — phone lookup/create   │
              └─────────────────────────────────────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    ▼                               ▼
            Tenant store (new)              Clover REST API
            (SQLite → Postgres)             apisandbox / api.clover.com
            OAuth tokens, mId,              Inventory + Orders + Print
            menu cache, config
                                    │
                                    ▼
              Clover merchant devices (Register, kitchen printer)
```

### Order state machine (Sierra-side)

Sierra must not tell the customer "order placed" until Clover returns an order id.

```
┌──────────┐   add items    ┌──────────┐   checkout API   ┌─────────────┐
│  DRAFT   │ ─────────────► │  CART    │ ───────────────► │  PREVIEWED  │
│ (session)│                │ (session)│                  │ (Clover $)  │
└──────────┘                └──────────┘                  └──────┬──────┘
                                                                   │ verbal "yes"
                                                                   ▼
┌──────────┐   print OK     ┌──────────┐   atomic create  ┌─────────────┐
│  DONE    │ ◄───────────── │ PRINTING │ ◄───────────────── │ SUBMITTING  │
└──────────┘                └──────────┘                    └─────────────┘
     ▲                            │
     │ print fail (order exists)  └── log + optional retry; still DONE for customer
     │
     └── FAILED ←── Clover 4xx/5xx / network — do NOT confirm; offer callback
```

Rules:

- **PREVIEWED** — totals spoken come **only** from `atomic_order/checkouts` response.
- **SUBMITTING** — re-validate item `available` / stock at this step (86'd mid-call).
- **Idempotency** — one submit per session; store `sierra_session_id` in order `note` to detect dupes.
- **Hang-up before verbal yes** — no submit.

---

## Multi-tenant model (v1 sketch)

Phase 8 starts with **one tenant** (Bizbull) but schema supports N.

| Field | Purpose |
|---|---|
| `tenant_id` | Internal UUID |
| `name` | Display name |
| `clover_merchant_id` | Clover `mId` |
| `clover_env` | `sandbox` \| `production` |
| `oauth_access_token` | Encrypted; short-lived |
| `oauth_refresh_token` | Encrypted |
| `oauth_expires_at` | Refresh before expiry |
| `order_type_pickup_id` | Clover order type for pickup |
| `order_type_delivery_id` | Clover order type for delivery |
| `phone_number` | Twilio → LiveKit routing |
| `menu_cache` | JSON blob or normalized tables |
| `menu_cache_updated_at` | Last full/delta sync |
| `voice_config` | Optional overrides (voice_stack seam) |
| `menu_aliases` | JSON: spoken name → Clover item id |

**Storage v1 recommendation:** SQLite file on VPS (`/opt/livekit-sarvam/data/tenants.db`) for pilot;
migrate to Postgres when second paying customer onboarded.

OAuth tokens **never** in shared `.env` — only in tenant store, encrypted at rest.

---

## Clover app strategy

### Sandbox (now)

- Use existing sandbox developer account + test merchant.
- **Test API token** for scripts and early dev (no OAuth loop needed).
- App permissions: Read inventory, Read/Write orders, Read/Write customers, Read merchant.
- Webhooks: point at VPS endpoint (Caddy route or ngrok during dev).

### Production pilots

- **Private app** per merchant or one private app with multi-merchant OAuth (recommended: **one Sierra app**, merchants install via private link).
- v2/OAuth expiring tokens; background job refreshes tokens per tenant.
- App approval required before production merchants — plan 2–4 weeks lead time for DevRel review.

### Permissions justification (for app submission)

| Permission | Justification |
|---|---|
| Read inventory | Display menu and prices to voice customers |
| Write orders | Submit phone/web orders to kitchen |
| Read orders | Confirm order placement and audit |
| Read/Write customers | Link repeat callers by phone |
| Read merchant | Order types, tax config, business hours |

---

## Proposed code layout (when we build)

No files created yet — this is the target structure:

```
restaurant/
  voice_stack.py          # existing
  menu.py                   # deprecated → fallback until Clover live
  orders.py                 # session cart → delegates to clover/orders.py
  clover/
    __init__.py
    client.py               # HTTP, auth, rate-limit backoff
    menu.py                 # fetch, cache, alias resolve
    orders.py               # checkout, create, print
    customers.py            # phone lookup/create
    models.py               # internal Order, LineItem, Modifier types
  tenants/
    store.py                # SQLite/Postgres CRUD
    config.py               # resolve tenant from phone number or room metadata

scripts/
  clover_sandbox_probe.py   # menu read + test order (Phase 8a)

webhooks/
  clover_webhook.py         # inventory events → invalidate menu cache
  (or route on token_server / new FastAPI app)
```

**Agent integration:** `agent.py` tools call `restaurant/clover/` and `restaurant/tenants/` — not raw HTTP in tool handlers.

---

## Phased delivery

### Phase 8a — Sandbox probe (no agent changes)

**PR:** `pr_003_clover-sandbox-probe`

- `scripts/clover_sandbox_probe.py` — env: `CLOVER_MID`, `CLOVER_API_TOKEN`, `CLOVER_BASE_URL`
- Prove: list items + modifiers, atomic checkout, atomic create
- Document sandbox ids in PR doc (not committed secrets)
- **Exit criteria:** test order visible in sandbox Merchant Dashboard

### Phase 8b — Menu cache + tenant store

**PR:** `pr_004_clover-menu-cache`

- SQLite tenant table (single Bizbull row for sandbox)
- Full menu sync → JSON cache
- Replace or augment agent menu tool to read cache (feature flag: `USE_CLOVER_MENU=1`)
- Static `menu.py` remains fallback if flag off
- **Exit criteria:** Sierra answers "what paneer dishes do you have?" from Clover cache

### Phase 8c — Order placement

**PR:** `pr_005_clover-place-order`

- Order state machine in agent session
- Tools: `preview_order`, `confirm_and_place_order`
- Customer create/link by phone
- `print_event` after create
- **Exit criteria:** end-to-end sandbox call → order in Clover + print attempted

### Phase 8d — Webhooks + availability

**PR:** `pr_006_clover-webhooks`

- HTTPS webhook receiver for inventory events
- Invalidate/update menu cache on `I`/`IG`/`IM`
- Re-check availability at checkout submit
- **Exit criteria:** hide 86'd item within one webhook latency window

### Phase 8e — Production pilot

**PR:** `pr_007_clover-production-pilot`

- OAuth onboarding flow for one real merchant (private app)
- Production base URL + token refresh job
- Bizbull (or pilot) on live Clover
- **Exit criteria:** real phone call → real kitchen ticket

### Phase 8f — Multi-tenant routing (SaaS)

**PR:** `pr_008_multi-tenant-routing`

- Map Twilio number → tenant
- Per-tenant OAuth, menu, voice config
- Admin script to onboard restaurant
- **Exit criteria:** two tenants, two numbers, isolated menus/orders

---

## Edge cases (production checklist)

| Scenario | v1 handling |
|---|---|
| STT mishears item | Fuzzy match + read-back confirmation; never guess UUID |
| Modifier min/max | Validate against modifier group rules before cart add |
| Item 86'd mid-call | Checkout step fails → offer alternative |
| Clover API 429 | Exponential backoff; apologize, retry once |
| Clover API down | Do not confirm; "team will call you back" + log alert |
| Duplicate submit | Session id in order `note`; reject second submit same session |
| Print fails | Order still valid; log + retry print; tell customer order number |
| Staff edits in Register | After submit, Clover wins |
| Wrong tax spoken | Only speak total from checkout API |
| Punjabi item name ≠ Clover name | `menu_aliases` per tenant + confirm back |
| Delivery address capture | Read back street + city + postal code; confirm before submit |
| Pickup ↔ delivery switch mid-call | Re-ask address or skip; re-run checkout with correct order type |

---

## Decisions needed (from you)

These stay **TBD** until you confirm; defaults shown in *italics*.

| # | Question | Options | *Default recommendation* |
|---|---|---|---|
| 1 | Pilot app type | Private app vs public App Market | *Private app for Bizbull pilot* |
| 2 | Order service location | Inside agent process vs separate FastAPI service | *Inside agent + shared `restaurant/clover/` lib; webhooks on token_server or small sidecar* |
| 3 | Tenant DB v1 | SQLite file vs Postgres immediately | *SQLite for pilot; Postgres before customer #2* |
| 4 | Menu aliases | Config file vs admin UI vs LLM-only fuzzy match | *JSON aliases in tenant row for pilot; UI later* |
| 5 | Order metadata | Put `channel`, `room_id`, `session_id` in Clover order `note`? | *Yes — aids support/debugging* |
| 6 | Phase 6 vs 8 priority | Finish voice quality tuning before POS, or parallel | *Parallel 8a sandbox probe while Phase 6 continues* |

---

## Sandbox validation checklist (before PR 003)

Run manually with your sandbox credentials:

```bash
# 1. Menu read
GET /v3/merchants/{mId}/items?limit=100&expand=modifierGroups

# 2. Order type — create or note existing pick-up type id
POST /v3/merchants/{mId}/order_types

# 3. Checkout preview
POST /v3/merchants/{mId}/atomic_order/checkouts

# 4. Create order
POST /v3/merchants/{mId}/atomic_order/orders

# 5. Print (optional — needs device)
POST /v3/merchants/{mId}/print_event
```

Base URL: `https://apisandbox.dev.clover.com`

---

## Success metrics (pilot)

| Metric | Target |
|---|---|
| Order reaches Clover Register | 100% of confirmed calls |
| Kitchen print | >95% (when device online) |
| Wrong item rate | <5% (measured by staff corrections) |
| Checkout total matches receipt | 100% (Clover-calculated) |
| Menu stale after 86 | <2 minutes (with webhooks) |

---

## Related docs

- [01-overview.md](01-overview.md) — Sierra product + stack
- [02-architecture.md](02-architecture.md) — current voice architecture (will extend when built)
- [06-milestones.md](06-milestones.md) — phase tracker
- [../reference/clover-platform-overview.md](../reference/clover-platform-overview.md)
- [../reference/clover-oauth-and-api.md](../reference/clover-oauth-and-api.md)
- [../reference/clover-inventory-menu.md](../reference/clover-inventory-menu.md)
- [../reference/clover-orders-api.md](../reference/clover-orders-api.md)
- [../reference/clover-sierra-integration-notes.md](../reference/clover-sierra-integration-notes.md)

---

## Next step after this doc

1. **You confirm or override** the six decisions in the table above.
2. **Phase 8a** — create `pr/pr_003_clover-sandbox-probe.md` + branch + sandbox probe script.
3. Optionally run sandbox checklist with your credentials before opening the PR.
