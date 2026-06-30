"""Tests for auto hang-up after order."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from restaurant.call_control import (
    end_call_after_goodbye,
    hangup_after_order_enabled,
    hangup_grace_seconds,
    schedule_call_hangup,
)


def test_hangup_enabled_default(monkeypatch):
    monkeypatch.delenv("AUTO_HANGUP_AFTER_ORDER", raising=False)
    assert hangup_after_order_enabled() is True


def test_hangup_disabled(monkeypatch):
    monkeypatch.setenv("AUTO_HANGUP_AFTER_ORDER", "0")
    assert hangup_after_order_enabled() is False


def test_hangup_grace_default(monkeypatch):
    monkeypatch.delenv("AUTO_HANGUP_GRACE_SEC", raising=False)
    assert hangup_grace_seconds() == 1.0


def test_hangup_grace_custom(monkeypatch):
    monkeypatch.setenv("AUTO_HANGUP_GRACE_SEC", "0.5")
    assert hangup_grace_seconds() == 0.5


def test_end_call_after_goodbye_deletes_room_and_shuts_down(monkeypatch):
    monkeypatch.setenv("AUTO_HANGUP_AFTER_ORDER", "1")
    monkeypatch.setenv("AUTO_HANGUP_GRACE_SEC", "0")

    session = MagicMock()
    job_ctx = MagicMock()
    job_ctx.room.name = "phone-test-room"
    job_ctx.delete_room = AsyncMock()

    speech = MagicMock()
    speech.__await__ = lambda self: iter([])

    asyncio.run(
        end_call_after_goodbye(
            session,
            job_ctx,
            reason="order_placed",
            channel="phone",
            speech_handle=speech,
        )
    )

    job_ctx.delete_room.assert_awaited_once()
    session.shutdown.assert_called_once_with(drain=False)


def test_end_call_skipped_when_disabled(monkeypatch):
    monkeypatch.setenv("AUTO_HANGUP_AFTER_ORDER", "0")

    session = MagicMock()
    job_ctx = MagicMock()
    job_ctx.delete_room = AsyncMock()

    asyncio.run(
        end_call_after_goodbye(
            session,
            job_ctx,
            reason="order_placed",
            channel="web",
            speech_handle=None,
        )
    )

    job_ctx.delete_room.assert_not_called()
    session.shutdown.assert_not_called()


def test_schedule_call_hangup_creates_task(monkeypatch):
    monkeypatch.setenv("AUTO_HANGUP_AFTER_ORDER", "1")

    session = MagicMock()
    job_ctx = MagicMock()
    job_ctx.room.name = "room-x"

    with patch("restaurant.call_control.asyncio.create_task") as create_task:
        schedule_call_hangup(
            session,
            job_ctx,
            reason="order_placed",
            channel="web",
        )
        create_task.assert_called_once()
        coro = create_task.call_args[0][0]
        assert asyncio.iscoroutine(coro)
        coro.close()
