"""Tests for the end-of-utterance watchdog (PR 067)."""

import asyncio
import time
from types import SimpleNamespace

from restaurant.channels.eou_watchdog import (
    EouWatchdog,
    eou_watchdog_max_seconds,
    eou_watchdog_seconds,
)

_TIMEOUT = 0.05
_PAST_TIMEOUT = 0.15
_MAX = 0.12


class _FakeSession:
    def __init__(self):
        self._handlers = {}
        self.user_state = "listening"
        self.agent_state = "listening"
        self.commits: list[tuple[float, float]] = []
        self.clear_calls = 0
        self.commit_exc: Exception | None = None
        self._activity = SimpleNamespace(
            _audio_recognition=SimpleNamespace(_last_final_transcript_time=None)
        )

    def on(self, name):
        def _register(fn):
            self._handlers[name] = fn
            return fn

        return _register

    def emit(self, name, **fields):
        if name in self._handlers:
            self._handlers[name](SimpleNamespace(**fields))

    def commit_user_turn(self, *, transcript_timeout, stt_flush_duration):
        self.commits.append((transcript_timeout, stt_flush_duration))
        fut = asyncio.get_running_loop().create_future()
        if self.commit_exc is not None:
            fut.set_exception(self.commit_exc)
        else:
            fut.set_result("one samosa")
        return fut

    def clear_user_turn(self):
        self.clear_calls += 1

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
        self._activity._audio_recognition._last_final_transcript_time = time.time()
        self.emit("user_input_transcribed", is_final=True, transcript=text)

    def promoted_final(self, text="one samosa"):
        # commit_user_turn's interim promotion: same event on the bus, but
        # _last_final_transcript_time is NOT stamped.
        self.emit("user_input_transcribed", is_final=True, transcript=text)

    def agent_thinks(self):
        self.agent_state = "thinking"
        self.emit("agent_state_changed", new_state="thinking", old_state="listening")


def _attach(timeout=_TIMEOUT):
    session = _FakeSession()
    EouWatchdog(timeout_sec=timeout).attach(session)
    return session


def _attach_capped(timeout=_TIMEOUT, max_sec=_MAX):
    session = _FakeSession()
    EouWatchdog(timeout_sec=timeout, max_sec=max_sec).attach(session)
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


def test_watchdog_max_seconds_default(monkeypatch):
    monkeypatch.delenv("EOU_WATCHDOG_MAX_SEC", raising=False)
    assert eou_watchdog_max_seconds() == 4.0


def test_watchdog_max_seconds_custom_and_invalid(monkeypatch):
    monkeypatch.setenv("EOU_WATCHDOG_MAX_SEC", "6")
    assert eou_watchdog_max_seconds() == 6.0
    monkeypatch.setenv("EOU_WATCHDOG_MAX_SEC", "later")
    assert eou_watchdog_max_seconds() == 4.0
    monkeypatch.setenv("EOU_WATCHDOG_MAX_SEC", "-1")
    assert eou_watchdog_max_seconds() == 0.0


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
        assert session.commits == [(1.0, 2.0)]

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


# ── sliding re-arm (finding 3) ───────────────────────────────────────────────


def test_streaming_interims_slide_the_deadline():
    async def _run():
        # VAD missed the speech entirely; Soniox keeps streaming interims.
        # The deadline must slide so the commit never lands mid-utterance.
        session = _attach()
        session.user_speaks()
        session.user_stops()
        for _ in range(4):
            await asyncio.sleep(_TIMEOUT / 2)
            session.interim()
            assert session.commits == []
        await asyncio.sleep(_PAST_TIMEOUT)  # tokens stop → commit fires
        assert len(session.commits) == 1

    asyncio.run(_run())


# ── re-arm after VAD-missed turns (finding 4) ────────────────────────────────


def test_final_rearms_without_vad_transition():
    async def _run():
        session = _attach()
        session.user_speaks()
        session.interim()
        session.user_stops()
        await asyncio.sleep(_PAST_TIMEOUT)
        assert len(session.commits) == 1
        # Soniox's final for the committed turn arrives; the NEXT utterance
        # is also VAD-missed (no "speaking" transition) — the watchdog must
        # still be alive for it.
        session.final()
        session.interim("mango lassi")
        await asyncio.sleep(_PAST_TIMEOUT)
        assert len(session.commits) == 2

    asyncio.run(_run())


# ── stale-final STT reset (finding 2) ────────────────────────────────────────


def test_reset_on_thinking_when_final_still_held():
    async def _run():
        session = _attach()
        session.user_speaks()
        session.interim()
        session.user_stops()
        await asyncio.sleep(_PAST_TIMEOUT)
        assert len(session.commits) == 1
        # transcript_timeout expired → the commit promoted the interim, but
        # Soniox still holds its final. The reset lands on the thinking
        # transition, killing the held final at the socket.
        session.promoted_final()
        session.agent_thinks()
        assert session.clear_calls == 1

    asyncio.run(_run())


