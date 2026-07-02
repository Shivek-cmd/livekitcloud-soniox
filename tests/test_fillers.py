"""Tests for intent-based voice fillers (PR 031)."""

import os
from collections import deque

import pytest

from restaurant.conversation import CustomerLanguage, UserIntent
from restaurant.fillers import (
    agent_session_busy,
    fillers_enabled,
    pick_filler,
    should_use_filler,
)
from restaurant.order_flow import OrderPhase


@pytest.fixture(autouse=True)
def _fillers_off(monkeypatch):
    monkeypatch.delenv("FILLERS_ENABLED", raising=False)


def test_fillers_enabled_env(monkeypatch):
    monkeypatch.setenv("FILLERS_ENABLED", "1")
    assert fillers_enabled() is True
    monkeypatch.setenv("FILLERS_ENABLED", "0")
    assert fillers_enabled() is False
    monkeypatch.delenv("FILLERS_ENABLED", raising=False)
    assert fillers_enabled() is False


def test_ask_availability_processing_punjabi(monkeypatch):
    monkeypatch.setenv("FILLERS_ENABLED", "1")
    line = pick_filler(
        intent=UserIntent.ASK_AVAILABILITY,
        phase=OrderPhase.BROWSING,
        lang=CustomerLanguage.PUNJABI,
    )
    assert line in ("ਇੱਕ minute.", "ਮੈਂ ਵੇਖਦੀ ਹਾਂ.", "menu check kardi haan.")


def test_add_item_ack_english(monkeypatch):
    monkeypatch.setenv("FILLERS_ENABLED", "1")
    line = pick_filler(
        intent=UserIntent.ADD_ITEM,
        phase=OrderPhase.COLLECTING_ITEMS,
        lang=CustomerLanguage.ENGLISH,
    )
    assert line in ("Got it.", "Sure.", "Okay.")


def test_blocked_confirming_phase(monkeypatch):
    monkeypatch.setenv("FILLERS_ENABLED", "1")
    assert (
        pick_filler(
            intent=UserIntent.ASK_AVAILABILITY,
            phase=OrderPhase.CONFIRMING,
            lang=CustomerLanguage.ENGLISH,
        )
        is None
    )


def test_blocked_confirm_yes_intent(monkeypatch):
    monkeypatch.setenv("FILLERS_ENABLED", "1")
    assert (
        pick_filler(
            intent=UserIntent.CONFIRM_YES,
            phase=OrderPhase.BROWSING,
            lang=CustomerLanguage.ENGLISH,
        )
        is None
    )


def test_blocked_when_disabled():
    assert (
        pick_filler(
            intent=UserIntent.GENERAL,
            phase=OrderPhase.BROWSING,
            lang=CustomerLanguage.ENGLISH,
        )
        is None
    )


def test_blocked_chitchat_browsing(monkeypatch):
    monkeypatch.setenv("FILLERS_ENABLED", "1")
    assert (
        pick_filler(
            intent=UserIntent.GENERAL,
            phase=OrderPhase.BROWSING,
            lang=CustomerLanguage.ENGLISH,
            user_text="Hey Sheera, how are you?",
        )
        is None
    )


def test_blocked_hangup_started(monkeypatch):
    monkeypatch.setenv("FILLERS_ENABLED", "1")
    assert (
        pick_filler(
            intent=UserIntent.GENERAL,
            phase=OrderPhase.BROWSING,
            lang=CustomerLanguage.ENGLISH,
            hangup_started=True,
        )
        is None
    )


def test_blocked_agent_busy(monkeypatch):
    monkeypatch.setenv("FILLERS_ENABLED", "1")
    assert (
        pick_filler(
            intent=UserIntent.GENERAL,
            phase=OrderPhase.BROWSING,
            lang=CustomerLanguage.ENGLISH,
            agent_busy=True,
        )
        is None
    )


def test_anti_repeat(monkeypatch):
    monkeypatch.setenv("FILLERS_ENABLED", "1")
    recent: deque[str] = deque(maxlen=3)
    first = pick_filler(
        intent=UserIntent.ASK_PRICE,
        phase=OrderPhase.BROWSING,
        lang=CustomerLanguage.ENGLISH,
        recent=recent,
    )
    assert first is not None
    recent.append(first)
    second = pick_filler(
        intent=UserIntent.ASK_PRICE,
        phase=OrderPhase.BROWSING,
        lang=CustomerLanguage.ENGLISH,
        recent=recent,
    )
    assert second is not None
    assert second != first


def test_mixed_language_pool(monkeypatch):
    monkeypatch.setenv("FILLERS_ENABLED", "1")
    line = pick_filler(
        intent=UserIntent.GENERAL,
        phase=OrderPhase.AWAITING_MORE,
        lang=CustomerLanguage.MIXED,
    )
    assert line in (
        "Let me check ji.",
        "ਇੱਕ minute.",
        "One moment ji.",
    )


def test_hindi_processing(monkeypatch):
    monkeypatch.setenv("FILLERS_ENABLED", "1")
    line = pick_filler(
        intent=UserIntent.ASK_PRICE,
        phase=OrderPhase.BROWSING,
        lang=CustomerLanguage.HINDI,
    )
    assert line in ("एक minute.", "मैं देखती हूँ.", "ज़रा check करती हूँ.")


def test_should_use_filler_general_browsing(monkeypatch):
    monkeypatch.setenv("FILLERS_ENABLED", "1")
    assert not should_use_filler(
        intent=UserIntent.GENERAL,
        phase=OrderPhase.BROWSING,
    )
    assert should_use_filler(
        intent=UserIntent.GENERAL,
        phase=OrderPhase.COLLECTING_ITEMS,
        user_text="what desserts do you have",
    )


def test_agent_session_busy():
    class _Session:
        agent_state = "thinking"

    assert agent_session_busy(_Session()) is True

    class _Listening:
        agent_state = "listening"

    assert agent_session_busy(_Listening()) is False

    class _NoState:
        pass

    assert agent_session_busy(_NoState()) is False
