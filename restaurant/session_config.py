"""AgentSession voice tuning — shared latency config for phone and web.

Both channels use LiveKit TurnDetector (v1-mini) + dynamic endpointing +
preemptive TTS. Phone-only echo handling (AEC warmup, greeting settle) lives
in agent.py / phone_echo.py.
"""

from __future__ import annotations

import os

from livekit.agents import AgentSession, TurnHandlingOptions, inference

from restaurant.voice_stack import build_llm, build_stt, build_tts


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


def _turn_handling() -> TurnHandlingOptions:
    # Default TurnDetector thresholds (LiveKit-calibrated). Logs showed eou_delay
    # hitting max_delay=2.5s — lower cap commits turns faster on Punjabi calls.
    return TurnHandlingOptions(
        turn_detection=inference.TurnDetector(version="v1-mini"),
        endpointing={
            "mode": "dynamic",
            "min_delay": _env_float("PHONE_ENDPOINTING_MIN", 0.2),
            "max_delay": _env_float("PHONE_ENDPOINTING_MAX", 0.8),
        },
        interruption={
            "mode": "adaptive",
            "enabled": True,
            "min_duration": _env_float("PHONE_INTERRUPTION_MIN_DURATION", 0.4),
            "min_words": int(_env_float("PHONE_INTERRUPTION_MIN_WORDS", 1)),
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


def build_agent_session(*, is_phone: bool) -> AgentSession:
    """Create AgentSession with channel-appropriate STT/TTS; shared turn latency."""
    turn_handling = _turn_handling()
    kwargs: dict = {
        "stt": build_stt(is_phone),
        "llm": build_llm(),
        "tts": build_tts(is_phone),
        "turn_handling": turn_handling,
    }
    if is_phone:
        # Cloud telephony path + trunk Krisp handle most echo; keep a short AEC warmup.
        kwargs["aec_warmup_duration"] = _env_float("PHONE_AEC_WARMUP_SEC", 1.0)
    return AgentSession(**kwargs)