def test_no_reset_when_real_final_consumed():
    async def _run():
        session = _attach()
        session.user_speaks()
        session.interim()
        session.user_stops()
        await asyncio.sleep(_PAST_TIMEOUT)
        assert len(session.commits) == 1
        # Soniox finalized inside transcript_timeout — nothing stale is held.
        session.final()
        session.agent_thinks()
        assert session.clear_calls == 0

    asyncio.run(_run())


def test_no_reset_when_user_speaks_again_first():
    async def _run():
        session = _attach()
        session.user_speaks()
        session.interim()
        session.user_stops()
        await asyncio.sleep(_PAST_TIMEOUT)
        assert len(session.commits) == 1
        # New VAD-detected utterance before the thinking transition:
        # resetting would drop in-flight speech.
        session.user_speaks()
        session.agent_thinks()
        assert session.clear_calls == 0

    asyncio.run(_run())


def test_no_reset_without_watchdog_fire():
    async def _run():
        session = _attach()
        session.user_speaks()
        session.interim()
        session.user_stops()
        session.final()  # normal turn, no rescue
        session.agent_thinks()
        assert session.clear_calls == 0

    asyncio.run(_run())


# ── lifecycle (finding 5) ────────────────────────────────────────────────────


def test_close_cancels_pending_timer():
    async def _run():
        session = _attach()
        session.user_speaks()
        session.interim()
        session.user_stops()
        session.emit("close", error=None, reason="test")
        await asyncio.sleep(_PAST_TIMEOUT)
        assert session.commits == []

    asyncio.run(_run())


def test_commit_exception_is_logged_not_raised(caplog):
    async def _run():
        session = _attach()
        session.commit_exc = RuntimeError("AgentSession isn't running")
        session.user_speaks()
        session.interim()
        session.user_stops()
        await asyncio.sleep(_PAST_TIMEOUT)
        assert len(session.commits) == 1

    asyncio.run(_run())
    assert any("forced commit failed" in r.message for r in caplog.records)


# ── absolute wall-clock cap (PR 083 / gap 3) ─────────────────────────────────


def test_interims_capped_by_max_sec():
    async def _run():
        # The 16s live repro in miniature: interims keep streaming past the
        # cap, but the commit must land once, ~max_sec after VAD end-of-speech.
        session = _attach_capped()
        session.user_speaks()
        session.user_stops()
        for _ in range(8):  # 8 × (_TIMEOUT/2) = 0.2s > _MAX (0.12)
            await asyncio.sleep(_TIMEOUT / 2)
            session.interim()
        assert len(session.commits) == 1

    asyncio.run(_run())


def test_cap_disabled_slides_indefinitely():
    async def _run():
        # max_sec == 0 → bit-for-bit the pre-cap behavior: the deadline slides
        # on every interim and never caps while tokens keep arriving.
        session = _attach_capped(max_sec=0.0)
        session.user_speaks()
        session.user_stops()
        for _ in range(8):
            await asyncio.sleep(_TIMEOUT / 2)
            session.interim()
            assert session.commits == []
        await asyncio.sleep(_PAST_TIMEOUT)  # tokens stop → commit fires
        assert len(session.commits) == 1

    asyncio.run(_run())


def test_user_resumes_before_cap_no_fire():
    async def _run():
        session = _attach_capped()
        session.user_speaks()
        session.user_stops()
        for _ in range(3):  # 0.075s < _MAX
            await asyncio.sleep(_TIMEOUT / 2)
            session.interim()
        session.user_speaks()  # resumed before the cap is spent
        await asyncio.sleep(_PAST_TIMEOUT)
        assert session.commits == []

    asyncio.run(_run())


def test_final_resets_cap_budget():
    async def _run():
        session = _attach_capped()
        session.user_speaks()
        session.user_stops()
        await asyncio.sleep(_TIMEOUT / 2)
        session.interim()
        # A real final closes the turn and clears the cap anchor.
        session.final()
        # The next utterance is VAD-missed (no "speaking"/"listening"); it must
        # get a fresh budget, not fire instantly against the old stopped-at.
        session.interim("mango lassi")
        await asyncio.sleep(_TIMEOUT / 2)
        assert session.commits == []  # fresh budget — not an instant fire
        await asyncio.sleep(_PAST_TIMEOUT)
        assert len(session.commits) == 1

    asyncio.run(_run())


def test_interim_after_cap_spent_commits_immediately():
    async def _run():
        # First transcript text arrives only after the whole cap window has
        # already elapsed → the delay≤0 immediate-commit path (no extra wait).
        session = _attach_capped()
        session.user_speaks()
        session.user_stops()
        await asyncio.sleep(_MAX + _TIMEOUT)
        assert session.commits == []  # nothing to commit yet — no interim
        session.interim()  # late text; cap already spent
        assert len(session.commits) == 1  # committed synchronously

    asyncio.run(_run())
