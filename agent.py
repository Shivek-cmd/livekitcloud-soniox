import asyncio
import json
import logging
import os
from typing import Annotated

from dotenv import load_dotenv
from livekit.agents import (
    Agent,
    JobContext,
    RoomInputOptions,
    WorkerOptions,
    cli,
    function_tool,
)
from livekit.agents.llm import StopResponse
from restaurant.session_config import build_agent_session, phone_greeting_settle_seconds
from restaurant.turn_latency import TurnLatencyTracker
from restaurant.menu import DELIVERY_CHARGE
from restaurant import menu_provider
from restaurant.conversation import (
    UserIntent,
    detect_intent,
    echo_recovery_phrase,
    sanitize_assistant_speech,
)
from restaurant.order_flow import OrderFlowController
from restaurant.orders import OrderCart
from restaurant.phone_echo import is_greeting_tail_echo, is_likely_phone_echo
from restaurant.prompts import build_system_prompt
from restaurant import reservations as res_store
from restaurant.web_sync import WebSync

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger("restaurant-agent")


class RestaurantAgent(Agent):
    def __init__(self, *, is_phone: bool = False):
        super().__init__(instructions=build_system_prompt(is_phone=is_phone))
        self.cart = OrderCart()
        self.is_phone = is_phone
        self._flow = OrderFlowController(is_phone=is_phone)
        self._recent_agent_lines: list[str] = []
        self._phone_session = None
        self._echo_reprompt_done = False
        self._greeting_echo_pending_reprompt = False
        self._echo_recovery_scheduled = False
        self._real_user_turns = 0
        self._web_sync: WebSync | None = None
        self.menu_source = menu_provider.menu_source_label()
        logger.info(f"Menu source: {self.menu_source} | phone={is_phone}")

    def bind_phone_session(self, session) -> None:
        self._phone_session = session

    def bind_web_sync(self, web_sync: WebSync) -> None:
        self._web_sync = web_sync

    async def _sync_web(self) -> None:
        """Push the current cart to the web UI (no-op on phone)."""
        if self._web_sync is not None:
            await self._web_sync.publish_order_state()

    def note_agent_speech(self, text: str) -> None:
        line = text.strip()
        if not line:
            return
        self._recent_agent_lines.append(line)
        self._recent_agent_lines = self._recent_agent_lines[-6:]

    def _schedule_echo_reprompt(self, *, greeting_only: bool = False) -> None:
        if not self.is_phone or not self._phone_session:
            return
        if greeting_only:
            if self._echo_reprompt_done:
                return
            self._echo_reprompt_done = True
        else:
            if self._echo_recovery_scheduled:
                return
            self._echo_recovery_scheduled = True
        asyncio.create_task(self._echo_reprompt(greeting_only=greeting_only))

    async def _echo_reprompt(self, *, greeting_only: bool = False) -> None:
        """Invite the caller to speak after echo — avoids dead air on phone."""
        await asyncio.sleep(1.2 if greeting_only else 0.8)
        if not self._phone_session:
            return
        if greeting_only and self._real_user_turns > 0:
            return
        line = (
            "ਹਾਂ ਜੀ — go ahead, I'm listening."
            if greeting_only
            else echo_recovery_phrase()
        )
        try:
            await self._phone_session.say(line, allow_interruptions=True)
        except Exception:
            logger.exception("Echo reprompt failed")
        finally:
            if not greeting_only:
                self._echo_recovery_scheduled = False

    def _inject_turn_guidance(self, turn_ctx, user_text: str) -> None:
        intent = detect_intent(user_text)
        plan = self._flow.build_turn_plan(user_text, intent, self.cart)
        turn_ctx.add_message(role="system", content=plan.guidance)
        logger.info("TURN_GUIDANCE intent=%s phase=%s", intent.value, self._flow.state.phase.value)

    async def on_user_turn_completed(self, turn_ctx, new_message) -> None:
        user_text = (new_message.text_content or "").strip()
        intent = detect_intent(user_text)

        if self.is_phone:
            if is_likely_phone_echo(
                user_text, self._recent_agent_lines, intent=intent
            ):
                logger.info("Ignoring phone echo turn: %s", user_text)
                if is_greeting_tail_echo(user_text):
                    self._greeting_echo_pending_reprompt = True
                    self._schedule_echo_reprompt(greeting_only=True)
                else:
                    self._schedule_echo_reprompt(greeting_only=False)
                raise StopResponse()

        if intent == UserIntent.PICKUP and not self.cart.order_type:
            self.cart.order_type = "pickup"
            self._flow.sync_from_cart(self.cart)
            await self._sync_web()
        elif intent == UserIntent.DELIVERY and not self.cart.order_type:
            self.cart.order_type = "delivery"
            self._flow.sync_from_cart(self.cart)
            await self._sync_web()

        self._real_user_turns += 1
        self._greeting_echo_pending_reprompt = False
        self._echo_recovery_scheduled = False
        self._inject_turn_guidance(turn_ctx, user_text)

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
        result = self.cart.add_item(item, quantity, note)
        self._flow.on_item_added()
        self._flow.note_discussed_item(item["name"], float(item.get("price") or 0))
        await self._sync_web()
        return result

    @function_tool
    async def remove_from_order(
        self,
        item_name: Annotated[str, "Name of the item to remove"],
    ) -> str:
        """Remove an item from the customer's order."""
        result = self.cart.remove_item(item_name)
        await self._sync_web()
        return result

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
        self._flow.sync_from_cart(self.cart)
        await self._sync_web()
        if order_type == "delivery":
            return f"Set to delivery. Delivery charge ${DELIVERY_CHARGE} will be added. Ask for delivery address."
        return "Set to pickup. Continue the order flow — read back cart before asking for name/phone."

    @function_tool
    async def set_customer_info(
        self,
        name: Annotated[str, "Customer's name"],
        phone: Annotated[str, "Customer's 10-digit phone number"],
    ) -> str:
        """Save the customer's name and phone number."""
        self.cart.customer_name = name
        self.cart.customer_phone = phone
        self._flow.sync_from_cart(self.cart)
        await self._sync_web()
        return f"Saved: {name}, {phone}."

    @function_tool
    async def set_delivery_address(
        self,
        address: Annotated[str, "Full delivery address including area and landmark"],
    ) -> str:
        """Save the delivery address for a delivery order."""
        self.cart.delivery_address = address
        self._flow.sync_from_cart(self.cart)
        await self._sync_web()
        return f"Delivery address saved: {address}."

    @function_tool
    async def get_order_summary(self) -> str:
        """Get the full current order to read back to the customer before confirming."""
        from restaurant.conversation import format_order_readback

        summary = self.cart.summary()
        readback = format_order_readback(self.cart)
        if readback:
            return f"{summary}\n\nSPOKEN READ-BACK (say exactly):\n{readback}"
        return summary

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

        eta = "30-40 min" if self.cart.order_type == "delivery" else "20-25 min"
        self.cart.mark_placed(eta=eta)
        await self._sync_web()

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
        item = menu_provider.find_item(item_name)
        if item and not item.get("unavailable"):
            price = menu_provider.item_price_dollars(item["name"])
            self._flow.note_discussed_item(item["name"], price)
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

    session = build_agent_session(is_phone=is_phone)
    channel = "phone" if is_phone else "web"
    TurnLatencyTracker(channel=channel).attach(session)

    agent = RestaurantAgent(is_phone=is_phone)
    if is_phone:
        agent.bind_phone_session(session)

    await session.start(
        room=ctx.room,
        agent=agent,
        room_input_options=RoomInputOptions(),
    )

    # Web channel: register cart RPCs + push live order state to the browser.
    if not is_phone:
        web_sync = WebSync(ctx.room, agent)
        web_sync.register()
        agent.bind_web_sync(web_sync)
        await web_sync.publish_order_state()

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
                cleaned = sanitize_assistant_speech(
                    text,
                    allow_greeting=agent._real_user_turns == 0,
                )
                if cleaned != text:
                    logger.warning("Mid-call re-greeting blocked in log: %s", text[:80])
                agent.note_agent_speech(text)
                logger.info(f"SIERRA: {text}")

    await session.say(
        "ਸਤ ਸ੍ਰੀ ਅਕਾਲ ਜੀ! Welcome to Bizbull Restaurant, I'm Sierra. How can I help you today?",
        allow_interruptions=False,
    )

    # Let greeting echo fade on mobile/outbound before listening for the caller.
    if is_phone:
        await asyncio.sleep(phone_greeting_settle_seconds())
        if agent._greeting_echo_pending_reprompt and agent._real_user_turns == 0:
            agent._echo_reprompt_done = True
            await session.say(
                "ਹਾਂ ਜੀ — go ahead, I'm listening.",
                allow_interruptions=True,
            )


if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            agent_name="restaurant-agent",
            port=int(os.getenv("AGENT_HTTP_PORT", "8081")),
        )
    )
