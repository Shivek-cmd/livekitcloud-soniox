"""Intent detection, spoken templates, and assistant speech guards (Tier B-5/B-6/B-7)."""

from __future__ import annotations

import re
from enum import Enum

from restaurant.orders import OrderCart

# ── Fixed spoken lines (Canadian Punjabi restaurant code-mix) ─────────────────

ALLERGIES_QUESTION = "Any allergies or special instructions?"
PICKUP_DELIVERY_QUESTION = "Will that be pickup or delivery?"
QUANTITY_QUESTION = "How many — one or two?"
CONFIRM_CLOSE = "All good?"


# ── Intent ────────────────────────────────────────────────────────────────────


class UserIntent(str, Enum):
    GENERAL = "general"
    ASK_PRICE = "ask_price"
    ASK_AVAILABILITY = "ask_availability"
    ADD_ITEM = "add_item"
    ORDER_DONE = "order_done"
    CONFIRM_YES = "confirm_yes"
    CONFIRM_NO = "confirm_no"
    PICKUP = "pickup"
    DELIVERY = "delivery"
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

_PICKUP_RE = re.compile(
    r"\b(pickup|pick up|pick-up|takeaway|take away|ਪਿਕਅੱਪ|ਪਿਕ ਅੱਪ)\b",
    re.I,
)

_DELIVERY_RE = re.compile(
    r"\b(delivery|deliver|home delivery|ਡਿਲਿਵਰੀ|ਘਰ.*ਡਿਲਿਵਰ)\b",
    re.I,
)

_ADD_RE = re.compile(
    r"\b("
    r"add|order|want|need|get me|give me|i.?ll take|i want|"
    r"i'd like|chahiye|dedo|de do|lao|"
    r"order karo|order kar|add karo|add kar|"
    r"ਚਾਹੀ(?:ਦਾ|ਦੀ|ਦੇ)|ਆਰਡਰ|ਪਾ ਦ|ਜੋੜ|ਲੈ"
    r")\b",
    re.I,
)

_DONE_RE = re.compile(
    r"\b("
    r"that.?s it|that.?s all|nothing else|no more|bas|bus|"
    r"done ordering|i.?m done|finish|"
    r"ਬਸ|ਹੋ ਗਿਆ|ਔਰ ਨਹੀ|ਕੁਝ ਨਹੀ|ਨਹੀਂ.*ਬਸ"
    r")\b",
    re.I,
)

_YES_RE = re.compile(
    r"^(yes|yeah|yep|yup|haan|han|ha ji|ji|correct|right|ok|okay|ਠੀਕ|ਹਾਂ)(?:\s+ji)?\.?$",
    re.I,
)

_NO_RE = re.compile(
    r"\b("
    r"^no\.?$|nope|nah|nothing|none|"
    r"nahi|nahin|na|"
    r"ਨਹੀਂ|ਨਹੀ|ਕੋਈ.*ਨਹੀਂ|ਕੁਝ ਨਹੀ"
    r")\b",
    re.I,
)

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

_QTY_WORDS = {
    1: "one",
    2: "two",
    3: "three",
    4: "four",
    5: "five",
    6: "six",
    7: "seven",
    8: "eight",
    9: "nine",
    10: "ten",
}


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
    if _PICKUP_RE.search(t) and not _DELIVERY_RE.search(t):
        return UserIntent.PICKUP
    if _DELIVERY_RE.search(t):
        return UserIntent.DELIVERY
    if re.search(r"ਚਾਹੀ(?:ਦਾ|ਦੀ|ਦੇ)", t):
        return UserIntent.ADD_ITEM
    if _NO_RE.search(t):
        return UserIntent.CONFIRM_NO
    if _ADD_RE.search(t):
        return UserIntent.ADD_ITEM
    if _AVAIL_RE.search(t):
        return UserIntent.ASK_AVAILABILITY
    return UserIntent.GENERAL


def is_add_intent(text: str) -> bool:
    return detect_intent(text) == UserIntent.ADD_ITEM


def is_allergies_step_answer(text: str, intent: UserIntent) -> bool:
    """Caller answered the allergies / special-instructions question."""
    if intent in (UserIntent.CONFIRM_NO, UserIntent.PICKUP, UserIntent.DELIVERY):
        return True
    t = (text or "").lower()
    if "allerg" in t or "ਐਲਰਜੀ" in text:
        return True
    if intent == UserIntent.CONFIRM_YES and ("instruction" in t or "special" in t):
        return True
    # Short no / bas after allergies prompt
    if intent == UserIntent.CONFIRM_NO:
        return True
    if intent == UserIntent.GENERAL and _NO_RE.search(text):
        return True
    return False


# ── Templates (B-7, B-5) ────────────────────────────────────────────────────


def format_price_reply(price_dollars: float) -> str:
    """Single-line English price — no fluff."""
    amount = (
        int(round(price_dollars))
        if abs(price_dollars - round(price_dollars)) < 0.05
        else round(price_dollars, 2)
    )
    if isinstance(amount, float):
        return f"That's about {amount:.2f} dollars ji."
    return f"That's about {amount} dollars ji."


def _qty_word(n: int) -> str:
    return _QTY_WORDS.get(n, str(n))


def _format_dollars(amount: float) -> str:
    if abs(amount - round(amount)) < 0.05:
        return str(int(round(amount)))
    return f"{amount:.2f}"


def format_order_readback(cart: OrderCart) -> str:
    """Exact spoken read-back line for final confirmation (Step E)."""
    if cart.is_empty:
        return ""

    item_parts: list[str] = []
    for item in cart.items:
        qty = _qty_word(item.quantity)
        name = item.voice_line or item.name
        if item.note:
            item_parts.append(f"{qty} {name} ({item.note})")
        else:
            item_parts.append(f"{qty} {name}")

    if len(item_parts) == 1:
        items_str = item_parts[0]
    elif len(item_parts) == 2:
        items_str = f"{item_parts[0]} and {item_parts[1]}"
    else:
        items_str = ", ".join(item_parts[:-1]) + f", and {item_parts[-1]}"

    order_type = cart.order_type or "pickup"
    total = _format_dollars(cart.total)
    name = cart.customer_name or ""

    if name:
        return (
            f"Okay {name} ji — {items_str}, {order_type}, "
            f"total about {total} dollars. {CONFIRM_CLOSE}"
        )
    return f"Okay — {items_str}, {order_type}, total about {total} dollars. {CONFIRM_CLOSE}"


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
        out = _GREETING_RE.sub("", out).strip()
        if not out or len(out) < 8:
            out = recovery_phrase(is_phone=True)

    replacements = {
        "ਸوری": "ਮਾਫ ਕਰਨਾ",
        "سوری": "ਮਾਫ ਕਰਨਾ",
    }
    for bad, good in replacements.items():
        out = out.replace(bad, good)

    return out.strip()
