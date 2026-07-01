"""Checkout mode — LLM-free order closing after customer says they are done ordering."""

from __future__ import annotations

import logging
from enum import Enum

from restaurant.conversation import (
    ALLERGIES_QUESTION,
    DELIVERY_ADDRESS_QUESTION,
    PICKUP_DELIVERY_QUESTION,
    CustomerLanguage,
    UserIntent,
    extract_customer_name,
    extract_phone_digits,
    format_final_confirm,
    format_order_readback,
    is_allergies_step_answer,
    is_confirm_yes,
    is_likely_pickup_stt,
    phrase_name_for_order,
    phrase_phone_for_order,
    phrase_repeat_request,
    resolve_intent,
)
from restaurant.order_flow import OrderFlowController

logger = logging.getLogger("checkout-runner")


class CheckoutStep(str, Enum):
    INACTIVE = "inactive"
    AWAITING_ALLERGY = "awaiting_allergy"
    AWAITING_ORDER_TYPE = "awaiting_order_type"
    AWAITING_DELIVERY_ADDRESS = "awaiting_delivery_address"
    AWAITING_READBACK_YES = "awaiting_readback_yes"
    AWAITING_NAME = "awaiting_name"
    AWAITING_PHONE = "awaiting_phone"
    AWAITING_FINAL_YES = "awaiting_final_yes"


