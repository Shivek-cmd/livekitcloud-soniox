"""AgentSession voice tuning — shared latency config for phone and web.

Both channels use LiveKit TurnDetector (v1-mini) + dynamic endpointing +
preemptive TTS. Phone-only echo/background handling lives in agent.py.
"""

from __future__ import annotations

import logging
import os

from livekit import rtc
from livekit.agents import AgentSession, TurnHandlingOptions, inference
from livekit.agents.voice import room_io
from livekit.plugins import noise_cancellation

from restaurant.voice_stack import build_llm, build_stt, build_tts

logger = logging.getLogger("session-config")


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name, "").strip().lower()
    if not raw:
        return default
    return raw in ("1", "true", "yes", "on")


def phone_greeting_settle_seconds() -> float:
    """Pause after opening greeting so mobile echo fades before listening."""
    return _env_float("PHONE_GREETING_SETTLE_SEC", 2.0)


def min_consecutive_speech_delay_seconds() -> float:
    """Forced gap between two queued speech handles (PR 042).

    Without this, back-to-back session.say() calls (fillers, ladder lines,
    LLM turn replies) play with zero pause and blend into one garbled,
    run-on utterance in transcripts.
    """
    return _env_float("MIN_CONSECUTIVE_SPEECH_DELAY_SEC", 0.3)


def phone_bvc_enabled() -> bool:
    """Krisp BVC voice isolation on inbound audio (phone + web)."""
    return _env_bool("PHONE_BVC_ENABLED", True)


def phone_background_filter_enabled() -> bool:
    """Drop low-signal phone transcripts (background chatter)."""
    return _env_bool("PHONE_BACKGROUND_FILTER_ENABLED", True)


def _endpointing_delays() -> tuple[float, float]:
    """Shared phone + web silence window before Sierra replies (env-tunable)."""
    min_delay = _env_float("PHONE_ENDPOINTING_MIN", 0.2)
    max_delay = _env_float("PHONE_ENDPOINTING_MAX", 0.5)
    return min_delay, max_delay


def _turn_handling(*, is_phone: bool) -> TurnHandlingOptions:
    endpointing_min, endpointing_max = _endpointing_delays()
    if is_phone:
        min_words = int(_env_float("PHONE_INTERRUPTION_MIN_WORDS", 2))
        min_duration = _env_float("PHONE_INTERRUPTION_MIN_DURATION", 0.55)
    else:
        min_words = 1
        min_duration = 0.4

    return TurnHandlingOptions(
        turn_detection=inference.TurnDetector(version="v1-mini"),
        endpointing={
            "mode": "dynamic",
            "min_delay": endpointing_min,
            "max_delay": endpointing_max,
        },
        interruption={
            "mode": "adaptive",
            "enabled": True,
            "min_duration": min_duration,
            "min_words": min_words,
            "discard_audio_if_uninterruptible": True,
            "false_interruption_timeout": 2.0,
            "resume_false_interruption": True,
        },
        preemptive_generation={
            "enabled": _env_bool("PHONE_PREEMPTIVE_GENERATION", True),
            "preemptive_tts": _env_bool("PHONE_PREEMPTIVE_TTS", True),
            "max_speech_duration": 10.0,
            "max_retries": 2,
        },
    )


def build_room_options(*, is_phone: bool) -> room_io.RoomOptions:
    """Room audio input options — BVC telephony for SIP callers when enabled."""
    if not phone_bvc_enabled():
        logger.info("BVC disabled (PHONE_BVC_ENABLED=0)")
        return room_io.RoomOptions()

    def _select_noise_cancellation(params):
        if params.participant.kind == rtc.ParticipantKind.PARTICIPANT_KIND_SIP:
            logger.info("BVC telephony selected for SIP participant")
            return noise_cancellation.BVCTelephony()
        logger.info("BVC selected for WebRTC participant")
        return noise_cancellation.BVC()

    return room_io.RoomOptions(
        audio_input=room_io.AudioInputOptions(
            noise_cancellation=_select_noise_cancellation,
        ),
    )


def build_agent_session(*, is_phone: bool) -> AgentSession:
    """Create AgentSession with channel-appropriate STT/TTS; shared turn latency."""
    kwargs: dict = {
        "stt": build_stt(is_phone),
        "llm": build_llm(),
        "tts": build_tts(is_phone),
        "turn_handling": _turn_handling(is_phone=is_phone),
        "min_consecutive_speech_delay": min_consecutive_speech_delay_seconds(),
    }
    if is_phone:
        kwargs["aec_warmup_duration"] = _env_float("PHONE_AEC_WARMUP_SEC", 1.0)
    return AgentSession(**kwargs)
