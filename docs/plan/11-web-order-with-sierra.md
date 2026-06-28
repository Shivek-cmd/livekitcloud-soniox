# Web App Plan — "Order with Sierra" (production)

> **Status:** Planning (no code yet). v1 — 2026-06-28. Key decisions **locked** (see §7).
> **Goal:** Turn the web app into a production-grade ordering experience where a customer
> places a real order by *talking to Sierra* while *watching her (avatar)*, *seeing the live
> menu*, and *watching their order build in real time*. Quality bar: it should feel like two
> humans talking — one human (the customer) on the internet placing an order, the other (Sierra)
> our AI taking it.

---

## 1. Product shape

The web app has **two tabs** (tab switcher at the top):

| Tab | Scope | Priority |
|-----|-------|----------|
| **Order with Sierra** | Live voice ordering with avatar + live menu + live order screen | **Build first** |
| **Store** | Browse/scroll menu, add to cart manually, classic e-commerce checkout | After "Order with Sierra" |

This doc covers **Order with Sierra** only. Store gets its own plan doc later.

### "Order with Sierra" screen — three live panels

```
┌─────────────────────────────────────────────────────────────┐
│  [ Order with Sierra ]   [ Store ]            (tab switcher)  │
├───────────────┬───────────────────────────┬─────────────────┤
│               │                           │                 │
│   1. AVATAR   │     2. LIVE MENU          │  3. LIVE ORDER  │
│   (Sierra     │     (browsable catalog,   │  (cart builds   │
│    speaking,  │      highlights the item  │   in real time  │
│    captions,  │      Sierra is talking    │   as Sierra     │
│    state)     │      about right now)     │   adds items)   │
│               │                           │                 │
│  [ Start Call ] / [ Mute ] / [ End ]      │  Subtotal/Total │
└───────────────┴───────────────────────────┴─────────────────┘
```

1. **Avatar speaking** — a video avatar of Sierra, lip-synced to her TTS, with a live caption
   line and a state indicator (listening / thinking / speaking).
2. **Live menu** — the full Clover catalog (categories, items, **prices**, veg/non-veg). The item(s)
   Sierra is currently discussing get **highlighted / scrolled into view** in real time. Each item
   also has an **"Add" control** (hybrid ordering — see below).
3. **Real-time order screen** — the cart/order updates instantly as Sierra adds/removes items,
   sets pickup/delivery, collects name/phone, and reaches the final total + checkout.

**Interaction model = HYBRID (locked):** the customer can order **by voice *and* by tapping the
menu**. Both paths converge on the same server-side `OrderCart` (single source of truth). A tap is
a *request* sent to the agent (RPC), the agent updates the cart and (optionally) acknowledges
verbally, then the pushed `order.state` reconciles every panel. No optimistic client-only cart.

---

## 2. Where we are today (baseline)

| Piece | Current state |
|-------|---------------|
| Frontend | React + Vite SPA, **single "Start Call" button**, audio only (`web/src/App.tsx`) |
| Token/dispatch | `token_server.py` → `/token` returns LiveKit token + dispatches `restaurant-agent` |
| Agent | Server-side on VPS, connects to LiveKit Cloud; `RestaurantAgent` in `agent.py` |
| Order state | In-memory `OrderCart` (`restaurant/orders.py`) mutated by function tools |
| Menu | Clover cache (`data/menu_cache_bizbull.json`, 61 items) via `menu_provider` |
| Avatar | **None** |
| UI state sync | **None** — agent sends *audio only*; the browser never sees cart/menu state |

