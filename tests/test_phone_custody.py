"""PR 082 — code-side phone digit custody in on_user_turn_completed.

The pure reducer (accumulate_phone) is unit-tested in test_customer_info.py.
Here we exercise the agent-level wiring: phase gating, code-side cart capture,
and the system-message injections. A web agent is used so the phone-only
echo/background hygiene filters don't intercept digit utterances.
"""

import asyncio

import pytest

from restaurant.agent.core import RestaurantAgent


def run(coro):
    return asyncio.run(coro)


class _TurnCtx:
    def __init__(self):
        self.messages = []

    def add_message(self, *, role, content):
        self.messages.append((role, content))


class _Msg:
    def __init__(self, text):
        self.text_content = text


class _EventRecorder:
    def __init__(self):
        self.events = []

    def log_tool(self, name, args, result):
        pass

    def add_event(self, event_type, payload=None):
        self.events.append((event_type, payload))

    # complete_turn is called at the end of on_user_turn_completed.
    def complete_turn(self, cart_snapshot=None):
        pass

    @property
    def current_turn(self):
        return object()

    def begin_user_turn(self, text):
        pass


@pytest.fixture
def agent() -> RestaurantAgent:
    return RestaurantAgent(is_phone=False)


def _enter_phone_phase(agent):
    """Name + order type set, phone still missing — the custody phase."""
    agent.cart.customer_name = "Aman"
    agent.cart.order_type = "pickup"


def _system_msgs(ctx):
    return [c for role, c in ctx.messages if role == "system"]


def test_no_custody_before_phone_phase(agent):
    # Name unset / order-type unset → custody must not fire on a digit turn.
    ctx = _TurnCtx()
    run(agent.on_user_turn_completed(ctx, _Msg("80770")))
    assert agent.state.phone_buffer == ""
    assert not agent.cart.customer_phone
    assert not any("PHONE" in m for m in _system_msgs(ctx))


def test_single_shot_capture_sets_cart_and_injects(agent):
    _enter_phone_phase(agent)
    recorder = _EventRecorder()
    agent.bind_recorder(recorder)
    ctx = _TurnCtx()
    run(agent.on_user_turn_completed(ctx, _Msg("It's 80770 39800.")))
    assert agent.cart.customer_phone == "8077039800"
    assert agent.state.phone_buffer == ""
    assert any(e[0] == "phone_captured_code_side" for e in recorder.events)
    msgs = _system_msgs(ctx)
    assert any("PHONE CAPTURED AND SAVED" in m for m in msgs)
    # Confirm-back is spoken as English word digits — never numerals.
    captured = next(m for m in msgs if "PHONE CAPTURED" in m)
    assert "eight, zero, seven, seven, zero" in captured


def test_fragments_stitch_to_capture(agent):
    _enter_phone_phase(agent)
    # First fragment → progress injection, cart still empty.
    ctx1 = _TurnCtx()
    run(agent.on_user_turn_completed(ctx1, _Msg("80")))
    assert agent.state.phone_buffer == "80"
    assert not agent.cart.customer_phone
    assert any("PHONE IN PROGRESS" in m and "2 of 10" in m for m in _system_msgs(ctx1))

    ctx2 = _TurnCtx()
    run(agent.on_user_turn_completed(ctx2, _Msg("770")))
    assert agent.state.phone_buffer == "80770"
    assert any("5 of 10" in m for m in _system_msgs(ctx2))

    ctx3 = _TurnCtx()
    run(agent.on_user_turn_completed(ctx3, _Msg("39800")))
    assert agent.cart.customer_phone == "8077039800"
    assert agent.state.phone_buffer == ""
    assert any("PHONE CAPTURED AND SAVED" in m for m in _system_msgs(ctx3))


def test_non_phone_turn_is_ignored(agent):
    _enter_phone_phase(agent)
    agent.state.phone_buffer = "80770"
    ctx = _TurnCtx()
    run(agent.on_user_turn_completed(ctx, _Msg("Actually, can I add a naan?")))
    # A menu-ish turn leaves the buffer untouched and injects nothing.
    assert agent.state.phone_buffer == "80770"
    assert not any("PHONE" in m for m in _system_msgs(ctx))


def test_no_custody_once_phone_set(agent):
    _enter_phone_phase(agent)
    agent.cart.customer_phone = "8077039800"
    ctx = _TurnCtx()
    run(agent.on_user_turn_completed(ctx, _Msg("90000")))
    # Phase is over — a stray digit turn must not disturb the saved phone.
    assert agent.cart.customer_phone == "8077039800"
    assert not any("PHONE" in m for m in _system_msgs(ctx))


def test_custody_disabled_by_env(agent, monkeypatch):
    monkeypatch.setenv("PHONE_DIGIT_CUSTODY", "off")
    _enter_phone_phase(agent)
    ctx = _TurnCtx()
    run(agent.on_user_turn_completed(ctx, _Msg("It's 80770 39800.")))
    assert not agent.cart.customer_phone
    assert agent.state.phone_buffer == ""
