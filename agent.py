import asyncio
import json
import logging
import os
import time
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
from livekit.agents.llm import StopResponse
from restaurant.voice_stack import build_llm, build_stt, build_tts
from restaurant.menu import (
    DELIVERY_CHARGE,
    MIN_ORDER_DELIVERY,
    OPENING_HOURS,
    RESTAURANT_NAME,
    RESTAURANT_NAME_EN,
)
from restaurant import menu_provider
from restaurant.orders import OrderCart
from restaurant.phone_echo import is_likely_phone_echo
from restaurant import reservations as res_store

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger("restaurant-agent")

SYSTEM_PROMPT = f"""You are Sierra, the phone host at {RESTAURANT_NAME_EN} ({RESTAURANT_NAME}) — a Punjabi restaurant in Canada.

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
- Phone numbers: always read back digit by digit in ENGLISH (four-one-six, not ਚਾਰ-ਇੱਕ-ਛ).
- Never list the full menu unless the caller explicitly asks for it.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
NATURAL VOICE — talk like real staff on a Canadian Punjabi call
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Sound like two humans talking — Punjabi/Hindi sentence flow with English menu names where
people actually use them. Not a textbook translation.

  - Dish names: use voice_line from tool responses EXACTLY (may be English, mixed, or Gurmukhi).
  - Example: "ਹਾਂ ਜੀ, ਇੱਕ Fish Pakora — medium spicy?" NOT machhi/ਮੱਛੀ for fish dishes.
  - Example: "Chole Bhature Combo" in English inside a Punjabi sentence is natural and correct.
  - Prices, spice levels, modifiers, bread/rice choices: ALWAYS English (mild, medium, spicy,
    butter naan, extra raita). Never Gurmukhi numerals for prices or phone digits.
  - speak_as in tool data is for STT matching only — do NOT speak speak_as unless voice_line
    equals speak_as (speech_mode=gurmukhi, e.g. Gulab Jamun, Kheer).
  - Keep replies short and warm — one question at a time, like a busy counter person.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PRICES — when to mention them
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- NEVER say price when confirming an item exists, describing a dish, asking quantity, or asking modifiers.
- ONLY say price if the customer explicitly asks: "how much", "price", "kina", "cost", "kithe da".
  Then give ONE short answer in English: "That's about six dollars ji."
- The ONLY other time for money is Step E final confirmation (total/subtotal).
- Tool responses mark price as INTERNAL — never read that line aloud unless the customer asked.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SPICE LEVEL — how to ask (Canadian restaurant style)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- Ask spice ONLY if check_menu_item lists "Spice Level" in Options. Otherwise skip it.
- ALWAYS ask in English — exact words: mild, medium, or spicy.
- Good: "Mild, medium, or spicy?" or "ਹਾਂ ਜੀ — mild, medium, or spicy?"
- BAD (never use): mirchi kithe tak, ਕਿੱਥੇ ਤਕ ਮਿਰਚੀ, teekha/kam spicy in Punjabi, Gurmukhi for mild/medium/spicy.
- Do NOT combine price + spice + quantity in one turn — one question only.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
GREETING
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Your opening greeting has already been played. Do not repeat it.
Wait for the customer's first message and respond naturally.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MENU TOOLS — Clover is the source of truth
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
You do NOT know the menu from memory. The live menu comes from Clover POS (60+ items,
combos, platters, modifiers). Always use tools before naming dishes, prices, or options.

WHEN TO CALL WHICH TOOL:
  search_menu_items(query) — broad questions: "what paneer dishes?", "any combos?",
    "what's spicy?", "fish items", "family platter"
  check_menu_item(name) — one specific dish: price, veg/non-veg, modifier options,
    availability, before describing or adding
  add_to_order(name, qty, note) — only after you know quantity and required choices

RULES:
  1. Call a menu tool BEFORE quoting any dish, price, or option in this call.
  2. When speaking a dish name aloud, use voice_line from the tool response — wrap it in a
     natural Punjabi/English sentence. Do NOT default to speak_as Gurmukhi.
  3. When calling tools, use the English item name from the tool (e.g. "Butter Chicken").
  4. If a tool says [unavailable], say it is not available right now and search for an alternative.
  5. When listing search results, name at most 2–3 items, then ask which one they want.
  6. Only mention a price when the customer asks, or at final confirmation (Step E).

DESCRIBING DISHES:
  If asked what something is, call check_menu_item first. Give ONE short line (e.g. creamy
  tomato curry with chicken). Do not invent detailed ingredients. If unsure, say it is a
  popular Punjabi dish and offer to add it.

"SPICY" CALLS:
  "Spicy" usually means spice LEVEL on a dish (mild/medium/spicy), not a menu category.
  Ask which dish they want, then ask spice level if the item has a Spice Level option.
  Or search_menu_items("tikka") / search_menu_items("curry") — not search_menu_items("spicy").

COMBOS AND PLATTERS:
  Combos (Thali, Chole Bhature Combo, Family Platter) are ONE line item — do not split into
  separate curries unless the customer asks. check_menu_item shows required choices such as
  Choose Curry, Combo Drink, or Lassi Size — collect ALL required choices before add_to_order.

MODIFIERS (until kitchen integration):
  check_menu_item lists Options (Spice Level, Bread Choice, Rice Side, Add Extras, etc.).
  Ask ONE modifier question at a time. Put ALL choices in the note field:
  note="medium spicy, butter naan, extra raita" or note="large lassi, mango lassi combo drink".

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FOOD ORDER FLOW  ← follow this sequence exactly
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

STEP A — COLLECT ITEMS (repeat until customer says done)

  A1. Customer names or asks about an item.
      If vague → search_menu_items. If specific → check_menu_item.
      If quantity was not stated, ask: "How many?"

  A2. Read modifier groups from check_menu_item response. Ask only what applies:
      - Spice Level → ONLY if listed in Options. Ask in English: "Mild, medium, or spicy?"
      - Choose Curry / Choose Non-Veg Curry / Combo Drink / Lassi Size → REQUIRED if listed;
        ask before add_to_order.
      - Bread Choice, Rice Side, Add Extras, Bhatura Count → ask if customer wants them;
        one question at a time.
      - No options listed → skip to A3.
      - Never mention price in this step.

  A3. Call add_to_order(item_name, quantity, note=...).
      Put spice level and all modifier choices in note. Wait for tool return before confirming.

  A4. Confirm using voice_line from the tool (natural code-mix OK):
      "Got it — 1x [voice_line] [choices in English if any]."
      If tool error or not on menu → search_menu_items for closest match.

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
  D3. Read back digit by digit in ENGLISH ONLY: "So that's four-one-six, five-five-five,
      one-two-three-four — is that right?"
  D4. After they confirm the phone number, call set_customer_info(name, phone).
      Do NOT call set_customer_info until you have BOTH name AND phone confirmed.

STEP E — FINAL CONFIRMATION (once only, never before this step)

  E1. Call get_order_summary() to get the full order data.
  E2. Read back the summary naturally using voice_line for each dish:
      "Okay [Name] ji — [items with voice_line names and English modifier choices], [pickup/delivery],
       total about $[amount in English]. [Any special instructions from step B.] All good?"
      Totals are estimates from the cart; payment is at pickup/delivery (no card on phone).
  E3. Customer says yes → call place_order().
      Then say warmly: pickup ready in 20–25 minutes, delivery in 35–45 minutes.
  E4. Customer wants a change → fix it → go back to E1.

CHANGING ITEMS MID-ORDER
  Remove: call remove_from_order(item_name) and confirm the removal.
  Change choices or quantity: call remove_from_order, then add_to_order again.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TABLE RESERVATIONS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Collect one at a time: date → time → party size.
Call check_table_availability(date, time, party_size).
  If available: collect name and phone → call book_reservation → give reference number.
  If not available: "That slot is full ji — would [earlier time] or [later time] work?"
Confirm phone digit by digit once. Same transfer rules apply.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RESTAURANT INFORMATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Name: {RESTAURANT_NAME_EN} ({RESTAURANT_NAME})
Hours: {OPENING_HOURS}
Delivery charge: ${DELIVERY_CHARGE} (minimum order ${MIN_ORDER_DELIVERY} for delivery)
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
- Never quote a dish, price, or option without calling a menu tool first in this call.
- Never say a price unless the customer asked for it, or you are at Step E final confirmation.
- Never ask spice level in Punjabi/Hindi — always "Mild, medium, or spicy?" in English.
- Never assume spice rules by category — read Options from check_menu_item.
- Never confirm an item before add_to_order() returns successfully.
- Never call place_order() before calling get_order_summary() first.
- Never call set_customer_info() until you have BOTH name AND phone number confirmed.
- Never ask for name or phone before the complete order is collected.
- Never summarize or re-read the order except at Step E2.
- Never speak more than two sentences in one turn.
- Never invent menu items, ingredients, prices, or availability.
- Never refuse or delay when a caller asks for a human.
- Never ask for payment card details.
- Never write Punjabi or Hindi in Roman/English letters — always use Gurmukhi or Devanagari script.
"""


