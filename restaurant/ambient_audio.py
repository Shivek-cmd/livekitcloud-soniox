"""Background ambient audio for web and phone via LiveKit BackgroundAudioPlayer."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from livekit.agents import AudioConfig, BackgroundAudioPlayer, BuiltinAudioClip

logger = logging.getLogger("ambient-audio")

_DEFAULT_WEB_VOLUME = 0.5
_DEFAULT_PHONE_VOLUME = 0.35
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


def _ambient_audio_path() -> Path:
    for key in ("AMBIENT_AUDIO_PATH", "WEB_AMBIENT_AUDIO_PATH"):
        custom = os.getenv(key, "").strip()
        if custom:
            return Path(custom)
    return _DEFAULT_CUSTOM_PATH


def web_ambient_enabled() -> bool:
    """True when web sessions should publish a background ambient track."""
    return _env_bool("WEB_AMBIENT_ENABLED", True)


def phone_ambient_enabled() -> bool:
    """True when phone sessions should publish a background ambient track."""
    return _env_bool("PHONE_AMBIENT_ENABLED", True)


def ambient_enabled(*, is_phone: bool) -> bool:
    return phone_ambient_enabled() if is_phone else web_ambient_enabled()


def build_ambient_player(*, is_phone: bool) -> BackgroundAudioPlayer | None:
    """Build ambient player for web or phone, or None when disabled for that channel."""
    channel = "phone" if is_phone else "web"
    if not ambient_enabled(is_phone=is_phone):
        env_key = "PHONE_AMBIENT_ENABLED" if is_phone else "WEB_AMBIENT_ENABLED"
        logger.info("%s ambient disabled (%s=0)", channel.capitalize(), env_key)
        return None

    default_volume = _DEFAULT_PHONE_VOLUME if is_phone else _DEFAULT_WEB_VOLUME
    volume_key = "PHONE_AMBIENT_VOLUME" if is_phone else "WEB_AMBIENT_VOLUME"
    fade_key = "PHONE_AMBIENT_FADE_IN" if is_phone else "WEB_AMBIENT_FADE_IN"

    volume = _env_float(volume_key, default_volume)
    fade_in = _env_float(fade_key, _DEFAULT_FADE_IN)
    path = _ambient_audio_path()

    if path.is_file():
        source: str | BuiltinAudioClip = str(path.resolve())
        label = path.name
    else:
        source = BuiltinAudioClip.OFFICE_AMBIENCE
        label = "OFFICE_AMBIENCE (builtin fallback)"
        logger.info(
            "No custom ambient at %s — using builtin OFFICE_AMBIENCE; "
            "drop restaurant_ambience.mp3 there or set AMBIENT_AUDIO_PATH",
            path,
        )

    thinking = None
    if not is_phone and _env_bool("WEB_AMBIENT_THINKING", False):
        thinking = AudioConfig(BuiltinAudioClip.KEYBOARD_TYPING, volume=volume * 0.6)

    logger.info(
        "%s ambient ready: source=%s volume=%.2f fade_in=%.1fs",
        channel.capitalize(),
        label,
        volume,
        fade_in,
    )
    return BackgroundAudioPlayer(
        ambient_sound=AudioConfig(source, volume=volume, fade_in=fade_in),
        thinking_sound=thinking,
    )


def build_web_ambient_player() -> BackgroundAudioPlayer | None:
    """Build a player for web, or None when disabled."""
    return build_ambient_player(is_phone=False)


async def start_ambient(
    player: BackgroundAudioPlayer | None,
    *,
    is_phone: bool,
    room,
    agent_session,
) -> None:
    if player is None:
        return
    await player.start(room=room, agent_session=agent_session)
    channel = "Phone" if is_phone else "Web"
    logger.info("%s ambient started", channel)


async def stop_ambient(player: BackgroundAudioPlayer | None, *, is_phone: bool) -> None:
    if player is None:
        return
    await player.aclose()
    channel = "Phone" if is_phone else "Web"
    logger.info("%s ambient stopped", channel)


async def start_web_ambient(
    player: BackgroundAudioPlayer | None,
    *,
    room,
    agent_session,
) -> None:
    await start_ambient(player, is_phone=False, room=room, agent_session=agent_session)


async def stop_web_ambient(player: BackgroundAudioPlayer | None) -> None:
    await stop_ambient(player, is_phone=False)
