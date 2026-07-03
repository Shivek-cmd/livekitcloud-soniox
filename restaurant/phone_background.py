"""Drop phone turns that look like background chatter, not the caller ordering."""

from __future__ import annotations

import re

from restaurant.clover.match import phonetic_key
from restaurant.conversation import UserIntent
from restaurant.phone_echo import _ORDER_SIGNAL_RE, should_bypass_phone_echo_filter
from restaurant.stt_noise import is_likely_stt_noise, parse_standalone_quantity

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
        "one",
        "two",
        "three",
        "four",
        "five",
        "van",
        "wan",
    }
)

# Phonetic keys for the Latin allowlist — matches Gurmukhi/Devanagari equivalents.
_SHORT_MEANINGFUL_KEYS: frozenset[str] = frozenset(
    phonetic_key(w) for w in _SHORT_MEANINGFUL if phonetic_key(w)
)


def _token_is_meaningful(token: str) -> bool:
    if token in _SHORT_MEANINGFUL:
        return True
    key = phonetic_key(token)
    return bool(key) and key in _SHORT_MEANINGFUL_KEYS


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
    # Do not use [^\w\s] — Gurmukhi/Devanagari matras are not \w and would
    # split words like ਹੈਲੋ into meaningless single-letter tokens.
    cleaned = re.sub(r"[.,!?;:\"]+", " ", _normalize(text))
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return [t for t in cleaned.split() if t]


def is_likely_background_speech(
    user_text: str,
    intent: UserIntent,
    *,
    enabled: bool = True,
    phase: str | None = None,
) -> bool:
    """True when STT text is probably background TV / nearby speaker, not the customer."""
    if not enabled:
        return False

    text = user_text.strip()
    if not text:
        return True

    # Never drop short replies during checkout contact capture.
    if phase in ("customer_name", "customer_phone", "readback"):
        return False

    # Quantity answers while collecting (one, van, ਇੱਕ).
    if phase in ("awaiting_more", "collecting_items", "browsing"):
        if parse_standalone_quantity(text) is not None:
            return False

    if should_bypass_phone_echo_filter(text, intent):
        return False

    if intent not in (UserIntent.GENERAL, UserIntent.UNCLEAR):
        return False

    if _ORDER_SIGNAL_RE.search(text):
        return False

    if _BACKGROUND_FRAGMENT_RE.search(text):
        return True

    if is_likely_stt_noise(text) and intent in (UserIntent.GENERAL, UserIntent.UNCLEAR):
        return True

    tokens = _tokens(text)
    if not tokens:
        return True

    if len(tokens) == 1:
        return not _token_is_meaningful(tokens[0])

    if len(tokens) == 2 and all(_token_is_meaningful(t) for t in tokens):
        return False

    # Very short side speech with no order/menu signal.
    if len(tokens) <= 2:
        return True

    return False