class CheckoutRunner:
    """Single state machine for post-order checkout — code speaks, LLM stays silent."""

    def __init__(self) -> None:
        self.step = CheckoutStep.INACTIVE

    def is_active(self) -> bool:
        return self.step != CheckoutStep.INACTIVE

    def reset(self) -> None:
        self.step = CheckoutStep.INACTIVE

    def _sync_flow(self, agent: object) -> None:
        agent._flow.sync_from_cart(agent.cart)  # type: ignore[attr-defined]

    async def handle_turn(
        self,
        agent: object,
        turn_ctx,
        user_text: str,
        intent: UserIntent,
    ) -> bool:
        """Run checkout logic. Returns True when caller must StopResponse (no LLM)."""
        cart = agent.cart
        flow: OrderFlowController = agent._flow
        lang = flow.state.preferred_language

        if intent == UserIntent.ORDER_DONE and not cart.is_empty and not self.is_active():
            return await self._enter_checkout(agent, turn_ctx)

        if not self.is_active():
            return False

        intent = self._resolve_for_step(user_text, intent)

        if self.step == CheckoutStep.AWAITING_ALLERGY:
            if is_allergies_step_answer(user_text, intent):
                flow.mark_special_instructions_done()
                self._sync_flow(agent)
                await self._speak(agent, turn_ctx, PICKUP_DELIVERY_QUESTION, "pickup_ask")
                self.step = CheckoutStep.AWAITING_ORDER_TYPE
            else:
                await self._speak(
                    agent,
                    turn_ctx,
                    phrase_repeat_request(lang),
                    "allergy_reprompt",
                )
            return True

        if self.step == CheckoutStep.AWAITING_ORDER_TYPE:
            if intent == UserIntent.PICKUP or is_likely_pickup_stt(user_text):
                cart.order_type = "pickup"
                await agent._sync_web()
                flow.sync_from_cart(cart)
                return await self._speak_readback(agent, turn_ctx)
            if intent == UserIntent.DELIVERY:
                cart.order_type = "delivery"
                await agent._sync_web()
                flow.sync_from_cart(cart)
                await self._speak(agent, turn_ctx, DELIVERY_ADDRESS_QUESTION, "delivery_address")
                self.step = CheckoutStep.AWAITING_DELIVERY_ADDRESS
                return True
            await self._speak(
                agent,
                turn_ctx,
                phrase_repeat_request(lang),
                "order_type_reprompt",
            )
            return True

        if self.step == CheckoutStep.AWAITING_DELIVERY_ADDRESS:
            addr = user_text.strip()
            if len(addr) >= 8:
                cart.delivery_address = addr
                await agent._sync_web()
                flow.sync_from_cart(cart)
                return await self._speak_readback(agent, turn_ctx)
            await self._speak(
                agent,
                turn_ctx,
                phrase_repeat_request(lang),
                "address_reprompt",
            )
            return True

        if self.step == CheckoutStep.AWAITING_READBACK_YES:
            if intent == UserIntent.CONFIRM_YES or is_confirm_yes(user_text):
                flow.mark_readback_confirmed()
                self._sync_flow(agent)
                await self._speak(
                    agent,
                    turn_ctx,
                    phrase_name_for_order(lang),
                    "name_ask",
                )
                self.step = CheckoutStep.AWAITING_NAME
            else:
                await self._speak(
                    agent,
                    turn_ctx,
                    phrase_repeat_request(lang),
                    "readback_reprompt",
                )
            return True

        if self.step == CheckoutStep.AWAITING_NAME:
            name = extract_customer_name(user_text)
            if name:
                cart.customer_name = name
                await agent._sync_web()
                self._sync_flow(agent)
                await self._speak(
                    agent,
                    turn_ctx,
                    phrase_phone_for_order(lang),
                    "phone_ask",
                )
                self.step = CheckoutStep.AWAITING_PHONE
            else:
                await self._speak(
                    agent,
                    turn_ctx,
                    phrase_name_for_order(lang),
                    "name_reprompt",
                )
            return True

        if self.step == CheckoutStep.AWAITING_PHONE:
            phone = extract_phone_digits(user_text)
            if phone:
                cart.customer_phone = phone
                flow.state.final_confirm_pending = True
                await agent._sync_web()
                self._sync_flow(agent)
                line = format_final_confirm(cart)
                if line:
                    await self._speak(agent, turn_ctx, line, "final_confirm")
                self.step = CheckoutStep.AWAITING_FINAL_YES
            else:
                await self._speak(
                    agent,
                    turn_ctx,
                    phrase_phone_for_order(lang),
                    "phone_reprompt",
                )
            return True

        if self.step == CheckoutStep.AWAITING_FINAL_YES:
            if intent == UserIntent.CONFIRM_YES or is_confirm_yes(user_text):
                flow.state.final_confirm_pending = False
                await agent._cancel_agent_speech()
                result = await agent.place_order()
                turn_ctx.add_message(
                    role="system",
                    content=f"[CHECKOUT:placed] {result}",
                )
                self.step = CheckoutStep.INACTIVE
            else:
                line = format_final_confirm(cart)
                if line:
                    await self._speak(agent, turn_ctx, line, "final_reprompt")
            return True

        return True

    async def _enter_checkout(self, agent: object, turn_ctx) -> bool:
        flow = agent._flow
        if not flow.state.items_complete:
            flow.mark_items_complete()
        flow.mark_allergies_asked()
        self._sync_flow(agent)
        await self._speak(agent, turn_ctx, ALLERGIES_QUESTION, "allergies")
        self.step = CheckoutStep.AWAITING_ALLERGY
        logger.info("CHECKOUT entered step=%s", self.step.value)
        return True

    async def _speak_readback(self, agent: object, turn_ctx) -> bool:
        flow = agent._flow
        line = format_order_readback(agent.cart, include_price=not agent.is_phone)
        if not line:
            return True
        flow.mark_readback_spoken()
        self._sync_flow(agent)
        await self._speak(agent, turn_ctx, line, "readback")
        self.step = CheckoutStep.AWAITING_READBACK_YES
        return True

    async def _speak(
        self,
        agent: object,
        turn_ctx,
        line: str,
        tag: str,
    ) -> None:
        turn_ctx.add_message(
            role="system",
            content=f'[CHECKOUT:{tag}] Already spoken: "{line}"',
        )
        logger.info("CHECKOUT %s text=%s", tag, line)
        await agent._cancel_agent_speech()
        if agent._session:
            await agent._session.say(line, allow_interruptions=True)
            agent.note_agent_speech(line)
        if agent._recorder is not None:
            agent._recorder.append_sierra(line)

    def _resolve_for_step(self, user_text: str, intent: UserIntent) -> UserIntent:
        if self.step in (
            CheckoutStep.AWAITING_READBACK_YES,
            CheckoutStep.AWAITING_FINAL_YES,
        ) and is_confirm_yes(user_text):
            return UserIntent.CONFIRM_YES
        if self.step == CheckoutStep.AWAITING_ORDER_TYPE:
            if is_likely_pickup_stt(user_text):
                return UserIntent.PICKUP
        if self.step == CheckoutStep.AWAITING_PHONE and extract_phone_digits(user_text):
            return UserIntent.GENERAL
        if self.step in (
            CheckoutStep.AWAITING_ALLERGY,
            CheckoutStep.AWAITING_ORDER_TYPE,
        ):
            phase = "special_instructions" if self.step == CheckoutStep.AWAITING_ALLERGY else "order_type"
            return resolve_intent(user_text, phase=phase)
        return intent
