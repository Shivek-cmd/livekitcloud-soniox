# Agent Implementation Plan

## Project Structure

```
livekit-sarvam/
├── .env                        # secrets (gitignored)
├── .env.example
├── pyproject.toml
├── agent.py                    # main agent entrypoint
├── token_server.py             # FastAPI token backend (web channel)
├── restaurant/
│   ├── __init__.py
│   ├── menu.py                 # menu data + lookup tools
│   ├── orders.py               # order state management
│   └── reservations.py        # reservation logic
├── prompts/
│   └── system_pa.txt           # Punjabi system prompt
├── web/                        # React frontend
│   └── src/App.tsx
└── docker/
    ├── docker-compose.yml
    ├── livekit.yaml
    └── sip-config.yaml
```

---

## Dependencies

```toml
# pyproject.toml
[project]
name = "livekit-sarvam-restaurant"
version = "0.1.0"
requires-python = ">=3.10"

dependencies = [
    "livekit-agents[sarvam]~=1.5",
    "fastapi",
    "uvicorn",
    "python-dotenv",
]
```

---

## System Prompt (Punjabi)

```
ਤੁਸੀਂ ਇੱਕ ਰੈਸਟੋਰੈਂਟ ਵੌਇਸ ਅਸਿਸਟੈਂਟ ਹੋ।
ਤੁਹਾਡਾ ਕੰਮ ਹੈ:
1. ਖਾਣੇ ਦੇ ਆਰਡਰ ਲੈਣਾ (ਪਿਕਅੱਪ ਜਾਂ ਡਿਲੀਵਰੀ)
2. ਟੇਬਲ ਰਿਜ਼ਰਵੇਸ਼ਨ ਬੁੱਕ ਕਰਨਾ
3. ਮੀਨੂ ਬਾਰੇ ਸਵਾਲਾਂ ਦੇ ਜਵਾਬ ਦੇਣਾ

ਨਿਯਮ:
- ਹਮੇਸ਼ਾ ਪੰਜਾਬੀ ਵਿੱਚ ਬੋਲੋ
- ਛੋਟੇ ਜਵਾਬ ਦਿਓ (ਵੌਇਸ ਕਾਲ ਹੈ)
- ਆਰਡਰ ਤੋਂ ਪਹਿਲਾਂ ਪੁਸ਼ਟੀ ਕਰੋ
- ਡਿਲੀਵਰੀ ਲਈ ਪਤਾ ਅਤੇ ਫ਼ੋਨ ਨੰਬਰ ਲਓ

[MENU_CONTEXT]  ← injected at runtime
```

---

## agent.py (Planned Structure)

```python
import os
from dotenv import load_dotenv
from livekit.agents import AgentSession, Agent, RoomInputOptions, cli, WorkerOptions
from livekit.plugins import sarvam
from restaurant.menu import get_menu_context
from restaurant.orders import OrderCart
from restaurant.reservations import ReservationManager

load_dotenv()

SYSTEM_PROMPT_TEMPLATE = open("prompts/system_pa.txt").read()


class RestaurantAgent(Agent):
    def __init__(self):
        menu_context = get_menu_context()  # injects current menu into prompt
        prompt = SYSTEM_PROMPT_TEMPLATE.replace("[MENU_CONTEXT]", menu_context)
        super().__init__(
            instructions=prompt,
            tools=[
                add_item_to_order,
                remove_item_from_order,
                confirm_order,
                check_menu_item,
                set_order_type,
                collect_delivery_info,
                book_reservation,
                check_reservation_availability,
            ],
        )


async def entrypoint(ctx):
    # Detect if phone call (SIP participant present)
    is_phone = any(
        "sip" in p.identity
        for p in ctx.room.remote_participants.values()
    )

    session = AgentSession(
        stt=sarvam.STT(
            language="pa-IN",
            model="saaras:v3",
            mode="transcribe",
            sample_rate=16000,
        ),
        llm=sarvam.LLM(model="sarvam-30b-16k"),
        tts=sarvam.TTS(
            target_language_code="pa-IN",
            model="bulbul:v3",
            speaker="shubh",
            speech_sample_rate=22050,
            pace=1.0 if not is_phone else 0.95,  # slightly slower on phone
        ),
    )

    await session.start(
        room=ctx.room,
        agent=RestaurantAgent(),
        room_input_options=RoomInputOptions(),
    )

    # Greeting
    greeting = (
        "ਸਤ ਸ੍ਰੀ ਅਕਾਲ! [Restaurant Name] ਵਿੱਚ ਤੁਹਾਡਾ ਸੁਆਗਤ ਹੈ। "
        "ਕੀ ਤੁਸੀਂ ਆਰਡਰ ਦੇਣਾ ਚਾਹੁੰਦੇ ਹੋ, ਟੇਬਲ ਬੁੱਕ ਕਰਨਾ ਚਾਹੁੰਦੇ ਹੋ, "
        "ਜਾਂ ਮੀਨੂ ਬਾਰੇ ਜਾਣਨਾ ਚਾਹੁੰਦੇ ਹੋ?"
    )
    await session.generate_reply(instructions=greeting)


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
```

