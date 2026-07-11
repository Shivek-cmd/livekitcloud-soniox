"""Customer language detection + opening greeting (salvaged from conversation.py)."""

from __future__ import annotations

import re
from enum import Enum

OPENING_GREETING = (
    "Hi! I'm Sierra, your virtual assistant. "
    "I speak English, Hindi, and Punjabi. How can I help you?"
)


class CustomerLanguage(str, Enum):
    ENGLISH = "en"
    HINDI = "hi"
    PUNJABI = "pa"
    MIXED = "mixed"


_GURMUKHI_CHARS = re.compile(r"[\u0A00-\u0A7F]")
_DEVANAGARI_CHARS = re.compile(r"[\u0900-\u097F]")
_LATIN_CHARS = re.compile(r"[A-Za-z]")


def detect_customer_language(text: str) -> CustomerLanguage | None:
    """Infer language from script in the user's utterance."""
    t = (text or "").strip()
    if len(t) < 2:
        return None

    g = len(_GURMUKHI_CHARS.findall(t))
    d = len(_DEVANAGARI_CHARS.findall(t))
    latin = len(_LATIN_CHARS.findall(t))

    if g >= 2 and g >= d:
        return CustomerLanguage.PUNJABI
    if d >= 2 and d > g:
        return CustomerLanguage.HINDI
    if g >= 1 and d >= 1:
        return CustomerLanguage.MIXED
    if g == 1 and d == 0:
        return CustomerLanguage.PUNJABI
    if d == 1 and g == 0:
        return CustomerLanguage.HINDI
    if latin >= 2:
        return CustomerLanguage.ENGLISH
    return None


def update_preferred_language(
    current: CustomerLanguage | None,
    user_text: str,
) -> CustomerLanguage:
    """Sticky session language — updates when caller clearly uses another script."""
    detected = detect_customer_language(user_text)
    if detected is None:
        return current or CustomerLanguage.ENGLISH
    if current is None:
        return detected
    if detected == CustomerLanguage.MIXED:
        return current
    return detected
