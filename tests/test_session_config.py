"""Tests for the min-consecutive-speech-delay gap (PR 042)."""

from restaurant.session_config import min_consecutive_speech_delay_seconds


def test_min_consecutive_speech_delay_default(monkeypatch):
    monkeypatch.delenv("MIN_CONSECUTIVE_SPEECH_DELAY_SEC", raising=False)
    assert min_consecutive_speech_delay_seconds() == 0.3


def test_min_consecutive_speech_delay_custom(monkeypatch):
    monkeypatch.setenv("MIN_CONSECUTIVE_SPEECH_DELAY_SEC", "0.5")
    assert min_consecutive_speech_delay_seconds() == 0.5
