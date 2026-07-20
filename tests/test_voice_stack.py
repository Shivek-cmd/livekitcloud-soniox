"""Tests for the env-tunable Soniox endpoint knobs (PR 064 + PR 066)."""

import asyncio
import json

from restaurant.voice_stack import (
    _ConfigInjectingWS,
    _WSConnectHandle,
    build_llm,
    gemini_thinking_budget,
    is_gemini_model,
    llm_model_name,
    stt_endpoint_latency_adjustment_level,
    stt_endpoint_sensitivity,
    stt_max_endpoint_delay_ms,
)


# ── LLM_MODEL / OPENAI_LLM_MODEL (PR 074 + PR 080) ───────────────────────────


def _clear_model_env(monkeypatch):
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_LLM_MODEL", raising=False)


def test_llm_model_default(monkeypatch):
    _clear_model_env(monkeypatch)
    assert llm_model_name() == "gpt-4.1-mini"


def test_llm_model_override(monkeypatch):
    _clear_model_env(monkeypatch)
    monkeypatch.setenv("OPENAI_LLM_MODEL", "gpt-4o-mini")
    assert llm_model_name() == "gpt-4o-mini"


def test_llm_model_blank_falls_back(monkeypatch):
    _clear_model_env(monkeypatch)
    monkeypatch.setenv("OPENAI_LLM_MODEL", "   ")
    assert llm_model_name() == "gpt-4.1-mini"


def test_llm_model_provider_agnostic_var_wins(monkeypatch):
    _clear_model_env(monkeypatch)
    monkeypatch.setenv("OPENAI_LLM_MODEL", "gpt-4.1")
    monkeypatch.setenv("LLM_MODEL", "gemini-2.5-flash")
    assert llm_model_name() == "gemini-2.5-flash"


def test_is_gemini_model():
    assert is_gemini_model("gemini-2.5-flash")
    assert is_gemini_model("gemini-2.5-pro")
    assert not is_gemini_model("gpt-4.1-mini")


def test_gemini_thinking_budget_default_zero(monkeypatch):
    monkeypatch.delenv("GEMINI_THINKING_BUDGET", raising=False)
    assert gemini_thinking_budget() == 0


def test_gemini_thinking_budget_override_and_invalid(monkeypatch):
    monkeypatch.setenv("GEMINI_THINKING_BUDGET", "512")
    assert gemini_thinking_budget() == 512
    monkeypatch.setenv("GEMINI_THINKING_BUDGET", "lots")
    assert gemini_thinking_budget() == 0
    monkeypatch.setenv("GEMINI_THINKING_BUDGET", "-5")
    assert gemini_thinking_budget() == 0


def test_build_llm_routes_openai(monkeypatch):
    _clear_model_env(monkeypatch)
    monkeypatch.setenv("LLM_MODEL", "gpt-4.1-mini")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    from livekit.plugins import openai

    assert isinstance(build_llm(), openai.LLM)


def test_build_llm_routes_gemini_with_fallback(monkeypatch):
    # PR 080 decision: gemini primary wrapped in a FallbackAdapter with an
    # OpenAI fallback (Gemini's non-configurable PROHIBITED_CONTENT filter
    # can block an ordinary delivery-order turn).
    _clear_model_env(monkeypatch)
    monkeypatch.setenv("LLM_MODEL", "gemini-3.5-flash")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.delenv("LLM_FALLBACK_MODEL", raising=False)
    from livekit.agents.llm import FallbackAdapter
    from livekit.plugins import google, openai

    adapter = build_llm()
    assert isinstance(adapter, FallbackAdapter)
    primary, fallback = adapter._llm_instances
    assert isinstance(primary, google.LLM)
    assert isinstance(fallback, openai.LLM)


def test_build_llm_gemini_fallback_disabled(monkeypatch):
    _clear_model_env(monkeypatch)
    monkeypatch.setenv("LLM_MODEL", "gemini-3.5-flash")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("LLM_FALLBACK_MODEL", "none")
    from livekit.plugins import google

    assert isinstance(build_llm(), google.LLM)


