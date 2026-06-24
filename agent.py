import json
import logging
import os
from typing import Annotated

from dotenv import load_dotenv
from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    RoomInputOptions,
    WorkerOptions,
    cli,
    function_tool,
)
from livekit.plugins import sarvam

from restaurant.menu import (
    DELIVERY_CHARGE,
    MIN_ORDER_DELIVERY,
    OPENING_HOURS,
    RESTAURANT_NAME,
    RESTAURANT_NAME_EN,
    find_item,
    get_menu_text,
)
from restaurant.orders import OrderCart
from restaurant import reservations as res_store

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger("restaurant-agent")

SYSTEM_PROMPT = f"""You are a voice assistant for {RESTAURANT_NAME_EN} ({RESTAURANT_NAME}), a Punjabi restaurant.

YOUR RESPONSIBILITIES:
1. Take food orders — pickup or delivery
2. Book table reservations
3. Answer questions about the menu, hours, and location

LANGUAGE RULES:
- ALWAYS respond in Punjabi (Gurmukhi script)
- Keep responses SHORT — this is a voice call, not a chat
- One sentence per thought, two sentences maximum per turn
- Never read out the full menu unless specifically asked
- Use natural Punjabi: ਹਾਂ ਜੀ, ਠੀਕ ਹੈ ਜੀ, ਜ਼ਰੂਰ ਜੀ

ORDER FLOW:
1. Ask: pickup ਜਾਂ delivery?
2. Take items one by one, confirm each
3. Collect name + phone (always)
4. For delivery: collect address too
5. Read back full order — ask for confirmation
6. Only call place_order() after explicit "ਹਾਂ" confirmation

RESERVATION FLOW:
1. Ask: date, time, party size
2. Check availability
3. Collect name + phone
4. Confirm all details, then book

RESTAURANT INFO:
Name: {RESTAURANT_NAME} ({RESTAURANT_NAME_EN})
Hours: {OPENING_HOURS}
Delivery charge: ₹{DELIVERY_CHARGE} | Min order for delivery: ₹{MIN_ORDER_DELIVERY}

MENU:
{get_menu_text()}
"""


