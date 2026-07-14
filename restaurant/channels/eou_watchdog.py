"""Watchdog that bounds worst-case end-of-speech latency (PR 067).

In livekit-agents 1.6.5 a user turn can never commit before the STT emits a
FINAL transcript, and Soniox's semantic endpoint model can hold a final for
many seconds under continuous background noise (turnwatchdog.md Part I). The
framework's rescue path — commit_user_turn(), which falls back to the interim
transcript on timeout — is never called automatically. This watchdog calls it
when the VAD says the user stopped speaking and no final arrives in time.

Note: commit_user_turn's stt_flush_duration silence flush only runs with
detached audio (audio_recognition.py:954); with a live mic the rescue is
purely "wait transcript_timeout, then promote the interim".

After a forced commit Soniox may still deliver the held final 5-30s later,
which the framework would treat as a brand-new turn (phantom turn / double
reply). To prevent that, the watchdog resets the STT stream via
session.clear_user_turn() once the agent transitions to thinking/speaking:
the reset tears down the Soniox WS and the held final dies at the socket.
The reset is skipped when a real final arrived in time (nothing stale is
held) or when the user started speaking again (a reset would drop in-flight
speech).
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass, field

from livekit.agents.voice import AgentSession

logger = logging.getLogger("eou-watchdog")

# commit_user_turn knobs (plan constants, not env — see pr/pr_067_eou-watchdog.md).
# transcript_timeout is the whole rescue wait with attached audio (the silence
# flush is a no-op there), so keep it short: 2.0s timer + 1.0s wait ≈ 3s worst
# case instead of 4-4.5s.
_TRANSCRIPT_TIMEOUT_SEC = 1.0
_STT_FLUSH_DURATION_SEC = 2.0


def eou_watchdog_seconds() -> float:
    """Delay after VAD end-of-speech before forcing a commit (EOU_WATCHDOG_SEC).

    0 disables the watchdog entirely. Keep well above the endpointing window
    (PHONE_ENDPOINTING_MAX, 0.5s) so the normal fast path always wins; 2.0 is
    conservative for slow, pausing speakers (phone-number dictation).
    """
    raw = os.getenv("EOU_WATCHDOG_SEC", "").strip()
    if not raw:
        return 2.0
    try:
        value = float(raw)
    except ValueError:
        return 2.0
    return max(0.0, value)


@dataclass
class EouWatchdog:
    timeout_sec: float = field(default_factory=eou_watchdog_seconds)
    _session: AgentSession | None = None
    _timer: asyncio.Task | None = None
    _has_interim: bool = False
    _fired_this_turn: bool = False
    _pending_stt_reset: bool = False
    _fired_at: float = 0.0

    def attach(self, session: AgentSession) -> None:
        if self.timeout_sec <= 0:
            logger.info("EOU watchdog disabled (EOU_WATCHDOG_SEC=0)")
            return
        self._session = session

        @session.on("user_state_changed")
        def _on_user_state(ev) -> None:
            if ev.new_state == "speaking":
                # New utterance: normal turn flow owns it again. Resetting
                # the STT now would drop in-flight speech, so stand down.
                self._cancel_timer()
                self._fired_this_turn = False
                self._pending_stt_reset = False
            elif ev.new_state == "listening":
                self._arm_timer()

        @session.on("user_input_transcribed")
        def _on_transcript(ev) -> None:
            if ev.is_final:
                self._cancel_timer()
                self._has_interim = False
                # The next utterance may be VAD-missed too (the same noise
                # this watchdog exists for), so a final — not just a VAD
                # "speaking" transition — must re-enable it.
                self._fired_this_turn = False
            elif (ev.transcript or "").strip():
                self._has_interim = True
                # Under noise Soniox delays even non-final tokens; slide the
                # deadline on every interim so the commit lands timeout_sec
                # after the LAST token, never mid-utterance while text is
                # still streaming in.
                if not self._fired_this_turn and session.user_state == "listening":
                    self._arm_timer()

        @session.on("agent_state_changed")
        def _on_agent_state(ev) -> None:
            # Anchor the post-rescue STT reset on the thinking transition:
            # any earlier and clear_user_turn() would wipe _audio_transcript
            # before the EOU task reads it, emptying the turn being committed.
            if not self._pending_stt_reset or ev.new_state not in ("thinking", "speaking"):
                return
            self._pending_stt_reset = False
            if self._real_final_since(self._fired_at):
                # Soniox finalized inside transcript_timeout — the commit
                # consumed it, nothing stale is held on the socket.
                return
            logger.warning(
                "EOU watchdog: resetting STT stream to drop the stale post-commit final"
            )
            try:
                session.clear_user_turn()
            except RuntimeError:
                pass  # session no longer running

        @session.on("close")
        def _on_close(ev) -> None:
            # A post-close fire would make commit_user_turn raise inside an
            # unawaited task.
            self._cancel_timer()
            self._pending_stt_reset = False

    def _arm_timer(self) -> None:
        self._cancel_timer()
        if self._fired_this_turn:
            return
        self._timer = asyncio.create_task(self._watch())

    def _cancel_timer(self) -> None:
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None

    async def _watch(self) -> None:
        await asyncio.sleep(self.timeout_sec)
        self._timer = None
        self._maybe_commit()

    def _maybe_commit(self) -> None:
        session = self._session
        if session is None or self._fired_this_turn:
            return
        if not self._has_interim:
            # Pure noise — no transcript text to commit; let the turn idle.
            logger.debug("EOU watchdog expired with no interim transcript — skipping")
            return
        if session.user_state != "listening":
            return
        if session.agent_state in ("thinking", "speaking"):
            return
        self._fired_this_turn = True
        self._pending_stt_reset = True
        self._fired_at = time.time()
        logger.warning(
            "EOU watchdog: no final transcript %.1fs after end of speech — forcing commit",
            self.timeout_sec,
        )
        fut = session.commit_user_turn(
            transcript_timeout=_TRANSCRIPT_TIMEOUT_SEC,
            stt_flush_duration=_STT_FLUSH_DURATION_SEC,
        )
        fut.add_done_callback(self._on_commit_done)

    def _real_final_since(self, since: float) -> bool:
        """Whether the STT delivered a real final after the watchdog fired.

        commit_user_turn's interim promotion emits a user_input_transcribed
        final that is indistinguishable on the event bus from a real Soniox
        final, so probe the recognition state instead: only real finals stamp
        _last_final_transcript_time (audio_recognition.py:1115). On any probe
        failure err toward False — a spurious reset costs one reconnect, a
        missed one costs a phantom turn.
        """
        session = self._session
        try:
            last = session._activity._audio_recognition._last_final_transcript_time
        except AttributeError:
            return False
        return last is not None and last >= since

    def _on_commit_done(self, fut: asyncio.Future) -> None:
        if fut.cancelled():
            logger.warning("EOU watchdog: forced commit was cancelled")
            return
        exc = fut.exception()
        if exc is not None:
            logger.error("EOU watchdog: forced commit failed", exc_info=exc)
