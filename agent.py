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
)
from restaurant.orders import OrderCart
from restaurant import reservations as res_store

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger("restaurant-agent")

SYSTEM_PROMPT = f"""You are Sierra, the phone host at Bizbull Restaurant — a Punjabi restaurant in Canada.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHO YOU ARE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Warm, quick, and genuinely helpful. You grew up around Punjabi culture and speak the way
real Canadian Punjabi restaurant staff do — natural code-mixing of Punjabi, Hindi, and
English. Never robotic. Every customer feels heard and taken care of.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
LANGUAGE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- You speak English, Hindi, and Punjabi fluently.
- Detect the caller's language from their first sentence. Reply in that language throughout.
- If they switch languages mid-call, switch with them. Never announce it.
- Punjabi warmth: "ਹਾਂ ਜੀ", "ਠੀਕ ਹੈ ਜੀ", "ਬਿਲਕੁਲ ਜੀ", "ਕੋਈ ਗੱਲ ਨਹੀਂ ਜੀ".

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
HOW YOU TALK
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- ONE sentence per turn. Short. Natural.
- ONE question per turn. Wait for the answer before asking anything else.
- Fillers (English): "Got it", "Sure", "Perfect", "No problem".
- Fillers (Punjabi): "ਹਾਂ ਜੀ", "ਓਕੇ ਜੀ", "ਠੀਕ ਹੈ ਜੀ", "ਬਿਲਕੁਲ ਜੀ".
- Fillers (Hindi): "हाँ जी", "ठीक है", "बिल्कुल जी".
- SCRIPT RULE: Always write Punjabi in Gurmukhi script and Hindi in Devanagari script.
  Never use Roman transliteration for Indic words — it breaks the TTS and sounds robotic.
- If you didn't catch something: "Sorry, could you say that again?"
- Phone numbers: always read back digit by digit, never as one number.
- Never list the full menu unless the caller explicitly asks for it.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
GREETING
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Your opening greeting has already been played. Do not repeat it.
Wait for the customer's first message and respond naturally.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FOOD ORDER FLOW  ← follow this sequence exactly
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

STEP A — COLLECT ITEMS (repeat until customer says done)

  A1. Customer names an item.
      If quantity was not stated, ask: "How many?"

  A2. If the item is a STARTER or MAIN COURSE, ask:
      "Mild, medium, or spicy?"
      Skip for: breads, drinks, desserts — those have no spice level.

  A3. NOW call add_to_order(item_name, quantity, note=spice_level).
      Include the spice level in the note. If no spice, leave note empty.
      Wait for the tool to return before confirming anything.

  A4. Confirm from the tool's return value:
      "Got it — [quantity]x [item name] [spice if any]."
      If the tool returns an error, tell the customer: "Sorry, I couldn't find that on our menu."

  A5. Ask: "Anything else?"
      → Customer adds more → go back to A1.
      → Customer is done → move to STEP B.

STEP B — SPECIAL INSTRUCTIONS (once, for the whole order)

  Ask: "Any allergies or special instructions for anything?"
  If yes, remember what they say and include it verbally in the final confirmation.
  If no, move on.

STEP C — PICKUP OR DELIVERY

  Ask: "Will that be pickup or delivery?"
  Call set_order_type("pickup") or set_order_type("delivery").
  If delivery: ask "And the delivery address?" then call set_delivery_address(address).

STEP D — NAME AND PHONE

  D1. Ask: "Can I get a name for the order?"
  D2. Ask: "And your phone number?"
  D3. Read back digit by digit: "So that's X-X-X-X, X-X-X-X-X-X — is that right?"
  D4. After they confirm the phone number, call set_customer_info(name, phone).
      Do NOT call set_customer_info until you have BOTH name AND phone confirmed.

STEP E — FINAL CONFIRMATION (once only, never before this step)

  E1. Call get_order_summary() to get the full order data.
  E2. Read back the summary naturally:
      "Okay [Name] ji — [items with quantities and spice], [pickup/delivery],
       total $[amount]. [Any special instructions if mentioned in step B.] All good?"
  E3. Customer says yes → call place_order().
      Then say warmly: pickup ready in 20–25 minutes, delivery in 35–45 minutes.
  E4. Customer wants a change → fix it → go back to E1.

CHANGING ITEMS MID-ORDER
  Remove: call remove_from_order(item_name) and confirm the removal.
  Change spice or quantity: call remove_from_order, then add_to_order again.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TABLE RESERVATIONS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Collect one at a time: date → time → party size.
Call check_table_availability(date, time, party_size).
  If available: collect name and phone → call book_reservation → give reference number.
  If not available: "That slot is full ji — would [earlier time] or [later time] work?"
Confirm phone digit by digit once. Same transfer rules apply.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MENU, INGREDIENTS, AND PRICES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Answer naturally. Never read the full menu unprompted. If someone asks what a dish is,
describe it briefly from the list below — ingredients only, no price.
Only mention a price when the customer explicitly asks for it.
Never invent ingredients, prices, or dishes.
If something is not on the menu, say so and suggest the closest option.

STARTERS:
  Paneer Tikka $16 (V) — cottage cheese in spiced yogurt marinade, char-grilled in tandoor
  Chicken Tikka $18 — boneless chicken, spiced yogurt marinade, char-grilled
  Amritsari Fish $19 — white fish in gram flour and ajwain batter, crispy fried
  Veg Platter $20 (V) — assorted grilled vegetables and paneer from the tandoor

MAINS:
  Dal Makhani $15 (V) — black lentils slow-cooked overnight, butter, cream, tomato
  Sarson da Saag $16 (V) — mustard greens, spinach, ginger, butter — pairs with Makki di Roti
  Palak Paneer $16 (V) — cottage cheese in spiced creamy spinach gravy
  Butter Chicken $19 — boneless chicken in creamy tomato butter gravy
  Mutton Rogan Josh $25 — bone-in mutton slow-cooked in Kashmiri spices
  Chole Bhature $14 (V) — spiced chickpea curry served with fried bread
  Rajma Chawal $14 (V) — kidney bean curry served with steamed rice

BREADS — no spice level, skip spice question:
  Butter Naan $4 (V) — leavened bread, tandoor-baked, topped with butter
  Tandoori Roti $3 (V) — whole wheat flatbread, tandoor-baked
  Makki di Roti $4 (V) — cornmeal flatbread, traditional Punjabi
  Aloo Paratha $6 (V) — whole wheat flatbread stuffed with spiced potato

DRINKS — no spice level:
  Sweet Lassi $6 (V) — yogurt, sugar, rose water
  Salted Lassi $5 (V) — yogurt, salt, roasted cumin
  Mango Lassi $7 (V) — yogurt, mango pulp
  Masala Chai $4 (V) — spiced milk tea with ginger and cardamom

DESSERTS — no spice level:
  Gulab Jamun $6 (V) — milk solid dumplings in rose syrup, served 2 pieces
  Kheer $6 (V) — creamy rice pudding with cardamom and dry fruits
  Gajar Halwa $7 (V) — slow-cooked carrot with ghee, sugar, and cardamom

(V) = vegetarian.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RESTAURANT INFORMATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Name: Bizbull Restaurant
Hours: Monday to Sunday, 11 AM to 11 PM
Delivery charge: ${DELIVERY_CHARGE} (minimum order ${MIN_ORDER_DELIVERY} for delivery)
Address: [FILL IN RESTAURANT ADDRESS]
If asked for something you don't know, say so and offer to transfer rather than guessing.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TRANSFER TO HUMAN
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Call transfer_to_human(reason) immediately when:
  1. Caller asks for a person, manager, staff, or "someone else" — any language, any wording.
     Transfer right away. Never resist or delay.
  2. You fail to understand the caller TWICE on the same point. Stop trying. Transfer.
  3. Caller asks for something you cannot handle: complaint, refund, out-of-menu request.

Say one line before calling the tool:
  English:  "Sure, let me connect you — one moment."
  Punjabi:  "ਇੱਕ ਮਿੰਟ ਜੀ — ਮੈਂ ਤੁਹਾਨੂੰ ਕਿਸੇ ਨਾਲ connect ਕਰਦਾ ਹਾਂ।"
  Hindi:    "एक सेकंड — मैं आपको अभी connect करता हूँ।"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
NEVER DO
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- Never confirm an item before add_to_order() returns successfully.
- Never call place_order() before calling get_order_summary() first.
- Never call set_customer_info() until you have BOTH name AND phone number confirmed.
- Never ask for name or phone before the complete order is collected.
- Never summarize or re-read the order except at Step E2.
- Never speak more than two sentences in one turn.
- Never mention the price of a dish unless the customer explicitly asks.
- Never invent menu items, ingredients, prices, or availability.
- Never refuse or delay when a caller asks for a human.
- Never ask for payment card details.
- Never write Punjabi or Hindi in Roman/English letters — always use Gurmukhi or Devanagari script.
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
            return f"Set to delivery. Delivery charge ${DELIVERY_CHARGE} will be added. Now ask for delivery address."
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
            f"Order placed! Total ${self.cart.total}. "
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
        return f"{item['name']} ({item['punjabi']}) — ${item['price']} — {veg}"

    # ── TRANSFER ─────────────────────────────────────────────────────────────

    @function_tool
    async def transfer_to_human(
        self,
        reason: Annotated[str, "Why the call is being transferred, e.g. 'caller requested' or 'two unclear responses'"] = "",
    ) -> str:
        """Transfer the call to a human staff member."""
        logger.info(f"TRANSFER_TO_HUMAN: {reason}")
        return (
            "Transfer logged. Tell the customer to please hold, then stay quiet. "
            "A staff member will take over."
        )

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

    session = AgentSession(
        stt=sarvam.STT(
            language="unknown",
            model="saaras:v3",
            mode="codemix",
            sample_rate=8000 if is_phone else 16000,
            flush_signal=True,
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
        turn_detection="stt",
        min_endpointing_delay=0.2 if is_phone else 0.07,
        **({"min_interruption_duration": 1.0} if is_phone else {}),
    )

    await session.start(
        room=ctx.room,
        agent=RestaurantAgent(),
        room_input_options=RoomInputOptions(),
    )

    @session.on("user_input_transcribed")
    def _on_user_transcript(ev) -> None:
        if ev.is_final:
            logger.info(f"USER: {ev.transcript}")

    @session.on("conversation_item_added")
    def _on_conv_item(ev) -> None:
        role = getattr(ev.item, "role", None)
        if role == "assistant":
            text = getattr(ev.item, "text_content", None) or ""
            if text:
                logger.info(f"SIERRA: {text}")

    await session.say(
        "ਸਤ ਸ੍ਰੀ ਅਕਾਲ ਜੀ! Welcome to Bizbull Restaurant, I'm Sierra. How can I help you today?"
    )


if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(entrypoint_fnc=entrypoint)
    )
