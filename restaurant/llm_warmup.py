"""LLM prompt-cache warmup — prime OpenAI's cache before the caller's first real turn.

OpenAI caches the longest common request prefix — our ~1400-token system prompt
PLUS the full tool/function-calling schema every real turn sends — but that cache
expires after a few minutes idle or a service restart. Without warmup, the caller's
first utterance always lands on a cold prefix: ~3.5s llm_ttft instead of the normal
~0.6-1.6s once the cache is warm.

v1 (PR 046) fired a raw completion with only the system prompt and no tools, which
only got a partial cache hit (~2.0s) because the real request's tools changed the
serialized prefix. This version drives the warmup through the actual openai.LLM
plugin, a real ChatContext, and the agent's real registered tools, so the request
is byte-identical in shape to a real turn. Fire-and-forget: it never touches the
real AgentSession / ChatContext, so it cannot affect conversation state or tool
calls — the response is discarded.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import TYPE_CHECKING

from livekit.agents.llm import ChatContext

from restaurant.prompts import build_system_prompt
from restaurant.voice_stack import build_llm

if TYPE_CHECKING:
    from livekit.agents import llm as lk_llm

logger = logging.getLogger("llm-warmup")


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name, "").strip().lower()
    if not raw:
        return default
    return raw in ("1", "true", "yes", "on")


def warmup_enabled() -> bool:
    return _env_bool("LLM_WARMUP_ENABLED", True)


async def warm_llm_cache(*, is_phone: bool, tools: list[lk_llm.Tool]) -> None:
    """Fire-and-forget: prime OpenAI's prompt cache with the same system prompt
    and tool schema a real turn on this channel would send."""
    if not warmup_enabled():
        return

    channel = "phone" if is_phone else "web"
    chat_ctx = ChatContext.empty()
    chat_ctx.add_message(role="system", content=build_system_prompt(is_phone=is_phone))
    chat_ctx.add_message(role="user", content="Hi")

    started = time.monotonic()
    try:
        llm = build_llm()
        await llm.chat(
            chat_ctx=chat_ctx,
            tools=tools,
            extra_kwargs={"max_completion_tokens": 1},
        ).collect()
        logger.info(
            "LLM_WARMUP ok channel=%s elapsed=%.2fs",
            channel,
            time.monotonic() - started,
        )
    except Exception:
        logger.warning(
            "LLM_WARMUP failed channel=%s elapsed=%.2fs",
            channel,
            time.monotonic() - started,
            exc_info=True,
        )


def schedule_llm_warmup(*, is_phone: bool, tools: list[lk_llm.Tool]) -> asyncio.Task | None:
    """Fire-and-forget scheduling — safe to call unconditionally."""
    if not warmup_enabled():
        return None
    return asyncio.create_task(
        warm_llm_cache(is_phone=is_phone, tools=tools),
        name="llm_cache_warmup",
    )
