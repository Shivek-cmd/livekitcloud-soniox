"""Intent detection, spoken templates, and assistant speech guards (Tier B-5/B-6/B-7)."""

from __future__ import annotations

import re
from enum import Enum

# ── Intent ────────────────────────────────────────────────────────────────────


class UserIntent(str, Enum):
    GENERAL = "general"
    ASK_PRICE = "ask_price"
    ASK_AVAILABILITY = "ask_availability"
    ADD_ITEM = "add_item"
    ORDER_DONE = "order_done"
    CONFIRM_YES = "confirm_yes"
    CONFIRM_NO = "confirm_no"
    HUMAN = "human"
    UNCLEAR = "unclear"


_PRICE_RE = re.compile(
    r"\b("
    r"price|prices|cost|how much|kithe da|kitna|kina|kine da|"
    r"ਕੀਮਤ|ਕਿਨਾ|ਕਿੰਨੇ|ਦਾਮ|rate|"
    r"how many dollars|what.?s the price"
    r")\b",
    re.I,
)

_AVAIL_RE = re.compile(
    r"("
    r"\b(do you have|have you got|is there|available|hai\??|hain\??|"
    r"mil.?ega|mil.?egi|kya hai|kya hain)\b|"
    r"ਕੀ\s*ਹੈ|ਕੀ\s*ਹਨ|ਮਿਲੇਗ|ਚ\s*ਕੀ\s*ਹੈ"
    r")",
    re.I,
)

_ADD_RE = re.compile(
    r"\b("
    r"add|order|want|need|get me|give me|i.?ll take|i want|"
    r"i'd like|chahiye|chahida|chahidi|dedo|de do|lao|"
    r"order karo|order kar|add karo|add kar|"
    r"ਚਾਹੀਦ|ਚਾਹੀਦਾ|ਚਾਹੀਦੀ|ਆਰਡਰ|ਪਾ ਦ|ਜੋੜ|ਲੈ"
    r")\b",
    re.I,
)

_DONE_RE = re.compile(
    r"\b("
    r"that.?s it|that.?s all|nothing else|no more|bas|bus|"
    r"done ordering|i.?m done|finish|"
    r"ਬਸ|ਹੋ ਗਿਆ|ਔਰ ਨਹੀ|ਕੁਝ ਨਹੀ"
    r")\b",
    re.I,
)

_YES_RE = re.compile(r"^(yes|yeah|yep|yup|haan|han|ha ji|ji|correct|right|ok|okay|ਠੀਕ|ਹਾਂ)\.?$", re.I)

_HUMAN_RE = re.compile(
    r"\b("
    r"human|person|staff|manager|someone else|real person|"
    r"operator|agent|connect me|talk to someone|"
    r"ਬੰਦਾ|ਆਦਮੀ|manager|staff"
    r")\b",
    re.I,
)

_GREETING_RE = re.compile(
    r"(sat\s*sri\s*akal|ਸਤ\s*ਸ੍ਰੀ\s*ਅਕਾਲ|welcome to bizbull|how can i help you today)",
    re.I,
)


def detect_intent(text: str) -> UserIntent:
    t = (text or "").strip()
    if not t:
        return UserIntent.UNCLEAR
    if _HUMAN_RE.search(t):
        return UserIntent.HUMAN
    if _PRICE_RE.search(t):
        return UserIntent.ASK_PRICE
    if _DONE_RE.search(t):
        return UserIntent.ORDER_DONE
    if _YES_RE.match(t):
        return UserIntent.CONFIRM_YES
    if _ADD_RE.search(t):
        return UserIntent.ADD_ITEM
    if _AVAIL_RE.search(t):
        return UserIntent.ASK_AVAILABILITY
    return UserIntent.GENERAL


def is_add_intent(text: str) -> bool:
    return detect_intent(text) == UserIntent.ADD_ITEM


# ── Templates (B-7, B-5) ────────────────────────────────────────────────────


def format_price_reply(price_dollars: float) -> str:
    """Single-line English price — no fluff."""
    amount = int(round(price_dollars)) if abs(price_dollars - round(price_dollars)) < 0.05 else round(price_dollars, 2)
    if isinstance(amount, float):
        return f"That's about {amount:.2f} dollars ji."
    return f"That's about {amount} dollars ji."


def spice_question_allowed(*, has_spice_modifier: bool) -> bool:
    return has_spice_modifier


def recovery_phrase(*, is_phone: bool) -> str:
    """After missed turn or echo — never re-greet."""
    if is_phone:
        return "Sorry ji — go ahead, I'm listening."
    return "Sorry ji — go ahead whenever you're ready."


def echo_recovery_phrase() -> str:
    """Short reprompt after phone echo drop — avoid echoing Sierra's own prior line."""
    return "ਮੈਂ ਸੁਣ ਰਹੀ ਹਾਂ — go ahead ji."


# ── Assistant output guard (B-6) ──────────────────────────────────────────────


def sanitize_assistant_speech(text: str, *, allow_greeting: bool) -> str:
    """Strip mid-call re-greetings; normalize common script slips."""
    if not text or allow_greeting:
        return text

    out = text
    if _GREETING_RE.search(out):
        # Replace greeting openers with recovery phrase
        out = _GREETING_RE.sub("", out).strip()
        if not out or len(out) < 8:
            out = recovery_phrase(is_phone=True)

    # Common slips from logs
    replacements = {
        "ਸوری": "ਮਾਫ ਕਰਨਾ",
        "سوری": "ਮਾਫ ਕਰਨਾ",
    }
    for bad, good in replacements.items():
        out = out.replace(bad, good)

    return out.strip()
