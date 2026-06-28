"""Web-only background ambient audio via LiveKit BackgroundAudioPlayer."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from livekit.agents import AudioConfig, BackgroundAudioPlayer, BuiltinAudioClip

logger = logging.getLogger("ambient-audio")

_DEFAULT_VOLUME = 0.25
_DEFAULT_FADE_IN = 1.0
_REPO_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_CUSTOM_PATH = _REPO_ROOT / "data" / "audio" / "restaurant_ambience.mp3"


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name, "").strip().lower()
    if not raw:
        return default
    return raw in ("1", "true", "yes", "on")


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        logger.warning("Invalid %s=%r — using default %s", name, raw, default)
        return default


def web_ambient_enabled() -> bool:
    """True when web sessions should publish a background ambient track."""
    return _env_bool("WEB_AMBIENT_ENABLED", True)


def build_web_ambient_player() -> BackgroundAudioPlayer | None:
    """Build a player for web, or None when disabled."""
    if not web_ambient_enabled():
        logger.info("Web ambient disabled (WEB_AMBIENT_ENABLED=0)")
        return None

    volume = _env_float("WEB_AMBIENT_VOLUME", _DEFAULT_VOLUME)
    fade_in = _env_float("WEB_AMBIENT_FADE_IN", _DEFAULT_FADE_IN)

    custom = os.getenv("WEB_AMBIENT_AUDIO_PATH", "").strip()
    path = Path(custom) if custom else _DEFAULT_CUSTOM_PATH

    if path.is_file():
        source: str | BuiltinAudioClip = str(path.resolve())
        label = path.name
    else:
        source = BuiltinAudioClip.OFFICE_AMBIENCE
        label = "OFFICE_AMBIENCE (builtin fallback)"
        if custom:
            logger.warning("WEB_AMBIENT_AUDIO_PATH not found: %s — using builtin", path)
        else:
            logger.info(
                "No custom ambient at %s — using builtin OFFICE_AMBIENCE; "
                "drop restaurant_ambience.mp3 there or set WEB_AMBIENT_AUDIO_PATH",
                path,
            )

    thinking = None
    if _env_bool("WEB_AMBIENT_THINKING", False):
        thinking = AudioConfig(BuiltinAudioClip.KEYBOARD_TYPING, volume=volume * 0.6)

    logger.info("Web ambient ready: source=%s volume=%.2f fade_in=%.1fs", label, volume, fade_in)
    return BackgroundAudioPlayer(
        ambient_sound=AudioConfig(source, volume=volume, fade_in=fade_in),
        thinking_sound=thinking,
    )


async def start_web_ambient(
    player: BackgroundAudioPlayer | None,
    *,
    room,
    agent_session,
) -> None:
    if player is None:
        return
    await player.start(room=room, agent_session=agent_session)
    logger.info("Web ambient started")


async def stop_web_ambient(player: BackgroundAudioPlayer | None) -> None:
    if player is None:
        return
    await player.aclose()
    logger.info("Web ambient stopped")
