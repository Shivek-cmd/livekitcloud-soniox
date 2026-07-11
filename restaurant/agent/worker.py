"""Worker entrypoint for the hybrid agent — plumbing carried 1:1 from the old
root agent.py (connect, channel detection, recorder, latency, warmup, ambient
audio, web sync, greeting settle). At cutover (PR 062) root agent.py becomes a
thin shim over run() so systemd (`python agent.py start`) and
scripts/setup_sip.py (agent_name="restaurant-agent") stay unchanged.
"""

from __future__ import annotations

import asyncio
import logging
import os

from dotenv import load_dotenv
from livekit.agents import JobContext, WorkerOptions, cli

from restaurant.agent.core import RestaurantAgent
from restaurant.agent.language import OPENING_GREETING
from restaurant.agent.replies import sanitize_assistant_speech
from restaurant.channels.ambient_audio import build_ambient_player, start_ambient, stop_ambient
from restaurant.analytics.analytics_store import persist_session
from restaurant.llm_warmup import schedule_llm_warmup
from restaurant.session_config import (
    build_agent_session,
    build_room_options,
    phone_greeting_settle_seconds,
)
from restaurant.analytics.session_recorder import SessionRecorder
from restaurant.analytics.turn_latency import TurnLatencyTracker
from restaurant.channels.web_sync import WebSync

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger("restaurant-agent")


def _sip_caller_phone(attrs: dict) -> str | None:
    for key in ("sip.phoneNumber", "sip.callerNumber", "sip.from"):
        value = attrs.get(key)
        if value:
            return str(value)
    return None


async def entrypoint(ctx: JobContext):
    await ctx.connect()

    participant = await ctx.wait_for_participant()
    sip_attrs = dict(participant.attributes or {})

    is_phone = (
        participant.identity.startswith("sip_")
        or sip_attrs.get("sip.callStatus") is not None
    )
    channel = "phone" if is_phone else "web"

    logger.info(
        f"Session started | room={ctx.room.name} | "
        f"channel={channel} | "
        f"participant={participant.identity}"
    )

    recorder = SessionRecorder(
        metadata={"git_sha": os.getenv("DEPLOY_GIT_SHA", "")},
    )
    recorder.start(
        room_name=ctx.room.name,
        channel=channel,
        participant_identity=participant.identity,
        caller_phone=_sip_caller_phone(sip_attrs),
    )

    session = build_agent_session(is_phone=is_phone)

    def _on_turn_latency(latency: dict) -> None:
        recorder.attach_latency(latency)

    TurnLatencyTracker(channel=channel, on_turn_latency=_on_turn_latency).attach(session)

    agent = RestaurantAgent(is_phone=is_phone)
    agent.bind_session(session)
    agent.bind_recorder(recorder)
    agent.bind_job_context(ctx)

    # Race the fixed greeting: prime the LLM's prompt cache with the real tool
    # schema so the caller's first real turn doesn't pay the cold-prefix cost.
    schedule_llm_warmup(is_phone=is_phone, tools=agent.tools)

    _analytics_flushed = False

    async def _flush_analytics(*, reason: str = "shutdown") -> None:
        nonlocal _analytics_flushed
        if _analytics_flushed:
            return
        _analytics_flushed = True
        logger.info(
            "Flushing session analytics (%s) room=%s session=%s",
            reason,
            recorder.room_name,
            recorder.session_id,
        )
        try:
            payload = recorder.finalize(
                agent.cart,
                preferred_language=agent.state.preferred_language.value,
            )
            await persist_session(payload)
        except Exception:
            logger.exception("Session analytics flush failed (%s)", reason)

    @session.on("close")
    def _on_session_close(_ev) -> None:
        asyncio.create_task(_flush_analytics(reason="session_close"))

    async def _shutdown_flush() -> None:
        await _flush_analytics(reason="shutdown")

    ctx.add_shutdown_callback(_shutdown_flush)

    await session.start(
        room=ctx.room,
        agent=agent,
        room_options=build_room_options(is_phone=is_phone),
    )

    background_audio = build_ambient_player(is_phone=is_phone)
    if background_audio is not None:
        await start_ambient(
            background_audio,
            is_phone=is_phone,
            room=ctx.room,
            agent_session=session,
        )

        async def _stop_ambient() -> None:
            await stop_ambient(background_audio, is_phone=is_phone)

        ctx.add_shutdown_callback(_stop_ambient)

    # Web channel: register cart RPCs + push live order state to the browser.
    if not is_phone:
        web_sync = WebSync(ctx.room, agent)
        web_sync.register()
        agent.bind_web_sync(web_sync)
        await web_sync.publish_order_state()

    @session.on("user_input_transcribed")
    def _on_user_transcript(ev) -> None:
        if ev.is_final:
            logger.info(f"USER: {ev.transcript}")
            lang = getattr(ev, "language", None)
            recorder.begin_user_turn(ev.transcript or "", stt_language=lang)

    @session.on("conversation_item_added")
    def _on_conv_item(ev) -> None:
        role = getattr(ev.item, "role", None)
        if role == "assistant":
            text = getattr(ev.item, "text_content", None) or ""
            if text:
                cleaned = sanitize_assistant_speech(
                    text,
                    allow_greeting=agent.state.real_user_turns == 0,
                    is_phone=agent.is_phone,
                    customer_phone=agent.cart.customer_phone or None,
                )
                if cleaned != text:
                    logger.warning("Mid-call re-greeting blocked in log: %s", text[:80])
                agent.note_agent_speech(text)
                recorder.append_sierra(text)
                logger.info(f"SIERRA: {text}")

    await session.say(
        OPENING_GREETING,
        allow_interruptions=False,
    )

    # Let greeting echo fade on mobile/outbound before listening for the caller.
    if is_phone:
        await asyncio.sleep(phone_greeting_settle_seconds())
        if agent._greeting_echo_pending_reprompt and agent.state.real_user_turns == 0:
            agent._echo_reprompt_done = True
            await session.say(
                "ਹਾਂ ਜੀ — go ahead, I'm listening.",
                allow_interruptions=True,
            )


def run() -> None:
    """CLI runner — root agent.py delegates here at cutover (PR 062)."""
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            agent_name=os.getenv("AGENT_NAME", "restaurant-agent"),
            port=int(os.getenv("AGENT_HTTP_PORT", "8081")),
        )
    )


if __name__ == "__main__":
    run()