def test_build_llm_gemini_pro_floors_thinking_budget(monkeypatch):
    # gemini-*-pro refuses thinking_budget=0 (API minimum 128); the default
    # config must not produce a request the API will 400.
    _clear_model_env(monkeypatch)
    monkeypatch.setenv("LLM_MODEL", "gemini-2.5-pro")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.delenv("GEMINI_THINKING_BUDGET", raising=False)
    from livekit.plugins import google

    captured: dict = {}
    real_init = google.LLM.__init__

    def spy_init(self, **kwargs):
        captured.update(kwargs)
        real_init(self, **kwargs)

    monkeypatch.setattr(google.LLM, "__init__", spy_init)
    build_llm()
    assert captured["thinking_config"]["thinking_budget"] == 128


def test_build_llm_gemini3_uses_thinking_level(monkeypatch):
    # Gemini 3 rejects thinking_budget; it takes thinking_level (min "low").
    _clear_model_env(monkeypatch)
    monkeypatch.setenv("LLM_MODEL", "gemini-3.5-flash")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("LLM_FALLBACK_MODEL", "none")
    from livekit.plugins import google

    captured: dict = {}
    real_init = google.LLM.__init__

    def spy_init(self, **kwargs):
        captured.update(kwargs)
        real_init(self, **kwargs)

    monkeypatch.setattr(google.LLM, "__init__", spy_init)
    build_llm()
    assert captured["thinking_config"] == {
        "thinking_level": "low",
        "include_thoughts": False,
    }


# ── SONIOX_MAX_ENDPOINT_DELAY_MS ──────────────────────────────────────────────


def test_max_endpoint_delay_default(monkeypatch):
    monkeypatch.delenv("SONIOX_MAX_ENDPOINT_DELAY_MS", raising=False)
    assert stt_max_endpoint_delay_ms() == 1000


def test_max_endpoint_delay_custom(monkeypatch):
    monkeypatch.setenv("SONIOX_MAX_ENDPOINT_DELAY_MS", "800")
    assert stt_max_endpoint_delay_ms() == 800


def test_max_endpoint_delay_invalid_falls_back(monkeypatch):
    monkeypatch.setenv("SONIOX_MAX_ENDPOINT_DELAY_MS", "fast")
    assert stt_max_endpoint_delay_ms() == 1000


def test_max_endpoint_delay_clamped_low(monkeypatch):
    # STTOptions raises outside 500-3000 — clamp instead of crashing the worker.
    monkeypatch.setenv("SONIOX_MAX_ENDPOINT_DELAY_MS", "100")
    assert stt_max_endpoint_delay_ms() == 500


def test_max_endpoint_delay_clamped_high(monkeypatch):
    monkeypatch.setenv("SONIOX_MAX_ENDPOINT_DELAY_MS", "10000")
    assert stt_max_endpoint_delay_ms() == 3000


# ── SONIOX_ENDPOINT_SENSITIVITY ───────────────────────────────────────────────


def test_endpoint_sensitivity_default_is_soniox_rec(monkeypatch):
    monkeypatch.delenv("SONIOX_ENDPOINT_SENSITIVITY", raising=False)
    assert stt_endpoint_sensitivity() == 0.3


def test_endpoint_sensitivity_explicit_unset_is_none(monkeypatch):
    for sentinel in ("", "none", "unset", "default"):
        monkeypatch.setenv("SONIOX_ENDPOINT_SENSITIVITY", sentinel)
        assert stt_endpoint_sensitivity() is None


def test_endpoint_sensitivity_custom(monkeypatch):
    monkeypatch.setenv("SONIOX_ENDPOINT_SENSITIVITY", "0.5")
    assert stt_endpoint_sensitivity() == 0.5


