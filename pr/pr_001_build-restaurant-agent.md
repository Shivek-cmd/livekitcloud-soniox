# PR 001 — Build Restaurant Voice Agent

## Branch
`pr_001_build-restaurant-agent`

## What This PR Does
Initial build of the Punjabi restaurant voice agent — core pipeline (STT → LLM → TTS), order management, reservation booking, and token server for web channel.

---

## Files Added

### `pyproject.toml`
Project dependencies. Pins `livekit-agents[sarvam]>=1.0,<2.0` which resolved to `1.6.3` on VPS.

### `.env.example`
Template for environment variables. Actual `.env` lives on VPS only (gitignored).

### `.gitignore`
Ignores `.env`, `.venv/`, `__pycache__`, logs, `web/dist/`.

### `restaurant/__init__.py`
Empty package init.

### `restaurant/menu.py`
- `MENU` dict — 5 categories: starters, mains, breads, drinks, desserts (22 items total)
- `find_item(name)` — case-insensitive search by English or Punjabi name
- `get_menu_text()` — formats menu as text injected into system prompt
- Constants: `RESTAURANT_NAME`, `OPENING_HOURS`, `DELIVERY_CHARGE` (₹50), `MIN_ORDER_DELIVERY` (₹200)

### `restaurant/orders.py`
- `CartItem` dataclass — name, punjabi, price, quantity, note
- `OrderCart` dataclass — items list, order_type, customer_name, customer_phone, delivery_address
- Methods: `add_item()`, `remove_item()`, `summary()`, `ready_to_place()`
- Properties: `subtotal`, `total` (adds delivery charge automatically)

### `restaurant/reservations.py`
- In-memory reservation store (Phase 1 — replace with DB in Phase 2)
- `check_availability(date, time, party_size)` — validates time slot and capacity (50 per slot max)
- `book(...)` — creates reservation with 6-char reference code
- Valid time slots: 11:00–14:30 and 18:00–21:30

### `agent.py`
Main agent file. Key decisions:
- `RestaurantAgent(Agent)` subclass — tools as `@function_tool` methods, `self.cart` gives per-session isolated state
- System prompt in English with strict "ALWAYS respond in Punjabi" rule
- Menu injected into system prompt at startup
- `entrypoint()` detects phone vs web channel via SIP participant attributes
- TTS pace set to `0.95` on phone (slightly slower for phone audio quality)
- Greeting via `session.say()` — skips LLM, fastest path for first audio

**Tools implemented:**
| Tool | Purpose |
|---|---|
| `add_to_order` | Add item + qty + special note to cart |
| `remove_from_order` | Remove item from cart |
| `set_order_type` | Set pickup or delivery |
| `set_customer_info` | Save name + phone |
| `set_delivery_address` | Save delivery address |
| `get_order_summary` | Read back full order before confirming |
| `place_order` | Finalize order (logs to console — POS integration Phase 2) |
| `check_menu_item` | Check if item exists + get price |
| `check_table_availability` | Check if time slot is free |
| `book_reservation` | Book table, return ref code |

### `token_server.py`
FastAPI app for web channel token generation.
- `GET /health` — health check
- `GET /token?room=&identity=` — returns signed LiveKit JWT + server URL
- CORS open (restrict to your domain in production)
- Runs on port 8001 (set in systemd service)

---

## What's NOT in This PR
- Web frontend (React) — Phase 2
- Systemd service files — separate PR after testing
- Caddy subdomain config — separate PR
- POS integration for `place_order` — Phase 2
- Database for reservations — Phase 2

---

## How to Test on VPS

```bash
cd /opt/livekit-sarvam
git pull origin pr_001_build-restaurant-agent

# Syntax check
uv run python -c "import agent; print('agent OK')"
uv run python -c "import token_server; print('token_server OK')"

# Run agent in dev mode
uv run python agent.py dev

# In another terminal: run token server
uv run uvicorn token_server:app --host 0.0.0.0 --port 8001
```

---

## Post-Merge: VPS Pull Command
```bash
cd /opt/livekit-sarvam && git pull origin main && uv sync
```
