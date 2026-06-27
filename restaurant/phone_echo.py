"""Detect phone-line echo: STT transcribing the agent's own TTS as user speech."""

from __future__ import annotations

import re
from typing import Sequence

# Fragments commonly transcribed from the opening greeting on mobile/outbound echo.
_GREETING_TAIL_PHRASES: tuple[str, ...] = (
    "help you today",
    "how can i help you",
    "how can i help",
    "i m sierra",
    "im sierra",
    "i am sierra",
    "welcome to bizbull",
    "bizbull restaurant",
    "sat sri akal",
)


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().strip())


def _tokens(text: str) -> list[str]:
    cleaned = re.sub(r"[^\w\s]", " ", _normalize(text))
    return [t for t in cleaned.split() if len(t) > 1]


def is_greeting_tail_echo(user_text: str) -> bool:
    """Known echo fragments from Sierra's opening greeting."""
    u = _normalize(user_text)
    if not u:
        return True
    return any(phrase in u for phrase in _GREETING_TAIL_PHRASES)


def is_likely_phone_echo(user_text: str, recent_agent_lines: Sequence[str]) -> bool:
    """Return True if user_text is probably acoustic echo of recent agent speech."""
    user = user_text.strip()
    if not user:
        return True

    if is_greeting_tail_echo(user):
        return True

    u_norm = _normalize(user)
    u_tokens = _tokens(user)

    for agent in recent_agent_lines:
        if not agent:
            continue
        a_norm = _normalize(agent)
        if len(u_norm) >= 10 and (u_norm in a_norm or a_norm in u_norm):
            return True

        a_tokens = _tokens(agent)
        if not u_tokens or not a_tokens:
            continue

        overlap = sum(1 for t in u_tokens if t in a_tokens)
        if len(u_tokens) >= 4 and overlap >= max(3, int(0.6 * len(u_tokens))):
            return True
        if len(u_tokens) == 3 and overlap == 3:
            return True
        if len(u_tokens) == 2 and overlap == 2 and u_tokens == a_tokens[:2]:
            return True

    return False