def test_endpoint_sensitivity_invalid_falls_back_to_default(monkeypatch):
    monkeypatch.setenv("SONIOX_ENDPOINT_SENSITIVITY", "high")
    assert stt_endpoint_sensitivity() == 0.3


def test_endpoint_sensitivity_clamped(monkeypatch):
    monkeypatch.setenv("SONIOX_ENDPOINT_SENSITIVITY", "5")
    assert stt_endpoint_sensitivity() == 1.0
    monkeypatch.setenv("SONIOX_ENDPOINT_SENSITIVITY", "-5")
    assert stt_endpoint_sensitivity() == -1.0


# ── SONIOX_ENDPOINT_LATENCY_ADJUSTMENT_LEVEL ─────────────────────────────────


def test_latency_level_default(monkeypatch):
    monkeypatch.delenv("SONIOX_ENDPOINT_LATENCY_ADJUSTMENT_LEVEL", raising=False)
    assert stt_endpoint_latency_adjustment_level() == 2


def test_latency_level_explicit_unset_is_none(monkeypatch):
    monkeypatch.setenv("SONIOX_ENDPOINT_LATENCY_ADJUSTMENT_LEVEL", "none")
    assert stt_endpoint_latency_adjustment_level() is None


def test_latency_level_custom_and_clamped(monkeypatch):
    monkeypatch.setenv("SONIOX_ENDPOINT_LATENCY_ADJUSTMENT_LEVEL", "1")
    assert stt_endpoint_latency_adjustment_level() == 1
    monkeypatch.setenv("SONIOX_ENDPOINT_LATENCY_ADJUSTMENT_LEVEL", "9")
    assert stt_endpoint_latency_adjustment_level() == 3


def test_latency_level_invalid_falls_back(monkeypatch):
    monkeypatch.setenv("SONIOX_ENDPOINT_LATENCY_ADJUSTMENT_LEVEL", "fast")
    assert stt_endpoint_latency_adjustment_level() == 2


# ── WS config injection ──────────────────────────────────────────────────────


class _FakeWS:
    def __init__(self):
        self.sent: list[str] = []

    async def send_str(self, data: str):
        self.sent.append(data)

    def custom_attr(self) -> str:
        return "delegated"


def test_ws_injects_first_message_only():
    fake = _FakeWS()
    ws = _ConfigInjectingWS(fake, {"endpoint_latency_adjustment_level": 2})

    async def _send():
        await ws.send_str(json.dumps({"model": "stt-rt-v5"}))
        await ws.send_str('{"type": "keepalive"}')

    asyncio.run(_send())
    first = json.loads(fake.sent[0])
    assert first == {"model": "stt-rt-v5", "endpoint_latency_adjustment_level": 2}
    assert json.loads(fake.sent[1]) == {"type": "keepalive"}


def test_ws_delegates_other_attrs():
    ws = _ConfigInjectingWS(_FakeWS(), {})
    assert ws.custom_attr() == "delegated"


class _FakeWSRequest:
    """Mimics aiohttp's awaitable-context-manager ws_connect return value."""

    def __init__(self, ws):
        self._ws = ws
        self.exited = False

    def __await__(self):
        async def _connect():
            return self._ws

        return _connect().__await__()

    async def __aenter__(self):
        return self._ws

    async def __aexit__(self, exc_type, exc, tb):
        self.exited = True
        return None


def test_ws_connect_handle_awaitable():
    fake = _FakeWS()
    handle = _WSConnectHandle(_FakeWSRequest(fake), {})

    async def _run():
        ws = await handle
        assert isinstance(ws, _ConfigInjectingWS)
        assert ws._inner_ws is fake

    asyncio.run(_run())


def test_ws_connect_handle_context_manager():
    fake = _FakeWS()
    request = _FakeWSRequest(fake)
    handle = _WSConnectHandle(request, {})

    async def _run():
        async with handle as ws:
            assert isinstance(ws, _ConfigInjectingWS)
            assert ws._inner_ws is fake
        assert request.exited

    asyncio.run(_run())
