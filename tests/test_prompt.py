"""Tests for the sectioned persona prompt (PR 077) + drift re-anchor.

The persona sections are the only prompt — PR 099 retired the PROMPT_STYLE=legacy
rollback builder, and a stale PROMPT_STYLE in the environment must not change
anything.
"""

import asyncio

from restaurant.agent.core import RestaurantAgent
from restaurant.agent.persona import (
    PERSONA_REANCHOR_LINE,
    persona_reanchor_turns,
    persona_section,
)
from restaurant.agent.prompt import build_system_prompt

# Rules that must survive in the assembled prompt on every channel.
_NON_NEGOTIABLES = [
    "Punjabi → Gurmukhi. Hindi → Devanagari. Never Roman Indic.",
    "voice_line from tools exactly",
    "NEVER transliterate an English dish name",
    "English word digits",
    "stay in English",
    "record_additional_requests",
    "add_item is additive",
    "NEVER GUESS A DISH OR A QUANTITY",
    "get_recommendations(preference, category)",
    "recommend dishes without get_recommendations/search_menu",
    "get_order_readback",
    "confirm_readback",
    "never repeat the welcome intro",
    "⛔ result means the cart did NOT change",
    "ORDER COMPLETE — goodbye already spoken",
]


def test_non_negotiables_present_on_both_channels():
    for is_phone in (True, False):
        prompt = build_system_prompt(is_phone=is_phone)
        for rule in _NON_NEGOTIABLES:
            assert rule in prompt, f"{rule!r} missing from {'phone' if is_phone else 'web'}"


def test_channel_blocks():
    phone = build_system_prompt(is_phone=True)
    web = build_system_prompt(is_phone=False)
    assert "CHANNEL: PHONE" in phone and "CHANNEL: WEB" not in phone
    assert "CHANNEL: WEB" in web and "CHANNEL: PHONE" not in web
    for prompt in (phone, web):
        assert "unless" in prompt and "price" in prompt.lower()  # no-volunteered-price policy


def test_prompt_uses_approved_persona():
    prompt = build_system_prompt(is_phone=True)
    assert persona_section() in prompt
    assert "AI cashier" in prompt
    assert "ONE short sentence per turn" not in prompt  # scripted delivery rule gone
    assert "TONE EXAMPLES" in prompt


def test_prompt_style_env_is_inert(monkeypatch):
    """A stale PROMPT_STYLE=legacy on a deployed host must change nothing (PR 099)."""
    monkeypatch.delenv("PROMPT_STYLE", raising=False)
    default = build_system_prompt(is_phone=True)
    monkeypatch.setenv("PROMPT_STYLE", "legacy")
    assert build_system_prompt(is_phone=True) == default
    assert "ONE short sentence per turn" not in build_system_prompt(is_phone=True)
    assert "Sure, let me connect you — one moment." not in build_system_prompt(is_phone=True)


def test_persona_reanchor_turns_env(monkeypatch):
    monkeypatch.delenv("PERSONA_REANCHOR_TURNS", raising=False)
    assert persona_reanchor_turns() == 8
    monkeypatch.setenv("PERSONA_REANCHOR_TURNS", "3")
    assert persona_reanchor_turns() == 3
    monkeypatch.setenv("PERSONA_REANCHOR_TURNS", "0")
    assert persona_reanchor_turns() == 0
    monkeypatch.setenv("PERSONA_REANCHOR_TURNS", "junk")
    assert persona_reanchor_turns() == 8


# ── periodic re-anchor injection ─────────────────────────────────────────────


class _FakeTurnCtx:
    def __init__(self):
        self.messages = []

    def add_message(self, *, role: str, content: str) -> None:
        self.messages.append((role, content))


class _FakeMessage:
    def __init__(self, text: str):
        self.text_content = text


def _run_turns(agent: RestaurantAgent, count: int) -> list[list[tuple[str, str]]]:
    """Feed `count` real user turns; return each turn's injected messages."""
    injected = []
    for i in range(count):
        ctx = _FakeTurnCtx()
        asyncio.run(
            agent.on_user_turn_completed(ctx, _FakeMessage(f"two butter chicken please {i}"))
        )
        injected.append(ctx.messages)
    return injected


def test_reanchor_injected_every_n_turns(monkeypatch):
    monkeypatch.setenv("PERSONA_REANCHOR_TURNS", "3")
    agent = RestaurantAgent(is_phone=False)
    turns = _run_turns(agent, 6)
    assert turns[0] == [] and turns[1] == []
    assert turns[2] == [("system", PERSONA_REANCHOR_LINE)]
    assert turns[3] == [] and turns[4] == []
    assert turns[5] == [("system", PERSONA_REANCHOR_LINE)]


def test_reanchor_disabled_by_zero(monkeypatch):
    monkeypatch.setenv("PERSONA_REANCHOR_TURNS", "0")
    agent = RestaurantAgent(is_phone=False)
    assert all(msgs == [] for msgs in _run_turns(agent, 4))


def test_reanchor_still_fires_with_stale_legacy_env(monkeypatch):
    """PROMPT_STYLE no longer gates the drift re-anchor (PR 099)."""
    monkeypatch.setenv("PERSONA_REANCHOR_TURNS", "2")
    monkeypatch.setenv("PROMPT_STYLE", "legacy")
    agent = RestaurantAgent(is_phone=False)
    turns = _run_turns(agent, 4)
    assert turns[1] == [("system", PERSONA_REANCHOR_LINE)]
    assert turns[3] == [("system", PERSONA_REANCHOR_LINE)]
