"""Tests for the generic checkout re-ask fallback (PR 050).

Live-call regression: a caller correcting a missed item at the read-back
"All good?" step got zero response for 4+ turns because the general
checkout-mute path had no fallback speech of its own once the caller's turn
didn't match any specific ladder branch. _reask_current_checkout_question()
re-speaks the current phase's pending fixed question instead of going silent.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

from agent import RestaurantAgent
from restaurant.conversation import (
    ALLERGIES_QUESTION,
    PICKUP_DELIVERY_QUESTION,
)
from restaurant.order_flow import OrderPhase


def _make_agent() -> RestaurantAgent:
    agent = RestaurantAgent(is_phone=True)
    session = MagicMock()
    session.say = AsyncMock()
    agent.bind_session(session)
    return agent


def _spoken_lines(agent: RestaurantAgent) -> list[str]:
    return [call.args[0] for call in agent._session.say.call_args_list]


def test_reask_allergies():
    agent = _make_agent()
    agent._flow.state.phase = OrderPhase.SPECIAL_INSTRUCTIONS
    agent._flow.mark_allergies_asked()

    handled = asyncio.run(agent._reask_current_checkout_question(MagicMock()))

    assert handled is True
    assert ALLERGIES_QUESTION in _spoken_lines(agent)


def test_reask_pickup_delivery():
    agent = _make_agent()
    agent._flow.state.phase = OrderPhase.ORDER_TYPE

    handled = asyncio.run(agent._reask_current_checkout_question(MagicMock()))

    assert handled is True
    assert PICKUP_DELIVERY_QUESTION in _spoken_lines(agent)


def test_reask_readback_repeats_full_readback():
    agent = _make_agent()
    agent.cart.add_item({"name": "Palak Paneer", "voice_line": "Palak Paneer", "price": 12.0}, 1)
    agent.cart.order_type = "pickup"
    agent._flow.state.phase = OrderPhase.READBACK
    agent._flow.mark_readback_spoken()

    handled = asyncio.run(agent._reask_current_checkout_question(MagicMock()))

    assert handled is True
    spoken = _spoken_lines(agent)
    assert spoken
    assert "pickup" in spoken[0].lower()


def test_reask_readback_noop_before_readback_spoken():
    # If the read-back was never actually spoken yet, this isn't "the caller
    # ignored a question" — a different branch of _try_run_checkout_ladder
    # owns speaking it for the first time, so this must not double-speak.
    agent = _make_agent()
    agent._flow.state.phase = OrderPhase.READBACK

    handled = asyncio.run(agent._reask_current_checkout_question(MagicMock()))

    assert handled is False
    agent._session.say.assert_not_called()


def test_reask_customer_name():
    agent = _make_agent()
    agent._flow.state.phase = OrderPhase.CUSTOMER_NAME

    handled = asyncio.run(agent._reask_current_checkout_question(MagicMock()))

    assert handled is True
    assert agent._session.say.await_count == 1


def test_reask_customer_phone_requires_name_saved():
    agent = _make_agent()
    agent._flow.state.phase = OrderPhase.CUSTOMER_PHONE
    agent.cart.customer_name = "Shivek"

    handled = asyncio.run(agent._reask_current_checkout_question(MagicMock()))

    assert handled is True
    assert agent._session.say.await_count == 1


def test_reask_ready_to_place_has_no_fallback():
    # No pending "question" at this phase — falls back to the old
    # filler+guidance behavior at the call site, not this helper.
    agent = _make_agent()
    agent._flow.state.phase = OrderPhase.READY_TO_PLACE

    handled = asyncio.run(agent._reask_current_checkout_question(MagicMock()))

    assert handled is False
    agent._session.say.assert_not_called()
