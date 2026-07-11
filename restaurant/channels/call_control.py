"""Call lifecycle — auto hang-up after order placed (phone + web)."""

from __future__ import annotations

import asyncio
import logging
import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from livekit.agents import JobContext
    from livekit.agents.voice.agent_session import AgentSession
    from livekit.agents.voice.speech_handle import SpeechHandle

logger = logging.getLogger("call-control")


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
        return default


def hangup_after_order_enabled() -> bool:
    return _env_bool("AUTO_HANGUP_AFTER_ORDER", True)


def hangup_grace_seconds() -> float:
    return max(0.0, _env_float("AUTO_HANGUP_GRACE_SEC", 1.0))


async def end_call_after_goodbye(
    session: AgentSession,
    job_ctx: JobContext,
    *,
    reason: str,
    channel: str,
    speech_handle: SpeechHandle | None = None,
) -> None:
    """Wait for goodbye TTS, delete room (SIP + web), shutdown session."""
    if not hangup_after_order_enabled():
        return

    room_name = job_ctx.room.name

    try:
        if speech_handle is not None:
            await speech_handle

        grace = hangup_grace_seconds()
        if grace > 0:
            await asyncio.sleep(grace)
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception("CALL_END wait failed room=%s reason=%s", room_name, reason)
        return

    logger.info(
        "CALL_END reason=%s channel=%s room=%s",
        reason,
        channel,
        room_name,
    )

    try:
        await job_ctx.delete_room()
    except Exception:
        logger.exception("delete_room failed room=%s", room_name)

    try:
        session.shutdown(drain=False)
    except Exception:
        logger.exception("session.shutdown failed room=%s", room_name)


def schedule_call_hangup(
    session: AgentSession,
    job_ctx: JobContext,
    *,
    reason: str,
    channel: str,
    speech_handle: SpeechHandle | None = None,
) -> None:
    """Fire-and-forget hang-up task (idempotent scheduling is caller's duty)."""
    if not hangup_after_order_enabled():
        return

    asyncio.create_task(
        end_call_after_goodbye(
            session,
            job_ctx,
            reason=reason,
            channel=channel,
            speech_handle=speech_handle,
        ),
        name=f"call_hangup_{reason}",
    )
