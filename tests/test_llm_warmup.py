"""Tests for LLM prompt-cache warmup (v2 — real ChatContext + real tools)."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from restaurant.llm_warmup import (
    schedule_llm_warmup,
    warm_llm_cache,
    warmup_enabled,
)


def test_warmup_enabled_default(monkeypatch):
    monkeypatch.delenv("LLM_WARMUP_ENABLED", raising=False)
    assert warmup_enabled() is True


def test_warmup_disabled(monkeypatch):
    monkeypatch.setenv("LLM_WARMUP_ENABLED", "0")
    assert warmup_enabled() is False


def _mock_llm_stream():
    stream = MagicMock()
    stream.collect = AsyncMock()
    return stream


def test_warm_llm_cache_sends_system_prompt_and_tools(monkeypatch):
    monkeypatch.setenv("LLM_WARMUP_ENABLED", "1")

    mock_llm = MagicMock()
    mock_llm.chat = MagicMock(return_value=_mock_llm_stream())
    fake_tools = ["tool_a", "tool_b"]

    with patch("restaurant.llm_warmup.build_llm", return_value=mock_llm):
        asyncio.run(warm_llm_cache(is_phone=True, tools=fake_tools))

    mock_llm.chat.assert_called_once()
    kwargs = mock_llm.chat.call_args.kwargs
    assert kwargs["tools"] == fake_tools
    assert kwargs["extra_kwargs"] == {"max_completion_tokens": 1}
    chat_ctx = kwargs["chat_ctx"]
    messages = list(chat_ctx.items)
    assert messages[0].role == "system"
    assert len(messages[0].content[0]) > 0
    assert messages[1].role == "user"
    mock_llm.chat.return_value.collect.assert_awaited_once()


def test_warm_llm_cache_skipped_when_disabled(monkeypatch):
    monkeypatch.setenv("LLM_WARMUP_ENABLED", "0")

    with patch("restaurant.llm_warmup.build_llm") as mock_build:
        asyncio.run(warm_llm_cache(is_phone=False, tools=[]))
        mock_build.assert_not_called()


def test_warm_llm_cache_swallows_errors(monkeypatch):
    monkeypatch.setenv("LLM_WARMUP_ENABLED", "1")

    mock_llm = MagicMock()
    mock_llm.chat = MagicMock(side_effect=RuntimeError("boom"))

    with patch("restaurant.llm_warmup.build_llm", return_value=mock_llm):
        asyncio.run(warm_llm_cache(is_phone=True, tools=[]))  # must not raise


def test_schedule_llm_warmup_creates_task(monkeypatch):
    monkeypatch.setenv("LLM_WARMUP_ENABLED", "1")

    with patch("restaurant.llm_warmup.asyncio.create_task") as create_task:
        schedule_llm_warmup(is_phone=True, tools=[])
        create_task.assert_called_once()
        coro = create_task.call_args[0][0]
        assert asyncio.iscoroutine(coro)
        coro.close()


def test_schedule_llm_warmup_noop_when_disabled(monkeypatch):
    monkeypatch.setenv("LLM_WARMUP_ENABLED", "0")

    with patch("restaurant.llm_warmup.asyncio.create_task") as create_task:
        result = schedule_llm_warmup(is_phone=True, tools=[])
        create_task.assert_not_called()
        assert result is None
