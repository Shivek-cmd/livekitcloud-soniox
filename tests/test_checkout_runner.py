"""Tests for checkout mode state machine (PR 034)."""

import asyncio

from restaurant.checkout_runner import CheckoutRunner, CheckoutStep
from restaurant.conversation import (
    ALLERGIES_QUESTION,
    PICKUP_DELIVERY_QUESTION,
    UserIntent,
    is_confirm_yes,
    phrase_name_for_order,
    phrase_phone_for_order,
)
from restaurant.order_flow import OrderFlowController
from restaurant.orders import OrderCart


class _FakeTurnCtx:
    def __init__(self) -> None:
        self.messages: list[tuple[str, str]] = []

    def add_message(self, *, role: str, content: str) -> None:
        self.messages.append((role, content))


class _FakeAgent:
    def __init__(self) -> None:
        self.cart = OrderCart()
        self.is_phone = True
        self._flow = OrderFlowController(is_phone=True)
        self._session = None
        self._recorder = None
        self.spoken: list[str] = []

    async def _sync_web(self) -> None:
        return None

    async def _cancel_agent_speech(self) -> None:
        return None

    async def place_order(self) -> str:
        self.cart.mark_placed(eta="20-25 min")
        return "ORDER COMPLETE"

    def note_agent_speech(self, text: str) -> None:
        return None


def test_enter_checkout_on_order_done():
    async def _run():
        agent = _FakeAgent()
        agent.cart.add_item({"name": "Chai", "voice_line": "Masala Chai", "price": 4}, 1)
        runner = CheckoutRunner()
        ctx = _FakeTurnCtx()

        blocked = await runner.handle_turn(
            agent, ctx, "bas", UserIntent.ORDER_DONE
        )

        assert blocked is True
        assert runner.step == CheckoutStep.AWAITING_ALLERGY
        assert any(ALLERGIES_QUESTION in m[1] for m in ctx.messages)

    asyncio.run(_run())


def test_checkout_flow_to_name():
    async def _run():
        agent = _FakeAgent()
        agent.cart.add_item({"name": "Chai", "voice_line": "Masala Chai", "price": 4}, 1)
        agent.cart.add_item({"name": "Kheer", "voice_line": "Kheer", "price": 6}, 1)
        runner = CheckoutRunner()
        ctx = _FakeTurnCtx()

        await runner.handle_turn(agent, ctx, "bas", UserIntent.ORDER_DONE)
        await runner.handle_turn(agent, ctx, "no", UserIntent.CONFIRM_NO)
        assert runner.step == CheckoutStep.AWAITING_ORDER_TYPE
        assert any(PICKUP_DELIVERY_QUESTION in m[1] for m in ctx.messages)

        await runner.handle_turn(agent, ctx, "pickup", UserIntent.PICKUP)
        assert runner.step == CheckoutStep.AWAITING_READBACK_YES
        assert agent.cart.order_type == "pickup"

        await runner.handle_turn(agent, ctx, "ਹਾਂ ਜੀ, ਹਾਂ ਜੀ", UserIntent.GENERAL)
        assert runner.step == CheckoutStep.AWAITING_NAME
        assert phrase_name_for_order(agent._flow.state.preferred_language) in ctx.messages[-1][1]

    asyncio.run(_run())


def test_checkout_name_and_phone_use_fixed_phrases():
    async def _run():
        agent = _FakeAgent()
        agent.cart.add_item({"name": "Chai", "voice_line": "Masala Chai", "price": 4}, 1)
        agent.cart.order_type = "pickup"
        runner = CheckoutRunner()
        ctx = _FakeTurnCtx()
        runner.step = CheckoutStep.AWAITING_NAME
        agent._flow.mark_items_complete()
        agent._flow.mark_allergies_asked()
        agent._flow.mark_special_instructions_done()
        agent._flow.mark_readback_spoken()
        agent._flow.mark_readback_confirmed()

        await runner.handle_turn(agent, ctx, "Shivek", UserIntent.GENERAL)
        assert runner.step == CheckoutStep.AWAITING_PHONE
        assert phrase_phone_for_order(agent._flow.state.preferred_language) in ctx.messages[-1][1]

        await runner.handle_turn(agent, ctx, "94137 52688", UserIntent.GENERAL)
        assert runner.step == CheckoutStep.AWAITING_FINAL_YES
        assert agent.cart.customer_phone == "9413752688"
        assert "All good?" in ctx.messages[-1][1]
        assert "dollar" not in ctx.messages[-1][1].lower()

    asyncio.run(_run())


def test_double_haan_ji_is_confirm_yes():
    assert is_confirm_yes("ਹਾਂ ਜੀ, ਹਾਂ ਜੀ") is True


def test_inactive_checkout_does_not_block():
    runner = CheckoutRunner()
    assert runner.is_active() is False
