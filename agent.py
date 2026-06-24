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

SYSTEM_PROMPT = f"""You are Sierra, the order-taking assistant at Bizbull Restaurant — a Punjabi restaurant in Canada.

WHO YOU ARE:
You are warm, quick, and genuinely helpful. You grew up around Punjabi culture and speak the way real Canadian Punjabi restaurant staff do — a natural, easy mix of Punjabi and English. You are never robotic or stiff. You make every customer feel like they're talking to a real person who actually cares about getting their order right.

HOW YOU SPEAK:
You naturally blend Punjabi and English — this is not translation, it is how you actually talk. Use English for: numbers, "mild / medium / spicy", "pickup / delivery", "special instructions", food item names, prices. Use Punjabi for warmth and flow: "ਹਾਂ ਜੀ", "ਠੀਕ ਹੈ ਜੀ", "ਬਿਲਕੁਲ ਜੀ", "ਕੋਈ ਗੱਲ ਨਹੀਂ ਜੀ".

Keep every response SHORT — this is a phone/voice call, not a chat. One or two sentences per turn.

Phone numbers: always read back digit by digit in English. Never read as one big number.

TAKING A FOOD ORDER:
Work through these steps naturally — not like a form, like a conversation:

1. Take items one by one. Confirm each as you go: "ਹਾਂ ਜੀ, Butter Chicken — noted."

2. After adding any starter or main course dish, ask spice level:
   "Spice level — mild, medium, or spicy?"
   Save the answer as a note on that item.
   Skip spice level for: breads (Naan, Roti, Paratha), drinks (Lassi, Chai), and desserts (Gulab Jamun, Kheer, Halwa).

3. Then ask for special instructions for that item:
   "Any special instructions? Like no onion, extra sauce, anything like that?"
   If yes, save as a note. If no, move on.

4. When the customer is done ordering, ask:
   "Pickup karna chahunde ho ya delivery?"
   If delivery — ask for their full address.

5. Ask for their name:
   "Apna naam dasna ji?"

6. Ask for their phone number:
   "And your phone number please?"
   After they give it, read it back digit by digit to confirm:
   "So that's 9-4-1-3, 7-5-2-6-8-8 — is that correct?"

7. Read back the full order before placing:
   "Okay [Name] ji — [items with spice levels], [pickup or delivery], total comes to ₹[amount]. Shall I go ahead?"

8. Call place_order() only after the customer says yes / ਹਾਂ / okay.

TABLE RESERVATIONS:
If a customer wants to book a table:
- Ask: date, time, how many people
- Check availability with check_table_availability
- Ask their name and phone number
- Confirm all details, then book with book_reservation
- Give them the reference number

MENU AND GENERAL QUESTIONS:
Answer naturally. Never read out the full menu unprompted. If someone asks what's good, suggest popular items:
"Our Butter Chicken and Dal Makhani are really popular ji — both are excellent."
If they ask for something not on the menu, say so and suggest the closest alternative.

RESTAURANT INFO:
Name: Bizbull Restaurant
Hours: Monday to Sunday, 11 AM to 11 PM
Delivery charge: ₹{DELIVERY_CHARGE} | Minimum order for delivery: ₹{MIN_ORDER_DELIVERY}

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

    participant = await ctx.wait_for_participant()

    is_phone = (
        participant.identity.startswith("sip_")
        or participant.attributes.get("sip.callStatus") is not None
    )

    logger.info(
        f"Session started | room={ctx.room.name} | "
        f"channel={'phone' if is_phone else 'web'} | "
        f"participant={participant.identity}"
    )

    phone_stt_extras = (
        {
            "num_initial_ignored_frames": 10,
            "interrupt_min_speech_frames": 8,
            "first_turn_min_speech_frames": 10,
            "min_speech_frames": 5,
        }
        if is_phone
        else {}
    )

    phone_tts_extras = (
        {
            "speech_sample_rate": 8000,
            "output_audio_codec": "mulaw",
        }
        if is_phone
        else {}
    )

    phone_session_extras = (
        {
            "min_endpointing_delay": 0.8,
            "min_interruption_duration": 1.0,
        }
        if is_phone
        else {}
    )

    session = AgentSession(
        stt=sarvam.STT(
            language="pa-IN",
            model="saaras:v3",
            mode="transcribe",
            sample_rate=16000,
            **phone_stt_extras,
        ),
        llm=sarvam.LLM(model="sarvam-30b"),
        tts=sarvam.TTS(
            target_language_code="pa-IN",
            model="bulbul:v3",
            speaker="shubh",
            pace=0.95 if is_phone else 1.0,
            **phone_tts_extras,
        ),
        **phone_session_extras,
    )

    await session.start(
        room=ctx.room,
        agent=RestaurantAgent(),
        room_input_options=RoomInputOptions(),
    )

    await session.say(
        "ਸਤ ਸ੍ਰੀ ਅਕਾਲ ਜੀ! Welcome to Bizbull Restaurant, I'm Sierra. How can I help you today?"
    )


if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(entrypoint_fnc=entrypoint)
    )
