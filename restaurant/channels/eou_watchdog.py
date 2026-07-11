"""Watchdog that bounds worst-case end-of-speech latency (PR 067).

In livekit-agents 1.6.5 a user turn can never commit before the STT emits a
FINAL transcript, and Soniox's semantic endpoint model can hold a final for
many seconds under continuous background noise (turnwatchdog.md Part I). The
framework's rescue path — commit_user_turn(), which silence-flushes the STT
and falls back to the interim transcript on timeout — is never called
automatically. This watchdog calls it when the VAD says the user stopped
speaking and no final arrives in time.
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass, field

from livekit.agents.voice import AgentSession

logger = logging.getLogger("eou-watchdog")

# commit_user_turn knobs (plan constants, not env — see pr/pr_067_eou-watchdog.md).
_TRANSCRIPT_TIMEOUT_SEC = 2.0
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

    def attach(self, session: AgentSession) -> None:
        if self.timeout_sec <= 0:
            logger.info("EOU watchdog disabled (EOU_WATCHDOG_SEC=0)")
            return
        self._session = session

        @session.on("user_state_changed")
        def _on_user_state(ev) -> None:
            if ev.new_state == "speaking":
                # New utterance: normal turn flow owns it again.
                self._cancel_timer()
                self._fired_this_turn = False
            elif ev.new_state == "listening":
                self._arm_timer()

        @session.on("user_input_transcribed")
        def _on_transcript(ev) -> None:
            if ev.is_final:
                # STT finalized on its own — the turn commits normally.
                self._cancel_timer()
                self._has_interim = False
            elif (ev.transcript or "").strip():
                self._has_interim = True

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
        logger.warning(
            "EOU watchdog: no final transcript %.1fs after end of speech — forcing commit",
            self.timeout_sec,
        )
        session.commit_user_turn(
            transcript_timeout=_TRANSCRIPT_TIMEOUT_SEC,
            stt_flush_duration=_STT_FLUSH_DURATION_SEC,
        )
