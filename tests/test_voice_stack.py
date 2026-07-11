"""Tests for the env-tunable Soniox endpoint knobs (PR 064)."""

from restaurant.voice_stack import stt_endpoint_sensitivity, stt_max_endpoint_delay_ms


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


def test_endpoint_sensitivity_default_is_none(monkeypatch):
    monkeypatch.delenv("SONIOX_ENDPOINT_SENSITIVITY", raising=False)
    assert stt_endpoint_sensitivity() is None


def test_endpoint_sensitivity_custom(monkeypatch):
    monkeypatch.setenv("SONIOX_ENDPOINT_SENSITIVITY", "0.3")
    assert stt_endpoint_sensitivity() == 0.3


def test_endpoint_sensitivity_invalid_falls_back_to_none(monkeypatch):
    monkeypatch.setenv("SONIOX_ENDPOINT_SENSITIVITY", "high")
    assert stt_endpoint_sensitivity() is None


def test_endpoint_sensitivity_clamped(monkeypatch):
    monkeypatch.setenv("SONIOX_ENDPOINT_SENSITIVITY", "5")
    assert stt_endpoint_sensitivity() == 1.0
    monkeypatch.setenv("SONIOX_ENDPOINT_SENSITIVITY", "-5")
    assert stt_endpoint_sensitivity() == -1.0
