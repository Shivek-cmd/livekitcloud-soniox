"""Drop phone turns that look like background chatter, not the caller ordering."""

from __future__ import annotations

import re

from restaurant.conversation import UserIntent
from restaurant.phone_echo import _ORDER_SIGNAL_RE, should_bypass_phone_echo_filter

# Short replies that are valid even when intent stays GENERAL.
_SHORT_MEANINGFUL: frozenset[str] = frozenset(
    {
        "yes",
        "yeah",
        "yep",
        "no",
        "nope",
        "ok",
        "okay",
        "pickup",
        "delivery",
        "haan",
        "han",
        "ji",
        "na",
        "hello",
        "hi",
        "hey",
        "stop",
        "wait",
        "human",
        "person",
        "operator",
        "menu",
    }
)

# Common background / side-conversation fragments (not order-related).
_BACKGROUND_FRAGMENT_RE = re.compile(
    r"\b("
    r"thank you|thanks|welcome|please subscribe|breaking news|"
    r"la la|na na|oh oh|mm hmm|uh huh|"
    r"shh|quiet|listen"
    r")\b",
    re.I,
)


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().strip())


def _tokens(text: str) -> list[str]:
    cleaned = re.sub(r"[^\w\s]", " ", _normalize(text))
    return [t for t in cleaned.split() if t]


def is_likely_background_speech(
    user_text: str,
    intent: UserIntent,
    *,
    enabled: bool = True,
) -> bool:
    """True when STT text is probably background TV / nearby speaker, not the customer."""
    if not enabled:
        return False

    text = user_text.strip()
    if not text:
        return True

    if should_bypass_phone_echo_filter(text, intent):
        return False

    if intent not in (UserIntent.GENERAL, UserIntent.UNCLEAR):
        return False

    if _ORDER_SIGNAL_RE.search(text):
        return False

    if _BACKGROUND_FRAGMENT_RE.search(text):
        return True

    tokens = _tokens(text)
    if not tokens:
        return True

    if len(tokens) == 1:
        return tokens[0] not in _SHORT_MEANINGFUL

    if len(tokens) == 2 and all(t in _SHORT_MEANINGFUL for t in tokens):
        return False

    # Very short side speech with no order/menu signal.
    if len(tokens) <= 2:
        return True

    return False