class RestaurantAgent(Agent):
    def __init__(self):
        super().__init__(instructions=SYSTEM_PROMPT)
        self.cart = OrderCart()

    # ── ORDER TOOLS ──────────────────────────────────────────────────────────

    @function_tool
    async def add_to_order(
        self,
        item_name: Annotated[str, "Name of the menu item in English or Punjabi"],
        quantity: Annotated[int, "How many of this item to add"],
        note: Annotated[str, "Special instructions e.g. 'extra spicy', 'no onion'"] = "",
    ) -> str:
        """Add an item to the customer's order."""
        item = find_item(item_name)
        if not item:
            return f"'{item_name}' is not on our menu. Ask the customer to clarify."
        return self.cart.add_item(item, quantity, note)

    @function_tool
    async def remove_from_order(
        self,
        item_name: Annotated[str, "Name of the item to remove"],
    ) -> str:
        """Remove an item from the customer's order."""
        return self.cart.remove_item(item_name)

    @function_tool
    async def set_order_type(
        self,
        order_type: Annotated[str, "Either 'pickup' or 'delivery'"],
    ) -> str:
        """Set whether the order is for pickup or delivery."""
        order_type = order_type.lower().strip()
        if order_type not in ("pickup", "delivery"):
            return "order_type must be 'pickup' or 'delivery'."
        self.cart.order_type = order_type
        if order_type == "delivery":
            return f"Set to delivery. Delivery charge ₹{DELIVERY_CHARGE} will be added. Now ask for delivery address."
        return "Set to pickup. Ask for customer name and phone number."

    @function_tool
    async def set_customer_info(
        self,
        name: Annotated[str, "Customer's name"],
        phone: Annotated[str, "Customer's 10-digit phone number"],
    ) -> str:
        """Save the customer's name and phone number."""
        self.cart.customer_name = name
        self.cart.customer_phone = phone
        return f"Saved: {name}, {phone}."

    @function_tool
    async def set_delivery_address(
        self,
        address: Annotated[str, "Full delivery address including area and landmark"],
    ) -> str:
        """Save the delivery address for a delivery order."""
        self.cart.delivery_address = address
        return f"Delivery address saved: {address}."

    @function_tool
    async def get_order_summary(self) -> str:
        """Get the full current order to read back to the customer before confirming."""
        return self.cart.summary()

    @function_tool
    async def place_order(self) -> str:
        """Finalize and place the order. Only call this after the customer explicitly confirms."""
        ready, reason = self.cart.ready_to_place()
        if not ready:
            return f"Cannot place order: {reason}"

        order_data = {
            "items": [
                {"name": i.name, "qty": i.quantity, "price": i.price, "note": i.note}
                for i in self.cart.items
            ],
            "type": self.cart.order_type,
            "subtotal": self.cart.subtotal,
            "total": self.cart.total,
            "customer": self.cart.customer_name,
            "phone": self.cart.customer_phone,
            "address": self.cart.delivery_address,
        }
        logger.info(f"ORDER_PLACED: {json.dumps(order_data, ensure_ascii=False)}")

        wait = "30-40 ਮਿੰਟ" if self.cart.order_type == "delivery" else "20-25 ਮਿੰਟ"
        return (
            f"Order placed! Total ₹{self.cart.total}. "
            f"Tell customer: ਤੁਹਾਡਾ ਆਰਡਰ ਮਿਲ ਗਿਆ ਜੀ। "
            f"{wait} ਵਿੱਚ ਤਿਆਰ ਹੋ ਜਾਵੇਗਾ। ਧੰਨਵਾਦ ਜੀ!"
        )

    # ── MENU TOOLS ───────────────────────────────────────────────────────────

    @function_tool
    async def check_menu_item(
        self,
        item_name: Annotated[str, "Item name to look up"],
    ) -> str:
        """Check if an item is on the menu and get its price and details."""
        item = find_item(item_name)
        if not item:
            return f"'{item_name}' is not on our menu."
        veg = "Vegetarian" if item["veg"] else "Non-vegetarian"
        return f"{item['name']} ({item['punjabi']}) — ₹{item['price']} — {veg}"

    # ── RESERVATION TOOLS ────────────────────────────────────────────────────

    @function_tool
    async def check_table_availability(
        self,
        date: Annotated[str, "Date in YYYY-MM-DD format"],
        time: Annotated[str, "Time in HH:MM 24-hour format e.g. 19:30"],
        party_size: Annotated[int, "Number of people"],
    ) -> str:
        """Check if a table is available for a given date, time and party size."""
        available, message = res_store.check_availability(date, time, party_size)
        return message if not available else f"Table available for {party_size} on {date} at {time}."

    @function_tool
    async def book_reservation(
        self,
        date: Annotated[str, "Date in YYYY-MM-DD format"],
        time: Annotated[str, "Time in HH:MM 24-hour format e.g. 19:30"],
        party_size: Annotated[int, "Number of people"],
        customer_name: Annotated[str, "Customer's name"],
        customer_phone: Annotated[str, "Customer's phone number"],
    ) -> str:
        """Book a table reservation after confirming all details with the customer."""
        available, message = res_store.check_availability(date, time, party_size)
        if not available:
            return message

        record = res_store.book(date, time, party_size, customer_name, customer_phone)
        logger.info(f"RESERVATION_BOOKED: {json.dumps(record, ensure_ascii=False)}")

        return (
            f"Reservation confirmed! Ref: {record['ref']}. "
            f"Tell customer: ਤੁਹਾਡੀ ਬੁਕਿੰਗ ਹੋ ਗਈ ਜੀ! "
            f"Reference number ਹੈ {record['ref']}। ਧੰਨਵਾਦ ਜੀ!"
        )


async def entrypoint(ctx: JobContext):
    await ctx.connect()

    is_phone = any(
        p.identity.startswith("sip_") or p.attributes.get("sip.callStatus") is not None
        for p in ctx.room.remote_participants.values()
    )

    logger.info(
        f"Session started | room={ctx.room.name} | "
        f"channel={'phone' if is_phone else 'web'} | "
        f"participants={len(ctx.room.remote_participants)}"
    )

    session = AgentSession(
        stt=sarvam.STT(
            language="pa-IN",
            model="saaras:v3",
            mode="transcribe",
            sample_rate=16000,
        ),
        llm=sarvam.LLM(model="sarvam-30b"),
        tts=sarvam.TTS(
            target_language_code="pa-IN",
            model="bulbul:v3",
            speaker="shubh",
            speech_sample_rate=22050,
            pace=0.95 if is_phone else 1.0,
        ),
    )

    await session.start(
        room=ctx.room,
        agent=RestaurantAgent(),
        room_input_options=RoomInputOptions(),
    )

    await session.say(
        "ਸਤ ਸ੍ਰੀ ਅਕਾਲ ਜੀ! ਪੰਜਾਬ ਦਾ ਢਾਬਾ ਵਿੱਚ ਤੁਹਾਡਾ ਸੁਆਗਤ ਹੈ। "
        "ਕੀ ਤੁਸੀਂ ਆਰਡਰ ਦੇਣਾ ਚਾਹੁੰਦੇ ਹੋ, ਟੇਬਲ ਬੁੱਕ ਕਰਨਾ ਚਾਹੁੰਦੇ ਹੋ, "
        "ਜਾਂ ਕੋਈ ਸਵਾਲ ਪੁੱਛਣਾ ਚਾਹੁੰਦੇ ਹੋ?"
    )


if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(entrypoint_fnc=entrypoint)
    )
