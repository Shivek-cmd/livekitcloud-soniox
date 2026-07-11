import asyncio
import json
import logging
import os
import re
from collections import deque
from typing import Annotated

from dotenv import load_dotenv
from livekit.agents import (
    Agent,
    JobContext,
    WorkerOptions,
    cli,
    function_tool,
)
from livekit.agents.llm import StopResponse
from restaurant.session_config import (
    build_agent_session,
    build_room_options,
    phone_background_filter_enabled,
    phone_greeting_settle_seconds,
)
from restaurant.turn_latency import TurnLatencyTracker
from restaurant.menu import DELIVERY_CHARGE
from restaurant import menu_provider
from restaurant.conversation import (
    ALLERGIES_QUESTION,
    OPENING_GREETING,
    PICKUP_DELIVERY_QUESTION,
    UserIntent,
    background_repeat_phrase,
    confirm_items_added,
    detect_intent,
    echo_recovery_phrase,
    extract_browse_query,
    format_browse_reply,
    format_availability_reply,
    format_order_readback,
    format_order_status,
    is_allergies_step_answer,
    is_availability_question,
    is_category_browse_query,
    is_confirm_yes,
    is_likely_pickup_stt,
    is_quantity_correction,
    is_readback_ack,
    is_readback_all_clear,
    is_want_to_order_only,
    order_placed_goodbye,
    phrase_anything_else,
    phrase_ask_phone,
    phrase_name_for_order,
    phrase_phone_saved,
    phrase_repeat_request,
    resolve_intent,
    sanitize_assistant_speech,
)
from restaurant.customer_info import (
    extract_phone_digits,
    format_phone_spoken,
    is_valid_customer_name,
    looks_like_phone_utterance,
    parse_customer_name,
)
from restaurant.order_flow import (
    COLLECTING_PHASES,
    OrderFlowController,
    OrderPhase,
    is_collecting_phase,
)
from restaurant.order_parse import auto_add_candidates, parse_order_lines
from restaurant.stt_noise import (
    agent_recently_asked_quantity,
    is_likely_stt_noise,
    parse_standalone_quantity,
)
from restaurant.orders import OrderCart
from restaurant.phone_echo import is_greeting_tail_echo, is_likely_phone_echo
from restaurant.phone_background import is_likely_background_speech
from restaurant.prompts import build_system_prompt
from restaurant import reservations as res_store
from restaurant.web_sync import WebSync
from restaurant.ambient_audio import build_ambient_player, start_ambient, stop_ambient
from restaurant.session_recorder import SessionRecorder
from restaurant.analytics_store import persist_session
from restaurant.call_control import hangup_after_order_enabled, schedule_call_hangup
from restaurant.llm_warmup import schedule_llm_warmup
from restaurant.clover.order_submit import clover_submit_enabled

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger("restaurant-agent")

_AUTO_ADD_PHASES = frozenset(
    {
        OrderPhase.BROWSING,
        OrderPhase.COLLECTING_ITEMS,
        OrderPhase.AWAITING_MORE,
    }
)


def _add_clarify_min_conf() -> float:
    """Below this match confidence, add_to_order asks 'did you mean X?' instead
    of silently adding a possibly-misheard dish. Above the abstain floor (0.55)
    but below the auto-add gate (0.8)."""
    try:
        return float(os.getenv("ADD_CLARIFY_MIN_CONF", "0.7"))
    except ValueError:
        return 0.7


_ADD_CLARIFY_MIN_CONF = _add_clarify_min_conf()


def _menu_browse_enabled() -> bool:
    return os.getenv("MENU_BROWSE_ENABLED", "1").strip().lower() not in (
        "0",
        "false",
        "no",
    )


