"""Tool-reply formatters, readback templates, and the assistant speech guard.

Salvaged verbatim from conversation.py — these encode hard-won live-call
lessons (no price on phone, no cart/menu meta-speech, English phone digits,
exact readback text generated from the code cart).
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from restaurant.agent.language import CustomerLanguage
from restaurant.customer_info import enforce_english_phone_in_speech

if TYPE_CHECKING:
    from restaurant.orders import OrderCart

CONFIRM_CLOSE = "All good?"

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


def _qty_word(n: int) -> str:
    return _QTY_WORDS.get(n, str(n))


def _format_dollars(amount: float) -> str:
    if abs(amount - round(amount)) < 0.05:
        return str(int(round(amount)))
    return f"{amount:.2f}"


def order_placed_goodbye(*, order_type: str | None) -> str:
    """Fixed Punjabi closing line after a successful order."""
    wait = "30-40 ਮਿੰਟ" if order_type == "delivery" else "20-25 ਮਿੰਟ"
    return (
        f"ਤੁਹਾਡਾ ਆਰਡਰ ਮਿਲ ਗਿਆ ਜੀ। {wait} ਵਿੱਚ ਤਿਆਰ ਹੋ ਜਾਵੇਗਾ। ਧੰਨਵਾਦ ਜੀ!"
    )


def confirm_items_added(
    entries: list[tuple[int, str]],
    lang: CustomerLanguage,
    *,
    updated: bool = False,
) -> str:
    """Cashier-style add confirm — no price, no cart/menu language."""
    if not entries:
        return "Sure."

    if updated and len(entries) == 1:
        qty, voice = entries[0]
        word = _qty_word(qty)
        if lang == CustomerLanguage.PUNJABI:
            return f"ਠੀਕ ਹੈ — {word} {voice} ਹੁਣ।"
        if lang == CustomerLanguage.HINDI:
            return f"ठीक है — {word} {voice} अब।"
        return f"Sure — {word} {voice} now."

    parts = [f"{_qty_word(qty)} {voice}" for qty, voice in entries]

    if lang == CustomerLanguage.PUNJABI:
        prefix, joiner = "ਠੀਕ ਹੈ — ", " ਤੇ "
    elif lang == CustomerLanguage.HINDI:
        prefix, joiner = "ठीक है — ", " और "
    else:
        prefix, joiner = "Yes — ", " and "

    if len(parts) == 1:
        body = parts[0]
    elif len(parts) == 2:
        body = f"{parts[0]}{joiner}{parts[1]}"
    else:
        body = ", ".join(parts[:-1]) + joiner + parts[-1]
    return f"{prefix}{body}."


def format_add_tool_reply(
    entries: list[tuple[int, str]],
    *,
    updated: bool = False,
) -> str:
    confirm = confirm_items_added(entries, CustomerLanguage.ENGLISH, updated=updated)
    return (
        "INTERNAL: item saved.\n"
        f'SAY EXACTLY: "{confirm}"\n'
        "Do NOT mention price, cart, menu, pieces, or say I can add / I've added."
    )


def format_remove_tool_reply(voice_line: str) -> str:
    confirm = f"Sure — removed {voice_line}."
    return (
        "INTERNAL: item removed.\n"
        f'SAY EXACTLY: "{confirm}"\n'
        "Do NOT mention cart or menu."
    )


def format_update_tool_reply(quantity: int, voice_line: str) -> str:
    """Correction confirm — distinct from add so it never reads as a second add."""
    word = _qty_word(quantity)
    confirm = f"Got it — {word} {voice_line}, fixed."
    return (
        "INTERNAL: quantity corrected (not added).\n"
        f'SAY EXACTLY: "{confirm}"\n'
        "Do NOT mention price, cart, or menu."
    )


def _cart_items_str(cart: "OrderCart") -> str:
    """Comma-joined spoken item list — shared by read-back and status templates."""
    item_parts: list[str] = []
    for item in cart.items:
        qty = _qty_word(item.quantity)
        name = item.voice_line or item.name
        if item.note:
            item_parts.append(f"{qty} {name} ({item.note})")
        else:
            item_parts.append(f"{qty} {name}")

    if len(item_parts) == 1:
        return item_parts[0]
    if len(item_parts) == 2:
        return f"{item_parts[0]} and {item_parts[1]}"
    return ", ".join(item_parts[:-1]) + f", and {item_parts[-1]}"


def format_order_status(cart: "OrderCart", *, include_price: bool = True) -> str:
    """Neutral mid-conversation cart read — grounded in real cart data, never
    LLM-improvised. Used whenever the customer asks what's in their order so
    far; distinct from format_order_readback, which is the final-confirmation
    line and assumes order_type/close are already meaningful.
    """
    if cart.is_empty:
        return "Your order is empty so far."

    items_str = _cart_items_str(cart)
    if include_price:
        total = _format_dollars(cart.total)
        return f"So far you have — {items_str}, total about {total} dollars."
    return f"So far you have — {items_str}."


def format_order_readback(cart: "OrderCart", *, include_price: bool = True) -> str:
    """Exact spoken read-back line for final confirmation."""
    if cart.is_empty:
        return ""

    items_str = _cart_items_str(cart)
    order_type = cart.order_type or "pickup"
    name = cart.customer_name or ""

    if include_price:
        total = _format_dollars(cart.total)
        if name:
            return (
                f"Okay {name} ji — {items_str}, {order_type}, "
                f"total about {total} dollars. {CONFIRM_CLOSE}"
            )
        return f"Okay — {items_str}, {order_type}, total about {total} dollars. {CONFIRM_CLOSE}"

    if name:
        return f"Okay {name} ji — {items_str}, {order_type}. {CONFIRM_CLOSE}"
    return f"Okay — {items_str}, {order_type}. {CONFIRM_CLOSE}"


def recovery_phrase(*, is_phone: bool) -> str:
    """After missed turn or echo — never re-greet."""
    if is_phone:
        return "Sorry ji — go ahead, I'm listening."
    return "Sorry ji — go ahead whenever you're ready."


# ── Assistant output guard ────────────────────────────────────────────────────


_GREETING_RE = re.compile(
    r"(sat\s*sri\s*akal|ਸਤ\s*ਸ੍ਰੀ\s*ਅਕਾਲ|welcome to bizbull|"
    r"how may i help you today|how can i help|"
    r"sierra from bizbull|i.?m sierra from bizbull|"
    r"i speak english|english,?\s*hindi,?\s*(?:and|or)\s*punjabi|"
    r"i can help you in english)",
    re.I,
)

_META_SPEECH_RE = re.compile(
    r"\b(?:"
    r"I can add|I(?:'ve| have) added|added to (?:the )?(?:cart|menu|order)|"
    r"comes with \d+ pieces?"
    r")\b",
    re.I,
)

_PRICE_SPEECH_RE = re.compile(
    r"(?:"
    r",?\s*total about [\d.]+\s*dollars?|"
    r"\$\s*[\d.]+|"
    r"about \d+(?:\.\d+)?\s*dollars?|"
    r"(?:,\s*)?(?:ਕੁੱ?\s*)?(?:total|ਕੁੱ?|ਤਕਰੀਬ(?:ਨ)?)"
    r"[^.?!]*(?:dollars?|ਡਾਲਰ)|"
    r"[\d.]+\s*(?:ਡਾਲਰ|dollars?)"
    r")",
    re.I,
)

_LLM_JUNK_RE = re.compile(
    r"(?:"
    r"ਪ[uu]?[sś][h]?[tṭ][iī]|push\s*confirm|confirm\s*push|"
    r"confirm(?:ing)?\s+(?:the\s+)?order|"
    r"ਚੇਲਾ|chela"
    r")",
    re.I,
)

_PUNJABI_CONFIRM_RE = re.compile(
    r"ਪ[uu]?[sś][h]?[tṭ][iī]\s*ਕਰ",
    re.I,
)


def sanitize_assistant_speech(
    text: str,
    *,
    allow_greeting: bool,
    is_phone: bool = True,
    customer_phone: str | None = None,
) -> str:
    """Strip mid-call re-greetings; normalize common script slips."""
    if not text:
        return text

    out = text
    if not allow_greeting:
        if _GREETING_RE.search(out):
            out = _GREETING_RE.sub("", out).strip()
            if not out or len(out) < 8:
                out = recovery_phrase(is_phone=True)

        if _META_SPEECH_RE.search(out):
            out = _META_SPEECH_RE.sub("", out)
            out = re.sub(r"\s{2,}", " ", out).strip(" ,.-")
            if not out or len(out) < 6:
                out = "Sure."

        if _PRICE_SPEECH_RE.search(out):
            out = _PRICE_SPEECH_RE.sub("", out)
            out = re.sub(r"\s{2,}", " ", out).strip(" ,.-")
            if not out or len(out) < 8:
                out = "Sure."

        replacements = {
            "ਸوری": "ਮਾਫ ਕਰਨਾ",
            "سوری": "ਮਾਫ ਕਰਨਾ",
            "سفارش": "ਆਰਡਰ",
        }
        for bad, good in replacements.items():
            out = out.replace(bad, good)

        if _LLM_JUNK_RE.search(out):
            out = _LLM_JUNK_RE.sub("", out)
            out = re.sub(r"\s{2,}", " ", out).strip(" ,.-")

        if _PUNJABI_CONFIRM_RE.search(out):
            out = _PUNJABI_CONFIRM_RE.sub("confirm", out)

        out = re.sub(r"\bDhanyavaad\b", "ਧੰਨਵਾਦ", out, flags=re.I)
        out = re.sub(r"\bdhanyavaad\b", "ਧੰਨਵਾਦ", out, flags=re.I)

    if customer_phone:
        out = enforce_english_phone_in_speech(out, customer_phone)

    return out.strip()
