"""Tests for restaurant.agent.core.place_order — hard gate, shadow mode,
to_thread Clover submit, failure path, goodbye + hangup, sentinel."""

import asyncio
import threading
from dataclasses import dataclass

import pytest

from restaurant import menu_provider
from restaurant.agent import core
from restaurant.agent.core import RestaurantAgent

_NAAN = {
    "name": "Garlic Naan",
    "voice_line": "Garlic Naan",
    "price": 3.50,
    "clover_item_id": "gn1",
    "match_confidence": 0.95,
}


@dataclass
class _FakeSubmitResult:
    clover_order_id: str = "CLV123"
    total_cents: int = 700
    customer_id: str = "CUST1"
    printed: bool = True


class _FakeSpeechHandle:
    def done(self) -> bool:
        return True


class _FakeSession:
    def __init__(self):
        self.said: list[tuple[str, bool]] = []

    @property
    def current_speech(self):
        return None

    async def say(self, text, allow_interruptions=True):
        self.said.append((text, allow_interruptions))
        return _FakeSpeechHandle()


@dataclass
class _FakeTenant:
    name: str = "test"


def run(coro):
    return asyncio.run(coro)


@pytest.fixture()
def agent(monkeypatch) -> RestaurantAgent:
    monkeypatch.setattr(menu_provider, "extract_dish_query", lambda text: None)
    monkeypatch.setattr(menu_provider, "find_item", lambda name: dict(_NAAN))
    monkeypatch.setattr(menu_provider, "disambiguation_options", lambda name, limit=3: [])
    monkeypatch.setattr(menu_provider, "item_has_spice_level", lambda name: False)
    monkeypatch.setattr(menu_provider, "required_modifier_groups", lambda item_id: [])
    monkeypatch.setattr(core, "hangup_after_order_enabled", lambda: False)
    a = RestaurantAgent(is_phone=True)
    return a


def _make_ready(agent):
    run(agent.add_item("garlic naan", quantity=2))
    run(agent.record_allergies("no"))
    run(agent.set_order_type("pickup"))
    run(agent.set_customer_contact(name="Aman Singh"))
    run(agent.set_customer_contact(phone="7805551234"))
    run(agent.get_order_readback())
    run(agent.confirm_readback())


def test_blockers_returned_verbatim(agent, monkeypatch):
    monkeypatch.setattr(core, "clover_submit_enabled", lambda: False)
    run(agent.add_item("garlic naan"))
    result = run(agent.place_order())
    assert "Cannot place order" in result
    assert "llerg" in result
    assert "read back" in result
    assert not agent.cart.placed


def test_shadow_mode_places_without_clover(agent, monkeypatch):
    monkeypatch.setattr(core, "clover_submit_enabled", lambda: False)

    def _boom(*a, **kw):
        raise AssertionError("submit_cart_to_clover must not be called in shadow mode")

    monkeypatch.setattr(core, "submit_cart_to_clover", _boom)
    _make_ready(agent)
    result = run(agent.place_order())
    assert "ORDER COMPLETE" in result or "Order placed" in result
    assert agent.cart.placed
    assert agent.cart.order_id is None


def test_clover_submit_runs_off_event_loop(agent, monkeypatch):
    monkeypatch.setattr(core, "clover_submit_enabled", lambda: True)
    import restaurant.tenants.config as tenants_config

    monkeypatch.setattr(tenants_config, "get_default_tenant", lambda: _FakeTenant())

    seen = {}

    def _fake_submit(cart, *, tenant, session_id=None, channel="phone", allergy_note=None):
        seen["thread"] = threading.current_thread()
        seen["channel"] = channel
        seen["allergy_note"] = allergy_note
        return _FakeSubmitResult()

    monkeypatch.setattr(core, "submit_cart_to_clover", _fake_submit)
    _make_ready(agent)
    result = run(agent.place_order())

    assert seen["thread"] is not threading.main_thread()
    assert seen["channel"] == "phone"
    assert seen["allergy_note"] is None  # "no" answer → no note threaded
    assert agent.cart.placed
    assert agent.cart.order_id == "CLV123"
    assert "ORDER COMPLETE" in result or "Order placed" in result


def test_clover_failure_never_fakes_success(agent, monkeypatch):
    monkeypatch.setattr(core, "clover_submit_enabled", lambda: True)
    import restaurant.tenants.config as tenants_config

    monkeypatch.setattr(tenants_config, "get_default_tenant", lambda: _FakeTenant())

    def _fail(cart, *, tenant, session_id=None, channel="phone", allergy_note=None):
        raise core.CloverOrderSubmitError("validation failed: item missing")

    monkeypatch.setattr(core, "submit_cart_to_clover", _fail)
    _make_ready(agent)
    result = run(agent.place_order())

    assert "Cannot place order" in result
    assert "validation failed" in result
    assert not agent.cart.placed
    assert not agent._goodbye_spoken


def test_unexpected_error_spoken_failure_path(agent, monkeypatch):
    monkeypatch.setattr(core, "clover_submit_enabled", lambda: True)
    import restaurant.tenants.config as tenants_config

    monkeypatch.setattr(tenants_config, "get_default_tenant", lambda: _FakeTenant())

    def _fail(cart, *, tenant, session_id=None, channel="phone", allergy_note=None):
        raise RuntimeError("socket timeout")

    monkeypatch.setattr(core, "submit_cart_to_clover", _fail)
    _make_ready(agent)
    result = run(agent.place_order())
    assert "Cannot place order" in result
    assert "POS" in result
    assert not agent.cart.placed


def test_goodbye_spoken_and_sentinel_with_session(agent, monkeypatch):
    monkeypatch.setattr(core, "clover_submit_enabled", lambda: False)
    session = _FakeSession()
    agent.bind_session(session)
    _make_ready(agent)
    result = run(agent.place_order())
    assert result.startswith("ORDER COMPLETE")
    assert "Do NOT generate any assistant speech" in result
    # Goodbye spoken uninterruptible, from code — not the LLM.
    goodbye = [s for s in session.said if "ਧੰਨਵਾਦ" in s[0]]
    assert goodbye and goodbye[0][1] is False


def test_hangup_scheduled_when_enabled(agent, monkeypatch):
    monkeypatch.setattr(core, "clover_submit_enabled", lambda: False)
    monkeypatch.setattr(core, "hangup_after_order_enabled", lambda: True)
    scheduled = {}

    def _fake_schedule(session, job_ctx, *, reason, channel, speech_handle=None):
        scheduled["reason"] = reason
        scheduled["channel"] = channel

    monkeypatch.setattr(core, "schedule_call_hangup", _fake_schedule)
    session = _FakeSession()
    agent.bind_session(session)
    agent.bind_job_context(object())
    _make_ready(agent)
    result = run(agent.place_order())
    assert scheduled == {"reason": "order_placed", "channel": "phone"}
    assert "ORDER COMPLETE" in result


def test_double_place_is_idempotent(agent, monkeypatch):
    monkeypatch.setattr(core, "clover_submit_enabled", lambda: False)
    _make_ready(agent)
    run(agent.place_order())
    revision_after = agent.cart.revision
    result = run(agent.place_order())
    assert "ORDER COMPLETE" in result
    assert agent.cart.revision == revision_after
