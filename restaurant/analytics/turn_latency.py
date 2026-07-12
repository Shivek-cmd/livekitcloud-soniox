"""Per-turn latency logging for phone/web voice sessions."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field

from livekit.agents.metrics import EOUMetrics, LLMMetrics, TTSMetrics
from livekit.agents.metrics.utils import log_metrics
from livekit.agents.voice import AgentSession

logger = logging.getLogger("turn-latency")


@dataclass
class _TurnSlice:
    turn_index: int = 0
    user_final_at: float | None = None
    user_stopped_at: float | None = None
    thinking_at: float | None = None
    speaking_at: float | None = None
    llm_ttft: float | None = None
    tts_ttfb: float | None = None
    eou_delay: float | None = None
    transcript: str = ""

    def reset(self, turn_index: int) -> None:
        self.turn_index = turn_index
        self.user_final_at = None
        self.user_stopped_at = None
        self.thinking_at = None
        self.speaking_at = None
        self.llm_ttft = None
        self.tts_ttfb = None
        self.eou_delay = None
        self.transcript = ""


@dataclass
class TurnLatencyTracker:
    channel: str
    on_turn_latency: Callable[[dict], None] | None = None
    _turn: _TurnSlice = field(default_factory=_TurnSlice)
    _turn_counter: int = 0
    _turn_active: bool = False
    _user_was_speaking: bool = False

    def _ms(self, start: float | None, end: float | None) -> int | None:
        if start is None or end is None:
            return None
        return int((end - start) * 1000)

    def _emit_summary(self) -> None:
        t = self._turn
        if t.user_stopped_at is None and t.user_final_at is None:
            return
        anchor = t.user_stopped_at or t.user_final_at
        parts = [
            f"turn={t.turn_index}",
            f"channel={self.channel}",
        ]
        if t.transcript:
            snippet = t.transcript[:60].replace("\n", " ")
            parts.append(f'user="{snippet}"')
        if t.eou_delay is not None:
            parts.append(f"eou_delay={t.eou_delay:.2f}s")
        transcript_delay = self._ms(t.user_stopped_at, t.user_final_at)
        if transcript_delay is not None:
            parts.append(f"transcript_delay={transcript_delay}ms")
        stop_to_think = self._ms(anchor, t.thinking_at)
        stop_to_speak = self._ms(anchor, t.speaking_at)
        if stop_to_think is not None:
            parts.append(f"user_stop→thinking={stop_to_think}ms")
        if stop_to_speak is not None:
            parts.append(f"user_stop→speaking={stop_to_speak}ms")
        if t.llm_ttft is not None:
            parts.append(f"llm_ttft={t.llm_ttft:.2f}s")
        if t.tts_ttfb is not None:
            parts.append(f"tts_ttfb={t.tts_ttfb:.2f}s")
        logger.info("LATENCY %s", " | ".join(parts))
        if self.on_turn_latency is not None:
            anchor = t.user_stopped_at or t.user_final_at
            self.on_turn_latency({
                "eou_delay": t.eou_delay,
                "llm_ttft": t.llm_ttft,
                "tts_ttfb": t.tts_ttfb,
                "transcript_delay_ms": transcript_delay,
                "user_stop_to_speaking_ms": self._ms(anchor, t.speaking_at),
            })
        self._turn_active = False

    def _begin_turn(self) -> None:
        self._turn_counter += 1
        self._turn.reset(self._turn_counter)
        self._turn_active = True

    def attach(self, session: AgentSession) -> None:
        @session.on("user_input_transcribed")
        def _on_transcript(ev) -> None:
            if not ev.is_final:
                return
            now = time.monotonic()
            if not self._turn_active:
                self._begin_turn()
            self._turn.user_final_at = now
            self._turn.transcript = (ev.transcript or "").strip()
            lang = getattr(ev, "language", None)
            if lang:
                logger.debug("STT language=%s turn=%d", lang, self._turn.turn_index)

        @session.on("user_state_changed")
        def _on_user_state(ev) -> None:
            if ev.new_state == "speaking":
                self._user_was_speaking = True
                if not self._turn_active:
                    self._begin_turn()
            elif ev.new_state == "listening" and self._user_was_speaking:
                self._user_was_speaking = False
                now = time.monotonic()
                if not self._turn_active:
                    self._begin_turn()
                if self._turn.user_stopped_at is None:
                    self._turn.user_stopped_at = now

        @session.on("agent_state_changed")
        def _on_agent_state(ev) -> None:
            now = time.monotonic()
            if ev.new_state == "thinking" and self._turn.thinking_at is None:
                self._turn.thinking_at = now
            elif ev.new_state == "speaking" and self._turn.speaking_at is None:
                self._turn.speaking_at = now
                self._emit_summary()

        @session.on("metrics_collected")
        def _on_metrics(ev) -> None:
            log_metrics(ev.metrics, logger=logger)
            m = ev.metrics
            if isinstance(m, LLMMetrics) and self._turn.llm_ttft is None:
                self._turn.llm_ttft = m.ttft
            elif isinstance(m, TTSMetrics) and self._turn.tts_ttfb is None:
                self._turn.tts_ttfb = m.ttfb
            elif isinstance(m, EOUMetrics) and self._turn.eou_delay is None:
                self._turn.eou_delay = m.end_of_utterance_delay
