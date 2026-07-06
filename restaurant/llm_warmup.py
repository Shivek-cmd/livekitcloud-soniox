"""LLM prompt-cache warmup — prime OpenAI's cache before the caller's first real turn.

OpenAI caches the longest common request prefix (our ~1400-token system prompt), but
that cache expires after a few minutes idle or a service restart. Without warmup, the
caller's first utterance always lands on a cold prefix: ~3.5s llm_ttft instead of the
normal ~0.6-1.6s once the cache is warm. Firing a throwaway completion with the same
system prompt while the fixed greeting is still playing warms the cache in time.

This never touches the real AgentSession / ChatContext — it's a side call whose
response is discarded, so it cannot affect conversation state or tool calls.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time

from openai import AsyncOpenAI

from restaurant.prompts import build_system_prompt

logger = logging.getLogger("llm-warmup")

_MODEL = "gpt-4o-mini"


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name, "").strip().lower()
    if not raw:
        return default
    return raw in ("1", "true", "yes", "on")


def warmup_enabled() -> bool:
    return _env_bool("LLM_WARMUP_ENABLED", True)


async def warm_llm_cache(*, is_phone: bool) -> None:
    """Fire-and-forget: prime OpenAI's prompt cache for this channel's system prompt."""
    if not warmup_enabled():
        return

    channel = "phone" if is_phone else "web"
    system_prompt = build_system_prompt(is_phone=is_phone)
    started = time.monotonic()
    try:
        client = AsyncOpenAI()
        await client.chat.completions.create(
            model=_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": "Hi"},
            ],
            max_tokens=1,
        )
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


def schedule_llm_warmup(*, is_phone: bool) -> asyncio.Task | None:
    """Fire-and-forget scheduling — safe to call unconditionally."""
    if not warmup_enabled():
        return None
    return asyncio.create_task(
        warm_llm_cache(is_phone=is_phone),
        name="llm_cache_warmup",
    )