---

## Tool Definitions (Planned)

```python
# restaurant/orders.py

@function_tool
async def add_item_to_order(
    context: RunContext,
    item_name: str,
    quantity: int,
    special_instructions: str = ""
) -> str:
    """Add an item to the customer's order."""
    # Validate item exists in menu
    # Add to in-memory cart for this session
    # Return confirmation string in Punjabi
    ...

@function_tool
async def set_order_type(
    context: RunContext,
    order_type: str  # "pickup" or "delivery"
) -> str:
    """Set whether the order is for pickup or delivery."""
    ...

@function_tool
async def collect_delivery_info(
    context: RunContext,
    address: str,
    phone_number: str
) -> str:
    """Collect delivery address and contact number."""
    ...

@function_tool
async def confirm_order(context: RunContext) -> str:
    """Read back the full order and ask for confirmation before placing."""
    ...

@function_tool
async def book_reservation(
    context: RunContext,
    date: str,
    time: str,
    party_size: int,
    customer_name: str,
    phone_number: str
) -> str:
    """Book a table reservation."""
    ...
```

---

## Latency Optimizations in Code

### 1. Streaming — All Three Layers Must Stream

```python
# Verify these are all in streaming mode (default in livekit-agents, but confirm)
stt=sarvam.STT(...),        # streams partial results via WebSocket
llm=sarvam.LLM(...),        # streams tokens (OpenAI-compatible stream=True)
tts=sarvam.TTS(...),        # streams audio chunks via HTTP streaming
```

### 2. Filler Phrases While LLM Thinks

```python
FILLERS = [
    "ਹਾਂ ਜੀ...",
    "ਠੀਕ ਹੈ...",
    "ਦੇਖਦੇ ਹਾਂ...",
]

# Inject filler if LLM hasn't responded within 600ms
# (LiveKit Agents supports this via the `thinking_speech` config)
```

### 3. Pre-cache Common Responses

```python
CACHED_RESPONSES = {
    "hours": "ਅਸੀਂ ਸਵੇਰੇ 11 ਵਜੇ ਤੋਂ ਰਾਤ 10 ਵਜੇ ਤੱਕ ਖੁੱਲ੍ਹੇ ਹਾਂ।",
    "location": "ਅਸੀਂ [Address] ਤੇ ਹਾਂ।",
    "specials": "ਅੱਜ ਦੀ ਸਪੈਸ਼ਲ ਡਿਸ਼ ਹੈ...",
}
```

### 4. Batch Tool Calls

Instead of one tool call per item, collect the full order first then validate all items in one call:

```python
# Bad: 3 items = 3 sequential tool calls = +900ms
add_item("paneer burger", 1)
add_item("mango lassi", 2)
add_item("fries", 1)

# Good: 1 tool call = +300ms
add_items_to_order([
    {"name": "paneer burger", "qty": 1},
    {"name": "mango lassi", "qty": 2},
    {"name": "fries", "qty": 1},
])
```

---

## Running the Agent

```bash
# Install
uv sync

# Dev (local LiveKit in --dev mode)
python agent.py dev

# Production
python agent.py start

# Token server (for web channel)
uvicorn token_server:app --host 0.0.0.0 --port 8080
```

---

## Session State Per Call

Each call needs its own isolated order cart. LiveKit agent sessions are per-room, so store state in the `AgentSession` or pass via `RunContext`:

```python
# Each call gets a fresh OrderCart
# Store on the session object so all tool calls share it
session.userdata = {
    "cart": OrderCart(),
    "order_type": None,        # "pickup" or "delivery"
    "delivery_address": None,
    "customer_phone": None,
    "customer_name": None,
}
```
