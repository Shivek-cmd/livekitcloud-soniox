"""Detect phone-line echo: STT transcribing the agent's own TTS as user speech."""

from __future__ import annotations

import re
from typing import Sequence

from restaurant.text_match import indic_word_re, word_bounded

# Echo of Sierra reprompt / recovery lines — drop silently, never reprompt again.
_RECOVERY_ECHO_PHRASES: tuple[str, ...] = (
    "go ahead",
    "i m listening",
    "im listening",
    "listening",
    "sun rahi",
    "what would you like to know",
    "from the menu",
    "sorry ji",
    "ਮੈਂ ਸੁਣ ਰਹੀ",
    "ਸੁਣ ਰਹੀ",
    # PR 077 reprompt-pool fragment. Deliberately NOT listing caller-plausible
    # fragments from the pools ("one more time", "ਇੱਕ ਵਾਰ ਫਿਰ", "a little
    # noisy") — a caller asking us to repeat must never be dropped (PR 073);
    # exact/truncated echoes of the full reprompt lines are already caught via
    # _recent_agent_lines.
    "take your time",
)

# Fragments commonly transcribed from the opening greeting on mobile/outbound echo.
_GREETING_TAIL_PHRASES: tuple[str, ...] = (
    "how may i help you",
    "how may i help you today",
    "english hindi or punjabi",
    "i can help you in english",
    "sierra from bizbull",
    "your virtual assistant",
    "virtual assistant",
    "i speak english hindi and punjabi",
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

# Intents that must never be dropped — caller is answering or ordering, not echoing.
_BYPASS_INTENTS: frozenset[str] = frozenset(
    {
        "pickup",
        "delivery",
        "add_item",
        "order_done",
        "ask_price",
        "ask_availability",
        "confirm_no",
        "confirm_yes",
        "human",
    }
)

_PRICE_SIGNAL_RE = indic_word_re(
    r"price|prices|cost|how much|kitna|kina|rate|ਕੀਮਤ|ਕਿਨਾ|ਦਾਮ"
)

_ORDER_SIGNAL_RE = re.compile(
    word_bounded(
        r"pickup|pick up|delivery|order|add|want|need|"
        r"one|two|three|four|five|"
        r"yeah|yep|yes|haan|han|"
        r"paneer|chicken|mango|shake|tikka|curry|naan|lassi|kulfi|"
        r"ਚਾਹੀ|ਆਰਡਰ|ਪਿਕਅੱਪ|ਡਿਲਿਵਰੀ|ਕਰ ਦ|ਕਿਹਾ|ਇੱਕ|ਦੋ|ਤੇ"
    )
    + r"|\d",
    re.I,
)

# PR 073 — function words excluded from echo content-overlap comparison. An
# answer to an option-list question inherently reuses the question's function
# words ("would", "it"); only leftover content words indicate real echo.
# Deliberately EXCLUDES order-signal words ("want") and meaningful particles
# ("ji", "haan") — those carry answer content, not filler.
_STOPWORDS: frozenset[str] = frozenset(
    {
        "i",
        "we",
        "you",
        "it",
        "the",
        "a",
        "an",
        "is",
        "are",
        "do",
        "did",
        "does",
        "would",
        "could",
        "can",
        "will",
        "like",
        "to",
        "of",
        "and",
        "or",
        "for",
        "in",
        "on",
        "that",
        "this",
        "my",
        "me",
        "so",
        # Common Punjabi/Hindi function-word equivalents.
        "hai",
        "hain",
        "ka",
        "ki",
        "ke",
        "ko",
        "kya",
        "aur",
        "hi",
        "ਹੈ",
        "ਹਨ",
        "ਦਾ",
        "ਦੀ",
        "ਦੇ",
        "ਨੂੰ",
        "ਅਤੇ",
    }
)


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().strip())


def _tokens(text: str) -> list[str]:
    cleaned = re.sub(r"[^\w\s]", " ", _normalize(text))
    return [t for t in cleaned.split() if len(t) > 1]


def is_recovery_phrase_echo(user_text: str) -> bool:
    """Echo of Sierra's go-ahead / listening reprompts."""
    u = _normalize(user_text)
    if not u:
        return False
    return any(phrase in u for phrase in _RECOVERY_ECHO_PHRASES)


def is_greeting_tail_echo(user_text: str) -> bool:
    """Known echo fragments from Sierra's opening greeting."""
    u = _normalize(user_text)
    if not u:
        return True
    return any(phrase in u for phrase in _GREETING_TAIL_PHRASES)


def should_bypass_phone_echo_filter(user_text: str, intent: str | None) -> bool:
    """True when user speech must be processed even if it overlaps recent agent lines.

    `intent` is the plain intent value ("pickup", "add_item", …) or None.
    """
    if not user_text.strip():
        return False
    if intent is not None and intent in _BYPASS_INTENTS:
        return True
    if _PRICE_SIGNAL_RE.search(user_text):
        return True
    if _ORDER_SIGNAL_RE.search(user_text):
        return True
    return False


def is_likely_phone_echo(
    user_text: str,
    recent_agent_lines: Sequence[str],
    *,
    intent: str | None = None,
) -> bool:
    """Return True if user_text is probably acoustic echo of recent agent speech."""
    user = user_text.strip()
    if not user:
        return True

    if is_greeting_tail_echo(user):
        return True

    if is_recovery_phrase_echo(user):
        return True

    u_norm = _normalize(user)
    for agent in recent_agent_lines:
        if not agent:
            continue
        a_norm = _normalize(agent)
        # Truncated STT echo of Sierra's last line (e.g. ends with "—").
        if len(u_norm) >= 8 and a_norm.startswith(u_norm.rstrip("-— ")):
            return True
        if agent and u_norm == a_norm:
            return True

    if should_bypass_phone_echo_filter(user_text, intent):
        return False

    u_tokens = _tokens(user)

    for agent in recent_agent_lines:
        if not agent:
            continue
        a_norm = _normalize(agent)

        a_tokens = _tokens(agent)
        if not u_tokens or not a_tokens:
            continue

        a_set = set(a_tokens)

        # Content-word gate: an answer that reuses the question's function
        # words but adds/changes a content word is a real reply, not echo.
        u_content = [t for t in u_tokens if t not in _STOPWORDS]
        if u_content and any(t not in a_set for t in u_content):
            continue

        unique_user = [t for t in u_tokens if t not in a_set]
        overlap = sum(1 for t in u_tokens if t in a_set)

        # Caller added their own words (yeah, numbers, dish names) — not echo.
        if len(u_tokens) >= 4 and len(unique_user) >= 2:
            continue

        if len(u_tokens) >= 6:
            needed = max(4, int(0.85 * len(u_tokens)))
            if overlap < needed:
                continue
        elif len(u_tokens) >= 4:
            needed = max(3, int(0.75 * len(u_tokens)))
            if overlap < needed:
                continue
        elif len(u_tokens) == 3:
            if overlap < 3:
                continue
        elif len(u_tokens) == 2:
            if not (overlap == 2 and u_tokens == a_tokens[:2]):
                continue
        else:
            continue

        return True

    return False
