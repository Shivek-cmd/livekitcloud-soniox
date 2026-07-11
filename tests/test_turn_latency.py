"""Tests for the per-turn latency tracker slice lifecycle (PR 065)."""

import logging
from types import SimpleNamespace

import pytest

from restaurant.analytics import turn_latency as tl
from restaurant.analytics.turn_latency import TurnLatencyTracker


class _FakeSession:
    def __init__(self):
        self._handlers = {}

    def on(self, name):
        def _register(fn):
            self._handlers[name] = fn
            return fn

        return _register

    def emit(self, name, **fields):
        self._handlers[name](SimpleNamespace(**fields))


class _Clock:
    def __init__(self):
        self.now = 100.0

    def tick(self, seconds):
        self.now += seconds

    def __call__(self):
        return self.now


@pytest.fixture()
def clock(monkeypatch):
    c = _Clock()
    monkeypatch.setattr(tl.time, "monotonic", c)
    return c


@pytest.fixture()
def tracker_env():
    session = _FakeSession()
    payloads: list[dict] = []
    tracker = TurnLatencyTracker(channel="test", on_turn_latency=payloads.append)
    tracker.attach(session)
    return session, tracker, payloads


def _run_turn(session, clock, transcript, stop_to_final=0.5):
    session.emit("user_state_changed", new_state="speaking", old_state="listening")
    clock.tick(2.0)
    session.emit("user_state_changed", new_state="listening", old_state="speaking")
    clock.tick(stop_to_final)
    session.emit(
        "user_input_transcribed", is_final=True, transcript=transcript, language=None
    )
    clock.tick(0.3)
    session.emit("agent_state_changed", new_state="thinking", old_state="listening")
    clock.tick(0.4)
    session.emit("agent_state_changed", new_state="speaking", old_state="thinking")


def _latency_lines(caplog):
    return [
        r.getMessage()
        for r in caplog.records
        if r.name == "turn-latency" and r.getMessage().startswith("LATENCY")
    ]


def test_every_turn_emits_summary(tracker_env, clock, caplog):
    session, _, payloads = tracker_env
    caplog.set_level(logging.INFO, logger="turn-latency")
    _run_turn(session, clock, "one samosa")
    _run_turn(session, clock, "make it two")
    _run_turn(session, clock, "that's all")
    lines = _latency_lines(caplog)
    assert len(lines) == 3
    assert "turn=1" in lines[0]
    assert "turn=2" in lines[1]
    assert "turn=3" in lines[2]
    assert len(payloads) == 3


def test_transcript_delay_in_line_and_payload(tracker_env, clock, caplog):
    session, _, payloads = tracker_env
    caplog.set_level(logging.INFO, logger="turn-latency")
    _run_turn(session, clock, "one samosa", stop_to_final=0.5)
    assert "transcript_delay=500ms" in _latency_lines(caplog)[0]
    assert payloads[0]["transcript_delay_ms"] == 500


def test_slice_resets_between_turns(tracker_env, clock, caplog):
    session, _, payloads = tracker_env
    caplog.set_level(logging.INFO, logger="turn-latency")
    _run_turn(session, clock, "one samosa", stop_to_final=0.5)
    _run_turn(session, clock, "make it two", stop_to_final=1.2)
    assert payloads[0]["transcript_delay_ms"] == 500
    assert payloads[1]["transcript_delay_ms"] == 1200
    lines = _latency_lines(caplog)
    assert 'user="make it two"' in lines[1]
    assert "one samosa" not in lines[1]


def test_final_before_listening_still_opens_turn(tracker_env, clock, caplog):
    session, _, payloads = tracker_env
    caplog.set_level(logging.INFO, logger="turn-latency")
    # Final transcript arrives before any user_state transition.
    session.emit(
        "user_input_transcribed", is_final=True, transcript="hello", language=None
    )
    clock.tick(0.3)
    session.emit("agent_state_changed", new_state="speaking", old_state="thinking")
    lines = _latency_lines(caplog)
    assert len(lines) == 1
    assert "turn=1" in lines[0]
    # A normal turn afterwards numbers as turn 2.
    _run_turn(session, clock, "one samosa")
    assert "turn=2" in _latency_lines(caplog)[1]
    assert len(payloads) == 2


def test_interim_transcripts_do_not_open_turn(tracker_env, clock, caplog):
    session, _, payloads = tracker_env
    caplog.set_level(logging.INFO, logger="turn-latency")
    session.emit(
        "user_input_transcribed", is_final=False, transcript="one sa", language=None
    )
    session.emit("agent_state_changed", new_state="speaking", old_state="thinking")
    assert _latency_lines(caplog) == []
    assert payloads == []
