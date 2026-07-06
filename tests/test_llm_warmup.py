"""Tests for LLM prompt-cache warmup."""

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


def test_warm_llm_cache_sends_system_prompt(monkeypatch):
    monkeypatch.setenv("LLM_WARMUP_ENABLED", "1")

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock()

    with patch("restaurant.llm_warmup.AsyncOpenAI", return_value=mock_client):
        asyncio.run(warm_llm_cache(is_phone=True))

    mock_client.chat.completions.create.assert_awaited_once()
    kwargs = mock_client.chat.completions.create.call_args.kwargs
    assert kwargs["model"] == "gpt-4o-mini"
    assert kwargs["max_tokens"] == 1
    assert kwargs["messages"][0]["role"] == "system"
    assert len(kwargs["messages"][0]["content"]) > 0
    assert kwargs["messages"][1]["role"] == "user"


def test_warm_llm_cache_skipped_when_disabled(monkeypatch):
    monkeypatch.setenv("LLM_WARMUP_ENABLED", "0")

    with patch("restaurant.llm_warmup.AsyncOpenAI") as mock_ctor:
        asyncio.run(warm_llm_cache(is_phone=False))
        mock_ctor.assert_not_called()


def test_warm_llm_cache_swallows_errors(monkeypatch):
    monkeypatch.setenv("LLM_WARMUP_ENABLED", "1")

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(side_effect=RuntimeError("boom"))

    with patch("restaurant.llm_warmup.AsyncOpenAI", return_value=mock_client):
        asyncio.run(warm_llm_cache(is_phone=True))  # must not raise


def test_schedule_llm_warmup_creates_task(monkeypatch):
    monkeypatch.setenv("LLM_WARMUP_ENABLED", "1")

    with patch("restaurant.llm_warmup.asyncio.create_task") as create_task:
        schedule_llm_warmup(is_phone=True)
        create_task.assert_called_once()
        coro = create_task.call_args[0][0]
        assert asyncio.iscoroutine(coro)
        coro.close()


def test_schedule_llm_warmup_noop_when_disabled(monkeypatch):
    monkeypatch.setenv("LLM_WARMUP_ENABLED", "0")

    with patch("restaurant.llm_warmup.asyncio.create_task") as create_task:
        result = schedule_llm_warmup(is_phone=True)
        create_task.assert_not_called()
        assert result is None
