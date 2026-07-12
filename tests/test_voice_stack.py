"""Tests for the env-tunable Soniox endpoint knobs (PR 064 + PR 066)."""

import asyncio
import json

from restaurant.voice_stack import (
    _ConfigInjectingWS,
    stt_endpoint_latency_adjustment_level,
    stt_endpoint_sensitivity,
    stt_max_endpoint_delay_ms,
)


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