class RestaurantAgent(Agent):
    def __init__(self, *, is_phone: bool = False):
        super().__init__(instructions=build_system_prompt(is_phone=is_phone))
        self.cart = OrderCart()
        self.is_phone = is_phone
        self._flow = OrderFlowController(is_phone=is_phone)
        self._session = None
        self._recent_agent_lines: list[str] = []
        self._echo_reprompt_done = False
        self._greeting_echo_pending_reprompt = False
        self._echo_recovery_scheduled = False
        self._real_user_turns = 0
        self._background_ignore_streak = 0
        self._background_reprompt_done = False
        self._web_sync: WebSync | None = None
        self._recorder: SessionRecorder | None = None
        self._job_ctx: JobContext | None = None
        self._hangup_started = False
        self._goodbye_spoken = False
        self.menu_source = menu_provider.menu_source_label()
        logger.info(f"Menu source: {self.menu_source} | phone={is_phone}")

    def bind_session(self, session) -> None:
        self._session = session

    def bind_phone_session(self, session) -> None:
        """Backward-compatible alias."""
        self.bind_session(session)

    def bind_web_sync(self, web_sync: WebSync) -> None:
        self._web_sync = web_sync

    def bind_recorder(self, recorder: SessionRecorder) -> None:
        self._recorder = recorder

    def bind_job_context(self, job_ctx: JobContext) -> None:
        self._job_ctx = job_ctx

    def _channel_label(self) -> str:
        return "phone" if self.is_phone else "web"

    def _record_tool(self, name: str, args: dict, result: str) -> None:
        if self._recorder is not None:
            self._recorder.log_tool(name, args, result)

    def _cart_snapshot(self) -> dict:
        return self.cart.to_state_dict()

    async def _sync_web(self) -> None:
        """Push the current cart to the web UI (no-op on phone)."""
        if self._web_sync is not None:
            await self._web_sync.publish_order_state()

    def _speech_in_flight(self) -> bool:
        """True if the session is currently speaking/about to speak (PR 042).

        Guards fire-and-forget speech (filler, echo/background reprompt) so
        it never queues behind — and blends into — the main turn reply.
        """
        if not self._session:
            return False
        handle = self._session.current_speech
        return handle is not None and not handle.done()

    def note_agent_speech(self, text: str) -> None:
        line = text.strip()
        if not line:
            return
        self._recent_agent_lines.append(line)
        self._recent_agent_lines = self._recent_agent_lines[-6:]

    def _schedule_echo_reprompt(self, *, greeting_only: bool = False) -> None:
        if not self.is_phone or not self._session:
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

    async def _background_reprompt(self) -> None:
        if not self.is_phone or not self._session:
            return
        await asyncio.sleep(0.6)
        if not self._session or self._speech_in_flight():
            return
        try:
            await self._session.say(
                background_repeat_phrase(),
                allow_interruptions=True,
            )
        except Exception:
            logger.exception("Background reprompt failed")

    def _schedule_background_reprompt(self) -> None:
        if not self.is_phone or self._background_reprompt_done:
            return
        self._background_reprompt_done = True
        asyncio.create_task(self._background_reprompt())

    async def _echo_reprompt(self, *, greeting_only: bool = False) -> None:
        """Invite the caller to speak after echo — avoids dead air on phone."""
        await asyncio.sleep(1.2 if greeting_only else 0.8)
        if not self._session or self._speech_in_flight():
            return
        if greeting_only and self._real_user_turns > 0:
            return
        line = (
            "ਹਾਂ ਜੀ — go ahead, I'm listening."
            if greeting_only
            else echo_recovery_phrase()
        )
        try:
            await self._session.say(line, allow_interruptions=True)
        except Exception:
            logger.exception("Echo reprompt failed")
        finally:
            if not greeting_only:
                self._echo_recovery_scheduled = False

    async def _try_auto_add(
        self,
        turn_ctx,
        user_text: str,
        intent: UserIntent,
    ) -> None:
        """Code-owned add when speech parses cleanly — single or multi item."""
        if self._flow.state.phase not in _AUTO_ADD_PHASES:
            return
        if intent != UserIntent.ADD_ITEM or is_want_to_order_only(user_text):
            return
        # A quantity correction ("I said one, not two") must NOT be auto-added —
        # add_item is additive and would double it. Let the LLM route it to
        # update_item_quantity (steered by the correction guidance).
        if is_quantity_correction(user_text):
            return

        lines = auto_add_candidates(user_text)
        if not lines:
            return

        entries: list[tuple[int, str]] = []
        for line in lines:
            result = self.cart.add_item(line.item, line.quantity)
            if "not available" in result.lower():
                return
            self._flow.on_item_added()
            price = float(line.item.get("price") or (line.item.get("price_cents", 0) / 100))
            self._flow.note_discussed_item(line.item["name"], price)
            voice = (
                line.item.get("voice_line")
                or line.item.get("speak_as")
                or line.item["name"]
            )
            entries.append((line.quantity, voice))

        await self._sync_web()
        lang = self._flow.state.preferred_language
        confirm = confirm_items_added(entries, lang)
        follow = phrase_anything_else(lang)
        say_line = f"{confirm} {follow}"

        turn_ctx.add_message(
            role="system",
            content=f'[AUTO-ADD] Items saved. Already spoken: "{say_line}"',
        )
        logger.info("AUTO_ADD items=%s qty=%s", [e[1] for e in entries], [e[0] for e in entries])

        if self._recorder is not None:
            self._recorder.complete_turn(
                intent=intent.value,
                phase=self._flow.state.phase.value,
                auto_add=True,
                cart_snapshot=self._cart_snapshot(),
            )

        if self._session:
            await self._session.say(say_line, allow_interruptions=True)
            self.note_agent_speech(say_line)
        raise StopResponse()

    async def _try_quantity_reply(
        self,
        turn_ctx,
        user_text: str,
    ) -> None:
        """Set quantity when caller answers a prior 'how many' — never additive."""
        if self._flow.state.phase not in _AUTO_ADD_PHASES:
            return
        qty = parse_standalone_quantity(user_text)
        if qty is None:
            return
        if not agent_recently_asked_quantity(self._recent_agent_lines):
            return
        if not self.cart.items:
            return

        item = self.cart.items[-1]
        self.cart.update_item_quantity(item.name, qty)
        self._flow.sync_from_cart(self.cart)
        await self._sync_web()

        lang = self._flow.state.preferred_language
        voice = item.voice_line or item.name
        confirm = confirm_items_added([(qty, voice)], lang)
        follow = phrase_anything_else(lang)
        say_line = f"{confirm} {follow}"

        turn_ctx.add_message(
            role="system",
            content=f'[QTY-REPLY] Set {item.name} qty={qty}. Already spoken: "{say_line}"',
        )
        logger.info("QTY_REPLY item=%s qty=%s", item.name, qty)

        if self._session:
            await self._session.say(say_line, allow_interruptions=True)
            self.note_agent_speech(say_line)
        raise StopResponse()

    async def _try_menu_browse(
        self,
        turn_ctx,
        user_text: str,
        intent: UserIntent,
    ) -> None:
        """Code-owned category/family browse — list options, never add to cart."""
        if not _menu_browse_enabled():
            return
        if intent in (UserIntent.HUMAN, UserIntent.ASK_ORDER_STATUS, UserIntent.ASK_PRICE):
            return
        if intent == UserIntent.ADD_ITEM:
            return
        if not is_category_browse_query(user_text):
            return
        if not (
            is_collecting_phase(self._flow.state.phase)
            or intent == UserIntent.ASK_AVAILABILITY
            or intent == UserIntent.GENERAL
        ):
            return

        query = extract_browse_query(user_text) or user_text.strip()
        topic, options = menu_provider.browse_menu_options(query)
        if not options:
            return

        lang = self._flow.state.preferred_language
        say_line = format_browse_reply(options, lang, topic=topic)
        tool_text = menu_provider.browse_menu(query)

        turn_ctx.add_message(
            role="system",
            content=f'[MENU_BROWSE] Already spoken: "{say_line}"\n{tool_text}',
        )
        self._flow.note_browse_topic(topic or query)
        logger.info("MENU_BROWSE topic=%s options=%s", topic, [o["name"] for o in options[:2]])

        if self._recorder is not None:
            self._recorder.complete_turn(
                intent=intent.value,
                phase=self._flow.state.phase.value,
                cart_snapshot=self._cart_snapshot(),
            )

        if self._session:
            await self._session.say(say_line, allow_interruptions=True)
            self.note_agent_speech(say_line)
        raise StopResponse()

    async def _try_answer_item_availability(
        self,
        turn_ctx,
        user_text: str,
        intent: UserIntent,
    ) -> None:
        """Code-owned yes/no when caller asks if one specific dish is available."""
        if not _menu_browse_enabled():
            return
        if intent in (UserIntent.HUMAN, UserIntent.ASK_ORDER_STATUS, UserIntent.ASK_PRICE):
            return
        if intent == UserIntent.ADD_ITEM:
            return
        if is_category_browse_query(user_text):
            return
        if not is_availability_question(user_text):
            return

        item = menu_provider.resolve_item_dict_from_text(user_text)
        if not item:
            return

        lang = self._flow.state.preferred_language
        say_line = format_availability_reply(item, lang)
        self._flow.note_discussed_item(item["name"], float(item.get("price") or 0))

        turn_ctx.add_message(
            role="system",
            content=f'[ITEM_AVAIL] Already spoken: "{say_line}"',
        )
        logger.info("ITEM_AVAIL item=%s available=%s", item["name"], not item.get("unavailable"))

        if self._recorder is not None:
            self._recorder.complete_turn(
                intent=intent.value,
                phase=self._flow.state.phase.value,
                cart_snapshot=self._cart_snapshot(),
            )

        if self._session:
            await self._session.say(say_line, allow_interruptions=True)
            self.note_agent_speech(say_line)
        raise StopResponse()

    async def _try_reject_stt_noise(
        self,
        turn_ctx,
        user_text: str,
        intent: UserIntent,
    ) -> None:
        """Ignore TV/background transcripts — ask caller to repeat."""
        if self._flow.state.phase not in _AUTO_ADD_PHASES:
            return
        if intent not in (UserIntent.ADD_ITEM, UserIntent.GENERAL, UserIntent.UNCLEAR):
            return
        if not is_likely_stt_noise(user_text):
            return
        if auto_add_candidates(user_text):
            return

        lang = self._flow.state.preferred_language
        line = phrase_repeat_request(lang)
        turn_ctx.add_message(
            role="system",
            content=f'[STT_NOISE] Ignored background-like transcript. Already spoken: "{line}"',
        )
        logger.info("STT_NOISE rejected turn: %s", user_text[:80])
        await self._ladder_say(turn_ctx, line, tag="STT_NOISE")
        raise StopResponse()

    async def _ladder_say(self, turn_ctx, line: str, *, tag: str = "LADDER") -> None:
        turn_ctx.add_message(
            role="system",
            content=f'[{tag}] Fixed phrase already spoken: "{line}"',
        )
        if self._session:
            await self._session.say(line, allow_interruptions=True)
            self.note_agent_speech(line)

    async def _try_answer_order_status(
        self,
        turn_ctx,
        user_text: str,
        intent: UserIntent,
    ) -> None:
        """Code-owned answer for 'what's my order' — grounded in real cart
        data at any phase. Never let the LLM improvise this from memory
        (PR 042) — that is how it hallucinates items the customer never
        ordered.
        """
        if intent != UserIntent.ASK_ORDER_STATUS:
            return
        status = format_order_status(self.cart, include_price=not self.is_phone)
        await self._ladder_say(turn_ctx, status, tag="ORDER_STATUS")
        raise StopResponse()

    def _fast_forward_checkout(self) -> None:
        """Caller jumped ahead (e.g. straight to 'pickup') while still adding.

        Only mark item-collection done — NEVER silently mark allergies as
        asked/answered. Skipping the allergies step here was the root cause of
        'sometimes it never asks about allergies': the flow still owes the
        customer that question, so we let the checklist surface it instead."""
        if not self._flow.state.items_complete:
            self._flow.mark_items_complete()

    async def _speak_order_readback_if_due(self, turn_ctx) -> bool:
        """Code-owned English read-back — returns True if spoken."""
        if self._flow.state.readback_spoken or not self.cart.order_type:
            return False
        if not self._flow.state.items_complete or not self._flow.state.special_instructions_done:
            return False
        readback = format_order_readback(self.cart, include_price=not self.is_phone)
        if not readback:
            return False
        self._flow.mark_readback_spoken()
        await self._ladder_say(turn_ctx, readback)
        return True

    async def _try_run_checkout_ladder(
        self,
        turn_ctx,
        user_text: str,
        intent: UserIntent,
    ) -> None:
        """Code-owned checkout anchors — the accuracy-critical, must-not-skip
        steps (grounded read-back, order-type capture, name hand-off). Everything
        conversational is led by the LLM via the per-turn checklist; this only
        fires for the transitions that must be exact. `phase` is re-read after
        every state change so a later branch never acts on a stale phase."""
        phase = self._flow.state.phase
        lang = self._flow.state.preferred_language
        cart = self.cart

        if cart.placed:
            return

        # Phone before name — redirect to name step.
        if (
            looks_like_phone_utterance(user_text)
            and phase != OrderPhase.CUSTOMER_PHONE
            and not cart.customer_name
        ):
            if not self._flow.state.readback_confirmed:
                return
            self._flow.sync_from_cart(cart)
            phase = self._flow.state.phase
            await self._sync_web()
            await self._ladder_say(turn_ctx, phrase_name_for_order(lang))
            raise StopResponse()

        # Done ordering → allergies (English) — once only.
        if phase == OrderPhase.AWAITING_MORE and intent == UserIntent.ORDER_DONE:
            if cart.is_empty:
                return
            self._flow.mark_items_complete()
            self._flow.sync_from_cart(cart)
            phase = self._flow.state.phase
            await self._sync_web()
            if not self._flow.state.allergies_asked:
                self._flow.mark_allergies_asked()
                await self._ladder_say(turn_ctx, ALLERGIES_QUESTION)
                raise StopResponse()
            if not self._flow.state.special_instructions_done:
                return
            if not cart.order_type:
                await self._ladder_say(turn_ctx, PICKUP_DELIVERY_QUESTION)
                raise StopResponse()

        # Allergies answered → pickup/delivery (English).
        if phase == OrderPhase.SPECIAL_INSTRUCTIONS and (
            is_allergies_step_answer(user_text, intent)
            or (intent == UserIntent.CONFIRM_YES and is_confirm_yes(user_text))
        ):
            if not self._flow.state.allergies_asked:
                self._flow.mark_allergies_asked()
            self._flow.mark_special_instructions_done()
            self._flow.sync_from_cart(cart)
            phase = self._flow.state.phase
            await self._sync_web()
            if not cart.order_type:
                await self._ladder_say(turn_ctx, PICKUP_DELIVERY_QUESTION)
                raise StopResponse()

        # LLM read-back early — caller confirms → ask name (skip re-read).
        if (
            phase
            in (
                OrderPhase.ORDER_TYPE,
                OrderPhase.READBACK,
            )
            and self._flow.state.items_complete
            and cart.order_type
            and self._flow.state.readback_spoken
            and not self._flow.state.readback_confirmed
            and (intent == UserIntent.CONFIRM_YES or is_confirm_yes(user_text))
        ):
            self._flow.mark_readback_confirmed()
            self._flow.sync_from_cart(cart)
            phase = self._flow.state.phase
            await self._sync_web()
            await self._ladder_say(turn_ctx, phrase_name_for_order(lang))
            raise StopResponse()

        # Read-back ack — ਚੈਕੋ / no problem / all clear.
        if (
            phase == OrderPhase.READBACK
            and not self._flow.state.readback_confirmed
            and (
                is_readback_ack(user_text)
                or is_readback_all_clear(user_text)
            )
        ):
            if not self._flow.state.readback_spoken:
                await self._speak_order_readback_if_due(turn_ctx)
            self._flow.mark_readback_spoken()
            self._flow.mark_readback_confirmed()
            self._flow.sync_from_cart(cart)
            phase = self._flow.state.phase
            await self._sync_web()
            await self._ladder_say(turn_ctx, phrase_name_for_order(lang))
            raise StopResponse()

        # Pickup/delivery → read-back.
        if phase == OrderPhase.ORDER_TYPE and (
            intent == UserIntent.DELIVERY
            or intent == UserIntent.PICKUP
            or is_likely_pickup_stt(user_text)
        ):
            if intent == UserIntent.DELIVERY:
                cart.order_type = "delivery"
            else:
                cart.order_type = "pickup"
            self._flow.sync_from_cart(cart)
            phase = self._flow.state.phase
            await self._sync_web()
            if cart.order_type == "delivery" and not cart.delivery_address:
                return
            readback = format_order_readback(cart, include_price=not self.is_phone)
            if readback:
                self._flow.mark_readback_spoken()
                await self._ladder_say(turn_ctx, readback)
                raise StopResponse()

        # Recover: pickup/delivery while still collecting (LLM went off-script).
        if (
            phase == OrderPhase.AWAITING_MORE
            and intent in (UserIntent.PICKUP, UserIntent.DELIVERY)
            and not cart.is_empty
        ):
            self._fast_forward_checkout()
            cart.order_type = "pickup" if intent == UserIntent.PICKUP else "delivery"
            self._flow.sync_from_cart(cart)
            phase = self._flow.state.phase
            await self._sync_web()
            if cart.order_type == "delivery" and not cart.delivery_address:
                return
            # Never read the order back before allergies were actually asked —
            # let the checklist surface allergies first (no silent skip).
            if not self._flow.state.special_instructions_done:
                return
            readback = format_order_readback(cart, include_price=not self.is_phone)
            if readback:
                self._flow.mark_readback_spoken()
                await self._ladder_say(turn_ctx, readback)
                raise StopResponse()

        # Read-back yes → ask name (never phone first).
        if phase == OrderPhase.READBACK and not self._flow.state.readback_confirmed:
            if (
                intent == UserIntent.CONFIRM_YES
                or is_confirm_yes(user_text)
                or is_readback_ack(user_text)
                or is_readback_all_clear(user_text)
            ):
                if not self._flow.state.readback_spoken:
                    await self._speak_order_readback_if_due(turn_ctx)
                self._flow.mark_readback_spoken()
                self._flow.mark_readback_confirmed()
                self._flow.sync_from_cart(cart)
                phase = self._flow.state.phase
                await self._sync_web()
                await self._ladder_say(turn_ctx, phrase_name_for_order(lang))
                raise StopResponse()

        # Missing read-back — LLM set pickup via tool without speaking read-back.
        if (
            phase == OrderPhase.READBACK
            and cart.order_type
            and not self._flow.state.readback_spoken
        ):
            if await self._speak_order_readback_if_due(turn_ctx):
                raise StopResponse()

        # Recover: confirm yes after off-script read-back at awaiting_more.
        if (
            phase == OrderPhase.AWAITING_MORE
            and cart.order_type
            and not cart.is_empty
            and (intent == UserIntent.CONFIRM_YES or is_confirm_yes(user_text))
        ):
            self._fast_forward_checkout()
            self._flow.sync_from_cart(cart)
            phase = self._flow.state.phase
            # Allergies still owed → surface it before confirming/read-back.
            if not self._flow.state.special_instructions_done:
                return
            self._flow.mark_readback_spoken()
            self._flow.mark_readback_confirmed()
            self._flow.sync_from_cart(cart)
            phase = self._flow.state.phase
            await self._sync_web()
            await self._ladder_say(turn_ctx, phrase_name_for_order(lang))
            raise StopResponse()

    def _ready_for_contact_capture(self) -> bool:
        return (
            self._flow.state.items_complete
            and not self.cart.is_empty
            and not self.cart.placed
        )

    async def _try_capture_customer_info(
        self,
        turn_ctx,
        user_text: str,
        intent: UserIntent,
    ) -> None:
        """Code-owned name/phone capture — works regardless of phase label."""
        if not self._ready_for_contact_capture():
            return

        if intent in (UserIntent.PICKUP, UserIntent.DELIVERY):
            return

        lang = self._flow.state.preferred_language

        if not self.cart.customer_name:
            if not self._flow.state.readback_confirmed:
                return

            name = parse_customer_name(user_text)
            if name and is_valid_customer_name(name):
                self.cart.customer_name = name
                self._flow.sync_from_cart(self.cart)
                await self._sync_web()
                ask_phone = phrase_ask_phone(lang, name)
                turn_ctx.add_message(
                    role="system",
                    content=(
                        f'[CAPTURE] Name saved exactly: "{name}". '
                        f'Already spoken: "{ask_phone}"'
                    ),
                )
                logger.info("CAPTURE name=%s", name)
                if self._session:
                    await self._session.say(ask_phone, allow_interruptions=True)
                    self.note_agent_speech(ask_phone)
                raise StopResponse()

            digits_only = extract_phone_digits(user_text)
            if digits_only:
                await self._ladder_say(
                    turn_ctx,
                    phrase_name_for_order(lang),
                    tag="CAPTURE",
                )
                raise StopResponse()
            return

        if not is_valid_customer_name(self.cart.customer_name or ""):
            self.cart.customer_name = ""
            self._flow.sync_from_cart(self.cart)
            await self._sync_web()
            await self._ladder_say(
                turn_ctx,
                phrase_name_for_order(lang),
                tag="CAPTURE",
            )
            raise StopResponse()

        if not self.cart.customer_phone:
            digits = extract_phone_digits(user_text)
            if not digits:
                return
            self.cart.customer_phone = digits
            self._flow.sync_from_cart(self.cart)
            await self._sync_web()
            spoken = format_phone_spoken(digits)
            saved = phrase_phone_saved(lang, spoken)
            turn_ctx.add_message(
                role="system",
                content=(
                    f'[CAPTURE] Phone saved: {digits}. '
                    f'Read back used English digits only: "{spoken}". '
                    f'Already spoken: "{saved}"'
                ),
            )
            logger.info("CAPTURE phone=%s spoken=%s", digits, spoken)
            if self._session:
                await self._session.say(saved, allow_interruptions=True)
                self.note_agent_speech(saved)
            ready, _ = self.cart.ready_to_place()
            if ready:
                await self._execute_place_order(from_capture=True, turn_ctx=turn_ctx)
            raise StopResponse()

    def _inject_turn_guidance(self, turn_ctx, user_text: str) -> None:
        intent = resolve_intent(user_text, phase=self._flow.state.phase.value)
        plan = self._flow.build_turn_plan(user_text, intent, self.cart)
        turn_ctx.add_message(role="system", content=plan.guidance)
        logger.info(
            "TURN_GUIDANCE intent=%s phase=%s lang=%s",
            intent.value,
            self._flow.state.phase.value,
            self._flow.state.preferred_language.value,
        )

    async def on_user_turn_completed(self, turn_ctx, new_message) -> None:
        user_text = (new_message.text_content or "").strip()
        intent = resolve_intent(user_text, phase=self._flow.state.phase.value)

        if self.is_phone:
            if is_likely_phone_echo(
                user_text, self._recent_agent_lines, intent=intent.value
            ):
                logger.info("Ignoring phone echo turn: %s", user_text)
                if self._recorder is not None:
                    if self._recorder.current_turn is None:
                        self._recorder.begin_user_turn(user_text)
                    self._recorder.mark_filtered("echo")
                # Only one post-greeting reprompt — never speak again on echo (avoids loop).
                if (
                    is_greeting_tail_echo(user_text)
                    and not self._echo_reprompt_done
                ):
                    self._greeting_echo_pending_reprompt = True
                    self._schedule_echo_reprompt(greeting_only=True)
                raise StopResponse()

            if is_likely_background_speech(
                user_text,
                intent.value,
                enabled=phone_background_filter_enabled(),
                phase=self._flow.state.phase.value,
            ):
                logger.info("Ignoring phone background turn: %s", user_text)
                if self._recorder is not None:
                    if self._recorder.current_turn is None:
                        self._recorder.begin_user_turn(user_text)
                    self._recorder.mark_filtered("background")
                self._background_ignore_streak += 1
                if self._background_ignore_streak >= 3:
                    self._schedule_background_reprompt()
                raise StopResponse()

        if intent == UserIntent.PICKUP and not self.cart.order_type:
            if self._flow.state.phase == OrderPhase.ORDER_TYPE:
                self.cart.order_type = "pickup"
                self._flow.sync_from_cart(self.cart)
                await self._sync_web()
        elif intent == UserIntent.DELIVERY and not self.cart.order_type:
            if self._flow.state.phase == OrderPhase.ORDER_TYPE:
                self.cart.order_type = "delivery"
                self._flow.sync_from_cart(self.cart)
                await self._sync_web()

        self._real_user_turns += 1
        self._greeting_echo_pending_reprompt = False
        self._echo_recovery_scheduled = False
        self._background_ignore_streak = 0

        self._flow.note_customer_language(user_text)
        # Code-owned handlers run first and raise StopResponse only when they
        # actually ground/capture something (order status, the exact read-back,
        # name/phone, a standalone quantity, a clean multi-item add). If none of
        # them fully handled the turn, the LLM leads the reply — and now ALWAYS
        # with the per-turn checklist as context, in collecting AND checkout.
        # This is what makes the agent flexible and human instead of a muted,
        # canned-line script during checkout.
        await self._try_answer_order_status(turn_ctx, user_text, intent)
        await self._try_run_checkout_ladder(turn_ctx, user_text, intent)
        await self._try_capture_customer_info(turn_ctx, user_text, intent)
        await self._try_reject_stt_noise(turn_ctx, user_text, intent)
        await self._try_quantity_reply(turn_ctx, user_text)
        await self._try_menu_browse(turn_ctx, user_text, intent)
        await self._try_answer_item_availability(turn_ctx, user_text, intent)
        await self._try_auto_add(turn_ctx, user_text, intent)

        self._inject_turn_guidance(turn_ctx, user_text)

        if self._recorder is not None:
            self._recorder.complete_turn(
                intent=intent.value,
                phase=self._flow.state.phase.value,
                cart_snapshot=self._cart_snapshot(),
            )

    # ── ORDER TOOLS ──────────────────────────────────────────────────────────

    @function_tool
    async def add_to_order(
        self,
        item_name: Annotated[str, "Name of the menu item in English or Punjabi"],
        quantity: Annotated[int, "How many of this item to add"],
        note: Annotated[str, "Modifier choices and special instructions e.g. 'medium spicy, butter naan'"] = "",
    ) -> str:
        """Add one menu item. Works at ANY point in the call — if the customer
        adds a dish after checkout has begun, add it and the system re-reads the
        updated order before placing. If customer listed several dishes, call
        once per item in the same turn."""
        lookup = menu_provider.extract_dish_query(item_name) or item_name
        item = menu_provider.find_item(lookup)
        if not item:
            # The strict matcher abstained. If the word maps to several real
            # dishes (e.g. "fish" -> Fish Curry / Fish Pakora), ASK which one —
            # never let the model pick or invent dishes the caller didn't name.
            options = menu_provider.disambiguation_options(lookup)
            if len(options) >= 2:
                names = ", ".join(o["name"] for o in options)
                return (
                    f'"{item_name}" could be more than one dish: {names}. '
                    "Ask the customer which ONE they want — do NOT add anything, "
                    "do NOT pick for them, and do NOT add more than one dish."
                )
            if len(options) == 1:
                return (
                    f'Did the customer mean "{options[0]["name"]}"? '
                    "Confirm with a quick yes/no before adding — do NOT add yet."
                )
            return f"'{item_name}' is not on our menu. Ask the customer to clarify or call search_menu_items."

        # Uncertain match → confirm before adding rather than guessing the dish.
        confidence = float(item.get("match_confidence", 1.0))
        if confidence < _ADD_CLARIFY_MIN_CONF:
            return (
                f'Not fully sure — did the customer mean "{item["name"]}"? '
                "Ask a quick one-line yes/no to confirm before adding; do NOT add yet."
            )

        # Never add a quantity the caller didn't actually say.
        if not isinstance(quantity, int) or quantity < 1:
            quantity = 1

        was_checkout = not is_collecting_phase(self._flow.state.phase)
        result = self.cart.add_item(item, quantity, note)
        self._flow.on_item_added()
        if was_checkout:
            # New dish mid-checkout: the previous read-back is now stale.
            self._flow.reopen_after_add()
        self._flow.note_discussed_item(item["name"], float(item.get("price") or 0))
        await self._sync_web()
        self._record_tool("add_to_order", {"item_name": item_name, "quantity": quantity, "note": note}, result)
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
    async def update_item_quantity(
        self,
        item_name: Annotated[str, "Name of the item already in the order"],
        quantity: Annotated[int, "The CORRECT total quantity for this item (not an amount to add)"],
    ) -> str:
        """Correct the quantity of an item already in the order.

        Use this — never add_to_order — when the customer corrects a quantity
        you already have (e.g. "I said one, not two", "make that three").
        add_to_order is additive and would compound the mistake instead of
        fixing it. quantity=0 removes the item.
        """
        result = self.cart.update_item_quantity(item_name, quantity)
        await self._sync_web()
        self._record_tool(
            "update_item_quantity", {"item_name": item_name, "quantity": quantity}, result
        )
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
            if self.is_phone:
                return (
                    "Set to delivery. INTERNAL: delivery charge applies. "
                    "Ask for delivery address. Do NOT mention price unless customer asked."
                )
            return f"Set to delivery. Delivery charge ${DELIVERY_CHARGE} will be added. Ask for delivery address."
        if (
            self._flow.state.items_complete
            and self._flow.state.special_instructions_done
            and not self._flow.state.readback_spoken
        ):
            readback = format_order_readback(self.cart, include_price=not self.is_phone)
            if readback and self._session:
                self._flow.mark_readback_spoken()
                await self._session.say(readback, allow_interruptions=True)
                self.note_agent_speech(readback)
                return (
                    "Set to pickup. Read-back already spoken — wait for customer All good?. "
                    "Do NOT ask allergies, name, or phone."
                )
        return (
            "Set to pickup. Do NOT ask name, phone, or allergies — "
            "system handles read-back and contact capture."
        )

    @function_tool
    async def set_customer_info(
        self,
        name: Annotated[str, "Customer's name — phone must be empty until name is saved"],
        phone: Annotated[str, "10-digit phone — leave empty until name step is complete"] = "",
    ) -> str:
        """Save customer name first, then phone on a separate step."""
        if not self._flow.state.readback_confirmed:
            return (
                "Too early — customer has not confirmed the read-back. "
                "Do NOT ask for or save name/phone yet."
            )

        lang = self._flow.state.preferred_language

        if not self.cart.customer_name:
            clean = name.strip()
            phone_digits = extract_phone_digits(phone) or extract_phone_digits(clean)
            if phone_digits and len(phone_digits) == 10:
                return (
                    "NAME STEP ONLY — save name without phone. "
                    "Do NOT ask name and phone in the same turn."
                )
            if not is_valid_customer_name(clean):
                return "Need the customer's real name — not pickup/delivery."
            self.cart.customer_name = clean
            self._flow.sync_from_cart(self.cart)
            await self._sync_web()
            ask_phone = phrase_ask_phone(lang, clean)
            if self._session:
                await self._session.say(ask_phone, allow_interruptions=True)
                self.note_agent_speech(ask_phone)
            return (
                f'Name saved: "{clean}". Phone question already spoken — '
                "do NOT ask name again or combine name+phone."
            )

        digits = extract_phone_digits(phone) or extract_phone_digits(name)
        if len(digits) != 10:
            return "Need a valid 10-digit phone number."
        self.cart.customer_phone = digits
        self._flow.sync_from_cart(self.cart)
        await self._sync_web()
        spoken = format_phone_spoken(digits)
        saved = phrase_phone_saved(lang, spoken)
        if self._session:
            await self._session.say(saved, allow_interruptions=True)
            self.note_agent_speech(saved)
        ready, _ = self.cart.ready_to_place()
        if ready:
            return await self._execute_place_order(from_capture=True)
        return (
            f"Phone saved: {digits}. "
            f'Read back used English digits only: "{spoken}".'
        )

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
        readback = format_order_readback(self.cart, include_price=False)
        if readback:
            price_note = " Do NOT mention price or totals in speech unless customer asked."
            return (
                f"{summary}\n\nSPOKEN READ-BACK (say exactly):\n{readback}{price_note}"
            )
        return summary

    async def _execute_place_order(
        self,
        *,
        from_capture: bool = False,
        turn_ctx=None,
    ) -> str:
        """Finalize order — shared by place_order tool and code-owned phone capture."""
        if self.cart.placed or self._goodbye_spoken:
            return (
                "ORDER COMPLETE — goodbye already spoken. "
                "Do NOT generate any assistant speech."
            )

        ready, reason = self.cart.ready_to_place()
        if not ready:
            return f"Cannot place order: {reason}"

        clover_order_id: str | None = None
        clover_meta: dict = {}
        if clover_submit_enabled():
            try:
                from restaurant.clover.order_submit import (
                    CloverOrderSubmitError,
                    submit_cart_to_clover,
                )
                from restaurant.tenants.config import get_default_tenant

                result = submit_cart_to_clover(
                    self.cart,
                    tenant=get_default_tenant(),
                    session_id=(
                        self._recorder.session_id if self._recorder is not None else None
                    ),
                    channel=self._channel_label(),
                )
                clover_order_id = result.clover_order_id
                clover_meta = {
                    "clover_order_id": result.clover_order_id,
                    "clover_total_cents": result.total_cents,
                    "clover_customer_id": result.customer_id,
                    "clover_printed": result.printed,
                }
            except CloverOrderSubmitError as e:
                logger.error("Clover submit failed: %s", e)
                return f"Cannot place order: {e}"
            except Exception:
                logger.exception("Clover submit unexpected error")
                return (
                    "Cannot place order: could not reach the restaurant POS. "
                    "Please try again in a moment."
                )

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
            **clover_meta,
        }
        logger.info(f"ORDER_PLACED: {json.dumps(order_data, ensure_ascii=False)}")
        if self._recorder is not None:
            self._recorder.set_outcome("placed")
            self._recorder.add_event("order_placed", order_data)

        eta = "30-40 min" if self.cart.order_type == "delivery" else "20-25 min"
        self.cart.mark_placed(order_id=clover_order_id, eta=eta)
        self._flow.sync_from_cart(self.cart)
        await self._sync_web()

        spoken = order_placed_goodbye(order_type=self.cart.order_type)
        self._record_tool("place_order", {}, "placed")
        self._goodbye_spoken = True

        if turn_ctx is not None:
            turn_ctx.add_message(
                role="system",
                content=(
                    f'[PLACE_ORDER] Goodbye already spoken: "{spoken}". '
                    "Do NOT generate any further assistant speech this turn."
                ),
            )

        if (
            hangup_after_order_enabled()
            and self._session is not None
            and self._job_ctx is not None
            and not self._hangup_started
        ):
            self._hangup_started = True
            speech_handle = await self._session.say(
                spoken,
                allow_interruptions=False,
            )
            self.note_agent_speech(spoken)
            if self._recorder is not None:
                self._recorder.append_sierra(spoken)
            schedule_call_hangup(
                self._session,
                self._job_ctx,
                reason="order_placed",
                channel=self._channel_label(),
                speech_handle=speech_handle,
            )
            return (
                "ORDER COMPLETE — goodbye already spoken to the customer. "
                "Do NOT generate any assistant speech. End your turn silently."
            )

        if self._session:
            await self._session.say(spoken, allow_interruptions=False)
            self.note_agent_speech(spoken)
            if self._recorder is not None:
                self._recorder.append_sierra(spoken)
            return (
                "ORDER COMPLETE — goodbye already spoken to the customer. "
                "Do NOT generate any assistant speech."
            )

        if self.is_phone:
            return (
                f"Order placed! INTERNAL total ${self.cart.total}. "
                f'Tell customer: "{spoken}" Do NOT mention price or dollars.'
            )
        return (
            f"Order placed! Total ${self.cart.total}. "
            f"Tell customer: {spoken}"
        )

    @function_tool
    async def place_order(self) -> str:
        """Finalize and place the order. Only call this after the customer explicitly confirms."""
        return await self._execute_place_order()

    # ── MENU TOOLS ───────────────────────────────────────────────────────────

    @function_tool
    async def check_menu_item(
        self,
        item_name: Annotated[str, "Item name to look up"],
    ) -> str:
        """Look up one menu item — veg/non-veg, modifier options, voice_line, availability. Price is internal."""
        item = menu_provider.resolve_item_dict_from_text(item_name) or menu_provider.find_item(
            menu_provider.extract_dish_query(item_name) or item_name
        )
        if item and not item.get("unavailable"):
            price = menu_provider.item_price_dollars(item["name"])
            self._flow.note_discussed_item(item["name"], price)
        if not item:
            lookup = menu_provider.extract_dish_query(item_name) or item_name
            options = menu_provider.disambiguation_options(lookup)
            if len(options) >= 2:
                names = ", ".join(o["name"] for o in options)
                result = (
                    f'"{item_name}" could be: {names}. Ask the customer which ONE — '
                    "do NOT pick for them and do NOT add anything yet."
                )
                self._record_tool("check_menu_item", {"item_name": item_name}, result)
                return result
        result = menu_provider.check_item(item_name)
        self._record_tool("check_menu_item", {"item_name": item_name}, result)
        return result

    @function_tool
    async def search_menu_items(
        self,
        query: Annotated[str, "Search term e.g. 'paneer', 'combo', 'biryani', 'vegetarian starters'"],
    ) -> str:
        """Search the menu by keyword or category. Use for 'what X dishes do you have?' questions."""
        result = menu_provider.search_menu(query)
        self._record_tool("search_menu_items", {"query": query}, result)
        if self._recorder is not None and "no items found" in result.lower():
            self._recorder.add_event("menu_search_empty", {"query": query})
        return result

    # ── TRANSFER ─────────────────────────────────────────────────────────────

    @function_tool
    async def transfer_to_human(
        self,
        reason: Annotated[str, "Why the call is being transferred, e.g. 'caller requested' or 'two unclear responses'"] = "",
    ) -> str:
        """Transfer the call to a human staff member."""
        logger.info(f"TRANSFER_TO_HUMAN: {reason}")
        if self._recorder is not None:
            self._recorder.set_transfer(reason or "unspecified")
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
        if self._recorder is not None:
            self._recorder.add_event("reservation_booked", record)

        return (
            f"Reservation confirmed! Ref: {record['ref']}. "
            f"Tell customer: ਤੁਹਾਡੀ ਬੁਕਿੰਗ ਹੋ ਗਈ ਜੀ! "
            f"Reference number ਹੈ {record['ref']}। ਧੰਨਵਾਦ ਜੀ!"
        )


