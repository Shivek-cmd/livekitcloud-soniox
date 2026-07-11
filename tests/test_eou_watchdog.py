"""Tests for the end-of-utterance watchdog (PR 067)."""

import asyncio
from types import SimpleNamespace

from restaurant.channels.eou_watchdog import EouWatchdog, eou_watchdog_seconds

_TIMEOUT = 0.05
_PAST_TIMEOUT = 0.15


class _FakeSession:
    def __init__(self):
        self._handlers = {}
        self.user_state = "listening"
        self.agent_state = "listening"
        self.commits: list[tuple[float, float]] = []

    def on(self, name):
        def _register(fn):
            self._handlers[name] = fn
            return fn

        return _register

    def emit(self, name, **fields):
        self._handlers[name](SimpleNamespace(**fields))

    def commit_user_turn(self, *, transcript_timeout, stt_flush_duration):
        self.commits.append((transcript_timeout, stt_flush_duration))

    # Scenario helpers ------------------------------------------------------
    def user_speaks(self):
        self.user_state = "speaking"
        self.emit("user_state_changed", new_state="speaking", old_state="listening")

    def user_stops(self):
        self.user_state = "listening"
        self.emit("user_state_changed", new_state="listening", old_state="speaking")

    def interim(self, text="one samosa"):
        self.emit("user_input_transcribed", is_final=False, transcript=text)

    def final(self, text="one samosa"):
        self.emit("user_input_transcribed", is_final=True, transcript=text)


def _attach(timeout=_TIMEOUT):
    session = _FakeSession()
    EouWatchdog(timeout_sec=timeout).attach(session)
    return session


# ── env helper ───────────────────────────────────────────────────────────────


def test_watchdog_seconds_default(monkeypatch):
    monkeypatch.delenv("EOU_WATCHDOG_SEC", raising=False)
    assert eou_watchdog_seconds() == 2.0


def test_watchdog_seconds_custom_and_invalid(monkeypatch):
    monkeypatch.setenv("EOU_WATCHDOG_SEC", "3.5")
    assert eou_watchdog_seconds() == 3.5
    monkeypatch.setenv("EOU_WATCHDOG_SEC", "soon")
    assert eou_watchdog_seconds() == 2.0
    monkeypatch.setenv("EOU_WATCHDOG_SEC", "-1")
    assert eou_watchdog_seconds() == 0.0


# ── firing behavior ──────────────────────────────────────────────────────────


def test_fast_final_no_fire():
    async def _run():
        session = _attach()
        session.user_speaks()
        session.interim()
        session.user_stops()
        session.final()  # STT finalized on its own, well before the deadline
        await asyncio.sleep(_PAST_TIMEOUT)
        assert session.commits == []

    asyncio.run(_run())


def test_late_final_fires_commit():
    async def _run():
        session = _attach()
        session.user_speaks()
        session.interim()
        session.user_stops()
        await asyncio.sleep(_PAST_TIMEOUT)
        assert session.commits == [(2.0, 2.0)]

    asyncio.run(_run())


def test_user_resumes_no_fire():
    async def _run():
        session = _attach()
        session.user_speaks()
        session.interim()
        session.user_stops()
        session.user_speaks()  # resumed before the deadline
        await asyncio.sleep(_PAST_TIMEOUT)
        assert session.commits == []

    asyncio.run(_run())


def test_agent_busy_no_fire():
    async def _run():
        for busy_state in ("thinking", "speaking"):
            session = _attach()
            session.user_speaks()
            session.interim()
            session.user_stops()
            session.agent_state = busy_state
            await asyncio.sleep(_PAST_TIMEOUT)
            assert session.commits == []

    asyncio.run(_run())


def test_no_interim_no_fire():
    async def _run():
        # Pure noise: VAD tripped but Soniox produced no transcript text.
        session = _attach()
        session.user_speaks()
        session.user_stops()
        await asyncio.sleep(_PAST_TIMEOUT)
        assert session.commits == []

    asyncio.run(_run())


def test_disabled_attaches_nothing():
    session = _FakeSession()
    EouWatchdog(timeout_sec=0.0).attach(session)
    assert session._handlers == {}


def test_one_fire_per_turn_then_rearms_next_turn():
    async def _run():
        session = _attach()
        session.user_speaks()
        session.interim()
        session.user_stops()
        await asyncio.sleep(_PAST_TIMEOUT)
        assert len(session.commits) == 1
        # State flap within the same turn must not fire again.
        session.user_stops()
        await asyncio.sleep(_PAST_TIMEOUT)
        assert len(session.commits) == 1
        # Next turn stalls too — the watchdog re-arms and fires again.
        session.user_speaks()
        session.interim("mango lassi")
        session.user_stops()
        await asyncio.sleep(_PAST_TIMEOUT)
        assert len(session.commits) == 2

    asyncio.run(_run())
