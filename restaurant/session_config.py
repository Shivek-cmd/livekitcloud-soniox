"""AgentSession voice tuning — phone latency (Tier A) vs web.

Phone uses LiveKit TurnDetector + dynamic endpointing + preemptive TTS.
Echo is handled by Cloud SIP/Krisp + phone_echo.py; we no longer add a full
second of endpointing or disable interruptions globally.
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
    return _env_float("PHONE_GREETING_SETTLE_SEC", 2.5)


def _phone_turn_handling() -> TurnHandlingOptions:
    # Punjabi (pa) is not in TurnDetector's 14-language map; Soniox often tags hi/en.
    # Slightly patient Hindi threshold reduces cutting off mid-sentence on code-mixed calls.
    turn_detection = inference.TurnDetector(
        unlikely_threshold={"hi": 0.52, "en": 0.48},
    )
    return TurnHandlingOptions(
        turn_detection=turn_detection,
        endpointing={
            "mode": "dynamic",
            "min_delay": _env_float("PHONE_ENDPOINTING_MIN", 0.3),
            "max_delay": _env_float("PHONE_ENDPOINTING_MAX", 2.5),
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


def _web_turn_handling() -> TurnHandlingOptions:
    return TurnHandlingOptions(
        turn_detection=inference.TurnDetector(),
        endpointing={
            "mode": "dynamic",
            "min_delay": 0.25,
            "max_delay": 2.0,
        },
        interruption={
            "mode": "adaptive",
            "enabled": True,
            "min_duration": 0.35,
            "min_words": 0,
            "resume_false_interruption": True,
        },
        preemptive_generation={
            "enabled": True,
            "preemptive_tts": True,
            "max_speech_duration": 10.0,
            "max_retries": 2,
        },
    )


def build_agent_session(*, is_phone: bool) -> AgentSession:
    """Create AgentSession with channel-appropriate latency tuning."""
    turn_handling = _phone_turn_handling() if is_phone else _web_turn_handling()
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