def _sip_caller_phone(attrs: dict) -> str | None:
    for key in ("sip.phoneNumber", "sip.callerNumber", "sip.from"):
        value = attrs.get(key)
        if value:
            return str(value)
    return None


async def entrypoint(ctx: JobContext):
    await ctx.connect()

    participant = await ctx.wait_for_participant()
    sip_attrs = dict(participant.attributes or {})

    is_phone = (
        participant.identity.startswith("sip_")
        or sip_attrs.get("sip.callStatus") is not None
    )
    channel = "phone" if is_phone else "web"

    logger.info(
        f"Session started | room={ctx.room.name} | "
        f"channel={channel} | "
        f"participant={participant.identity}"
    )

    recorder = SessionRecorder(
        metadata={"git_sha": os.getenv("DEPLOY_GIT_SHA", "")},
    )
    recorder.start(
        room_name=ctx.room.name,
        channel=channel,
        participant_identity=participant.identity,
        caller_phone=_sip_caller_phone(sip_attrs),
    )

    session = build_agent_session(is_phone=is_phone)

    def _on_turn_latency(latency: dict) -> None:
        recorder.attach_latency(latency)

    TurnLatencyTracker(channel=channel, on_turn_latency=_on_turn_latency).attach(session)

    agent = RestaurantAgent(is_phone=is_phone)
    agent.bind_session(session)
    agent.bind_recorder(recorder)
    agent.bind_job_context(ctx)

    # Race the fixed greeting: prime OpenAI's prompt cache with the real tool
    # schema so the caller's first real turn doesn't pay the cold-prefix cost.
    # See pr/pr_047_ladder-intent-guard-and-llm-warmup-v2.md.
    schedule_llm_warmup(is_phone=is_phone, tools=agent.tools)

    _analytics_flushed = False

    async def _flush_analytics(*, reason: str = "shutdown") -> None:
        nonlocal _analytics_flushed
        if _analytics_flushed:
            return
        _analytics_flushed = True
        logger.info(
            "Flushing session analytics (%s) room=%s session=%s",
            reason,
            recorder.room_name,
            recorder.session_id,
        )
        try:
            payload = recorder.finalize(
                agent.cart,
                preferred_language=agent._flow.state.preferred_language.value,
            )
            await persist_session(payload)
        except Exception:
            logger.exception("Session analytics flush failed (%s)", reason)

    @session.on("close")
    def _on_session_close(_ev) -> None:
        asyncio.create_task(_flush_analytics(reason="session_close"))

    async def _shutdown_flush() -> None:
        await _flush_analytics(reason="shutdown")

    ctx.add_shutdown_callback(_shutdown_flush)

    await session.start(
        room=ctx.room,
        agent=agent,
        room_options=build_room_options(is_phone=is_phone),
    )

    background_audio = build_ambient_player(is_phone=is_phone)
    if background_audio is not None:
        await start_ambient(
            background_audio,
            is_phone=is_phone,
            room=ctx.room,
            agent_session=session,
        )

        async def _stop_ambient() -> None:
            await stop_ambient(background_audio, is_phone=is_phone)

        ctx.add_shutdown_callback(_stop_ambient)

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
            lang = getattr(ev, "language", None)
            recorder.begin_user_turn(ev.transcript or "", stt_language=lang)

    @session.on("conversation_item_added")
    def _on_conv_item(ev) -> None:
        role = getattr(ev.item, "role", None)
        if role == "assistant":
            text = getattr(ev.item, "text_content", None) or ""
            if text:
                cleaned = sanitize_assistant_speech(
                    text,
                    allow_greeting=agent._real_user_turns == 0,
                    is_phone=agent.is_phone,
                    customer_phone=agent.cart.customer_phone or None,
                )
                if cleaned != text:
                    logger.warning("Mid-call re-greeting blocked in log: %s", text[:80])
                agent.note_agent_speech(text)
                recorder.append_sierra(text)
                logger.info(f"SIERRA: {text}")

    await session.say(
        OPENING_GREETING,
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
