"""Tests for the explicit tuned VAD (PR 066)."""

from restaurant import session_config
from restaurant.session_config import (
    vad_activation_threshold,
    vad_min_silence_seconds,
)


def test_activation_threshold_default(monkeypatch):
    monkeypatch.delenv("VAD_ACTIVATION_THRESHOLD", raising=False)
    assert vad_activation_threshold() == 0.6


def test_activation_threshold_custom(monkeypatch):
    monkeypatch.setenv("VAD_ACTIVATION_THRESHOLD", "0.7")
    assert vad_activation_threshold() == 0.7


def test_min_silence_default(monkeypatch):
    monkeypatch.delenv("VAD_MIN_SILENCE_SEC", raising=False)
    assert vad_min_silence_seconds() == 0.25


def test_min_silence_custom(monkeypatch):
    monkeypatch.setenv("VAD_MIN_SILENCE_SEC", "0.4")
    assert vad_min_silence_seconds() == 0.4


def test_build_agent_session_passes_explicit_vad(monkeypatch):
    """The whole point of PR 066 item 1: an explicit VAD flips the framework's
    _using_default_vad off, so it trusts VAD end-of-speech timestamps."""
    built = {}

    class _FakeVAD:
        def __init__(self, *, model, activation_threshold, min_silence_duration):
            built["model"] = model
            built["activation_threshold"] = activation_threshold
            built["min_silence_duration"] = min_silence_duration

    captured = {}

    def _fake_session(**kwargs):
        captured.update(kwargs)
        return "session"

    monkeypatch.setattr(session_config.inference, "VAD", _FakeVAD)
    monkeypatch.setattr(session_config, "AgentSession", _fake_session)
    monkeypatch.setattr(session_config, "build_stt", lambda is_phone: "stt")
    monkeypatch.setattr(session_config, "build_llm", lambda: "llm")
    monkeypatch.setattr(session_config, "build_tts", lambda is_phone: "tts")
    monkeypatch.setenv("VAD_ACTIVATION_THRESHOLD", "0.65")
    monkeypatch.setenv("VAD_MIN_SILENCE_SEC", "0.3")

    session = session_config.build_agent_session(is_phone=False)

    assert session == "session"
    assert isinstance(captured["vad"], _FakeVAD)
    assert built == {
        "model": "silero",
        "activation_threshold": 0.65,
        "min_silence_duration": 0.3,
    }


def test_build_vad_returns_real_inference_vad():
    from livekit.agents import inference

    assert isinstance(session_config.build_vad(), inference.VAD)