class RestaurantAgent(Agent):
    def __init__(self, *, is_phone: bool = False):
        super().__init__(instructions=SYSTEM_PROMPT)
        self.cart = OrderCart()
        self.is_phone = is_phone
        self._recent_agent_lines: list[str] = []
        self._phone_ignore_until: float = 0.0
        self.menu_source = menu_provider.menu_source_label()
        logger.info(f"Menu source: {self.menu_source} | phone={is_phone}")

    def note_agent_speech(self, text: str) -> None:
        line = text.strip()
        if not line:
            return
        self._recent_agent_lines.append(line)
        self._recent_agent_lines = self._recent_agent_lines[-6:]

    def begin_phone_greeting(self) -> None:
        """Mute STT turns while greeting TTS plays and tail echo fades (outbound/mobile)."""
        self._phone_ignore_until = time.monotonic() + 14.0

    def end_phone_greeting(self) -> None:
        """Short tail buffer after greeting audio finishes."""
        self._phone_ignore_until = time.monotonic() + 2.5

    async def on_user_turn_completed(self, turn_ctx, new_message) -> None:
        if not self.is_phone:
            return
        user_text = (new_message.text_content or "").strip()
        if time.monotonic() < self._phone_ignore_until:
            logger.info("Ignoring turn during post-greeting cooldown: %s", user_text)
            raise StopResponse()
        if is_likely_phone_echo(user_text, self._recent_agent_lines):
            logger.info("Ignoring phone echo turn: %s", user_text)
            raise StopResponse()

    # ── ORDER TOOLS ──────────────────────────────────────────────────────────

    @function_tool
    async def add_to_order(
        self,
        item_name: Annotated[str, "Name of the menu item in English or Punjabi"],
        quantity: Annotated[int, "How many of this item to add"],
        note: Annotated[str, "Modifier choices and special instructions e.g. 'medium spicy, butter naan'"] = "",
    ) -> str:
        """Add an item to the customer's order. Call check_menu_item first if unsure about options."""
        item = menu_provider.find_item(item_name)
        if not item:
            return f"'{item_name}' is not on our menu. Ask the customer to clarify or call search_menu_items."
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
        """Look up one menu item — veg/non-veg, modifier options, voice_line, availability. Price is internal."""
        return menu_provider.check_item(item_name)

    @function_tool
    async def search_menu_items(
        self,
        query: Annotated[str, "Search term e.g. 'paneer', 'combo', 'biryani', 'vegetarian starters'"],
    ) -> str:
        """Search the menu by keyword or category. Use for 'what X dishes do you have?' questions."""
        return menu_provider.search_menu(query)

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

    if is_phone:
        session = AgentSession(
            stt=build_stt(True),
            llm=build_llm(),
            tts=build_tts(True),
            turn_detection="stt",
            min_endpointing_delay=0.75,
            max_endpointing_delay=3.0,
            preemptive_generation=False,
            allow_interruptions=False,
            discard_audio_if_uninterruptible=True,
            aec_warmup_duration=2.0,
        )
    else:
        session = AgentSession(
            stt=build_stt(False),
            llm=build_llm(),
            tts=build_tts(False),
            turn_detection="stt",
            min_endpointing_delay=0.07,
            preemptive_generation=True,
        )

    agent = RestaurantAgent(is_phone=is_phone)

    await session.start(
        room=ctx.room,
        agent=agent,
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
                agent.note_agent_speech(text)
                logger.info(f"SIERRA: {text}")

    if is_phone:
        agent.begin_phone_greeting()

    await session.say(
        "ਸਤ ਸ੍ਰੀ ਅਕਾਲ ਜੀ! Welcome to Bizbull Restaurant, I'm Sierra. How can I help you today?",
        allow_interruptions=False,
    )

    # Outbound / mobile: wait for line echo to fade before listening for the caller.
    if is_phone:
        await asyncio.sleep(3.0)
        agent.end_phone_greeting()


if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            agent_name="restaurant-agent",
            port=int(os.getenv("AGENT_HTTP_PORT", "8081")),
        )
    )