**The core gap:** every panel except audio needs a new **agent → browser data channel**. The
agent already *has* all the state (cart, which item it's discussing); we just never push it to the UI.

---

## 3. Target architecture

```
Browser (React)                         LiveKit Cloud room                 VPS
┌────────────────────┐   WebRTC audio   ┌───────────────────┐   audio   ┌──────────────────┐
│ mic ───────────────┼─────────────────►│                   │◄──────────┤ RestaurantAgent  │
│ avatar <video>  ◄──┼──────────────────┤  participants:    │  (Soniox  │  (AgentSession)  │
│ captions  ◄────────┼── text streams ──┤   - customer      │   TTS)    │  OrderCart       │
│ order panel ◄──────┼── RPC / data ────┤   - agent         │           │  menu_provider   │
│ menu highlight ◄───┼── RPC / data ────┤   - avatar worker │◄──────────┤ AvatarSession    │
│ menu catalog ◄─────┼── HTTP /menu ────┼───────────────────┘           └──────────────────┘
└────────────────────┘                  (audio+video published by avatar worker)
```

### 3.1 Avatar
- Use LiveKit **`AvatarSession`** plugin. The avatar joins the room as a separate
  *avatar-worker* participant; the `AgentSession` sends its TTS audio to the worker, which
  publishes synced **audio + video**. (Set the agent session's audio output to the avatar.)
- Frontend: `useVoiceAssistant()` returns `{ agent, audioTrack, videoTrack, state }` —
  render `videoTrack` in the avatar panel; `state` drives the listening/thinking/speaking UI.
- Works with **our Soniox TTS** (the avatar is driven by the agent's output audio, not its own TTS).
- **Provider is an open decision** (see §7) — candidates: Tavus, Anam, Simli, bitHuman, Beyond
  Presence. Trade-offs: realism vs per-minute cost vs join/playback latency. We'll keep this
  behind a small abstraction so we can swap providers, and support an **audio-only fallback**
  (animated orb) if the avatar provider is down.

### 3.2 Live order screen (cart sync) — the key real-time piece
Two complementary mechanisms (hybrid, like LiveKit's `drive-thru` example):
- **Push (event-driven):** every time a cart tool mutates `OrderCart` (`add_to_order`,
  `remove_from_order`, `set_order_type`, `set_customer_info`, `place_order`, …), the agent
  publishes the **full order state** as a JSON **data packet** (topic `order.state`). The UI
  re-renders instantly.
- **Pull (resync):** agent registers a `get_order_state` **RPC**; the frontend calls it on
  connect and after any reconnect to get the authoritative state (covers refresh / network drop).

`OrderCart` gets a `to_state_dict()` producing a stable JSON contract (see §4). All cart
mutations route through one `publish_order_state()` helper so we never forget to sync.

### 3.3 Live menu highlight
- **Catalog:** new `GET /menu` endpoint on the token server serves the Clover cache as JSON
  (categories → items with name, price, veg, availability, voice_line, modifiers). The menu panel
  renders this once on load.
- **Highlight:** when the agent calls `check_menu_item`, `search_menu_items`, or `add_to_order`,
  it publishes a `ui.focus` data packet (`{type, item_ids[], query}`). The menu panel highlights
  and scrolls those items into view, so the screen tracks the conversation.

### 3.4 Captions + agent state
- **Captions:** `useTranscriptions` renders Sierra's words (and optionally the user's) under the
  avatar, in sync with audio. Good for accessibility and the "two humans" feel.
- **State:** `useVoiceAssistant().state` → mic-pulse when listening, spinner when thinking,
  waveform when speaking.

### 3.5 Channel-aware behavior (web vs phone)
The web customer **sees** prices, images, and the cart — so several phone-only prompt rules
should change for web:
- Phone prompt hides prices until asked; **web shows/says prices freely** (locked — they're on screen).
- Web Sierra can say "as you can see on the menu / on your screen".
- Web latency is lower; web session config already separate (`session_config.py`).
→ Introduce a **web prompt variant** (channel-aware system prompt) rather than reusing the phone prompt verbatim.

### 3.6 Hybrid control — frontend → agent (tap-to-add)
Because ordering is hybrid, the **browser must be able to drive the cart too**, without breaking
the server-as-source-of-truth rule:
- The agent registers client-callable **RPC methods**: `cart_add(item_id, qty, modifiers[])`,
  `cart_set_qty(item_id, qty)`, `cart_remove(item_id)`, and order-flow setters
  (`set_order_type`, etc.) as needed.
- A menu tap → frontend `performRpc("cart_add", …)` → agent validates against the menu cache,
  mutates `OrderCart`, then `publish_order_state()` so all panels reconcile.
- **Required modifiers on tap:** items with required choices (Spice Level, Choose Curry, Combo
  Drink…) can't be added blindly. v1 approach: tapping such an item either (a) opens a small
  **modifier picker** in the UI, or (b) adds it as "needs choices" and **hands to Sierra** to ask
  by voice. Default: modifier picker for simple single-select (spice), voice for complex combos.
- **Acknowledgement:** after a tap-add, Sierra gives a short spoken confirm ("Added two Butter
  Chicken — anything else?") so voice and screen stay one conversation. The agent must treat a
  tap as a real turn/event in its flow (not silently mutate state).

---

## 4. Data contracts (design these precisely before coding)

All payloads JSON, UTF-8, ≤15 KiB (RPC) / small (data packets).

**`order.state`** (push on every cart change + return of `get_order_state` RPC):
```jsonc
{
  "status": "building | awaiting_type | awaiting_contact | confirming | placed",
  "items": [
    { "id": "clover_item_id", "name": "Butter Chicken", "qty": 2,
      "unit_price": 13.99, "line_total": 27.98, "note": "medium spicy",
      "modifiers": ["medium spicy"] }
  ],
  "order_type": "pickup | delivery | null",
  "delivery_address": "string | null",
  "customer": { "name": "string | null", "phone": "string | null" },
  "subtotal": 27.98, "delivery_charge": 0, "total": 27.98,
  "eta": "string | null", "order_id": "string | null"
}
```

**`ui.focus`** (highlight in menu): `{ "kind": "item|search", "item_ids": ["..."], "query": "paneer" }`

**`ui.checkout`** (show final confirmation overlay): `{ "summary": <order.state>, "needs_confirm": true }`

**`ui.notice`** (transient toast): `{ "level": "info|warn|error", "message": "..." }`

**Client → agent RPCs** (hybrid tap-to-add; payload JSON):
- `cart_add` → `{ "item_id": "...", "qty": 1, "modifiers": ["medium spicy"] }`
- `cart_set_qty` → `{ "item_id": "...", "qty": 3 }`
- `cart_remove` → `{ "item_id": "..." }`
- `get_order_state` → (no args) returns current `order.state`
Each returns `{ "ok": true, "state": <order.state> }` or `{ "ok": false, "error": "...", "needs": ["spice_level"] }`
(where `needs` tells the UI which required modifiers to collect before the add can complete).

These become the stable interface between agent and UI; both sides version it (`"v": 1`).

---

## 5. Edge cases & failure modes (the "production / cover everything" list)

### Connection & session
- Mic permission denied / not granted → clear prompt + retry; never silently fail.
- Browser autoplay blocked → require user gesture (already do `startAudio()` on click).
- Network drop / WebRTC reconnect → on reconnect, call `get_order_state` to resync the order panel; show a "reconnecting" banner.
- Page refresh mid-order → order state lives in the agent session, which ends on disconnect.
  Decide: (a) accept loss + warn before unload, or (b) implement **session resume** (stable
  room+identity, agent re-attaches to prior cart). Phase-1 default: warn-on-unload; resume later.
- Agent not dispatched / worker crash → detect "no agent joined in N s" → error UI + retry; surface server health.
- Avatar worker fails to join / provider outage → fall back to audio-only orb (don't block the call).
- Double connect (two tabs) → one active session per identity; block/observe second tab.

### Conversation correctness (carry over Tier B awareness)
- User talks over Sierra (barge-in) → handled by turn detection; ensure caption/UI reflect interruption.
- Item discussed that isn't on the menu → Sierra says so; `ui.notice` optional; no phantom highlight.
- Ambiguous request ("something sweet") → search highlights ≤2 items; UI shows them.
- User edits by voice and (if enabled) by tapping the menu at the same time → single source of
  truth = server `OrderCart`; client taps are *requests* that go through the agent/RPC, then the
  pushed `order.state` reconciles the UI (no optimistic divergence).
- Long replies / lists → cap, same as phone.
- Language switching (Punjabi/English/Hindi) mid-call → captions + UI labels bilingual.

### Commerce / data
- Prices: shown on web; ensure menu prices and cart math match Clover cache.
- Item becomes unavailable (86'd) → reflected from cache/availability; block add.
- Payment: current model is pay-at-pickup/delivery (no card). Online payment is a **separate
  decision** (see §7) — default: keep pay-on-pickup for v1; online pay is a later phase.
- Order submission to Clover POS = **Phase 8c** (separate track). For the web demo, `place_order`
  can stay log-only first, then wire to Clover when 8c lands.
- Idle/timeout → auto-end after inactivity with a friendly message.
- Abuse: rate-limit `/token` and `/menu`; basic bot protection.

### Frontend quality
- Mobile layout (stacked panels / collapsible menu) vs desktop 3-column.
- Slow menu image loading → skeletons; lazy-load images.
- Accessibility: captions, keyboard, ARIA, color contrast, RTL-safe Gurmukhi rendering.

---

## 6. Phased delivery (each phase = its own PR per `pr/pr_rules.md`)

| Phase | Deliverable | Notes |
|-------|-------------|-------|
| **W1** | New shell: tab switcher + **responsive** 3-panel layout (desktop 3-col / mobile stacked); agent-state indicator + live captions; `GET /menu` + live-menu panel (with prices) | No avatar, no cart sync yet. Visible progress. |
| **W2** | **Live order panel + hybrid cart**: `OrderCart.to_state_dict()`, `publish_order_state()` on every mutation, `get_order_state` RPC, client→agent cart RPCs (`cart_add/remove/set_qty`), menu "Add" buttons, frontend order board | The core real-time win + tap-to-add. |
| **W3** | **Menu highlight + modifier picker**: `ui.focus` packets → highlight/autoscroll; modifier picker for tap-add of items with required choices; Sierra acknowledges tap-adds | Ties menu to conversation. |
| **W4** | **Avatar**: provider integration via `AvatarSession`, `videoTrack` in UI, audio-only fallback | Provider chosen at this point (§7 #1). |
| **W5** | **Hardening**: reconnect/resync, error states, mobile polish, idle timeout, rate limiting | Production edge cases. |
| **W6** | **Web prompt variant**: channel-aware prompt (prices on screen, tap-add awareness, "two humans" polish), checkout overlay | Conversation quality for web. |
| later | **Store tab**, **online payment**, **Clover submit (8c)** | Separate plans. |

---

## 7. Decisions

**Locked (2026-06-28):**
1. **Ordering = HYBRID** — voice + tap-to-add from menu (server cart is source of truth; §3.6).
2. **Prices = shown openly** on web menu/cart; web-Sierra says them freely.
3. **Finalization = `place_order` log-only + pay at pickup/delivery** for v1; Clover POS submit
   comes later via **Phase 8c** (web orders don't hit POS yet).
4. **Layout = fully responsive** from the start (desktop 3-column / mobile stacked).
5. **Avatar provider = decide at W4** — build W1–W3 first; keep behind a swappable abstraction
   with an audio-only fallback.

**Still open (low urgency):**
6. **Session resume on refresh** — v1 default: warn-on-unload + lose in-progress order; build true
   resume (stable room+identity, agent re-attaches to prior cart) later if needed.
7. **Avatar budget/quality** ceiling — to settle alongside #5 at W4 (realism Tavus/Beyond Presence
   vs latency-cost Simli/bitHuman/Anam).

---

## 8. Files this will touch (anticipated)

| Area | File(s) |
|------|---------|
| Frontend shell/tabs/panels | `web/src/` (new components: `OrderWithSierra`, `Avatar`, `LiveMenu`, `OrderPanel`, `Captions`, `TabSwitcher`) |
| Menu API | `token_server.py` (`GET /menu`), reuse `menu_provider` |
| Order state contract | `restaurant/orders.py` (`to_state_dict`), new `restaurant/web_sync.py` (publish helpers) |
| Agent wiring | `agent.py` (publish on cart mutations, register `get_order_state` RPC, `ui.focus` on menu tools, avatar session, web prompt variant) |
| Session config | `restaurant/session_config.py` (avatar audio output for web) |
| Deps | `pyproject.toml` (avatar plugin), `web/package.json` (`@livekit/components-react`) |

> Reference: LiveKit `drive-thru` complex-agent example (voice ordering + live order board via
> `get_order_state` RPC + `show_checkout` push) is the closest production pattern to mirror.
