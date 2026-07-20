"""Status templates, canned lines, and the assistant speech guard.

Salvaged from conversation.py — these encode hard-won live-call lessons
(no price on phone, English phone digits). The SAY EXACTLY tool-reply
formatters were replaced by structured facts in restaurant/agent/facts.py
(PR 075); the VERBATIM readback template by READBACK FACTS + the spoken
verifier in restaurant/agent/readback_verify.py (PR 078).
"""

from __future__ import annotations

import random
import re
from typing import TYPE_CHECKING

from restaurant.agent.facts import _qty_word
from restaurant.customer_info import enforce_english_phone_in_speech

if TYPE_CHECKING:
    from restaurant.orders import OrderCart

def _format_dollars(amount: float) -> str:
    if abs(amount - round(amount)) < 0.05:
        return str(int(round(amount)))
    return f"{amount:.2f}"


def order_placed_goodbye(*, order_type: str | None, language: str | None = None) -> str:
    """Fixed closing line after a successful order — spoken by code (hang-up
    choreography), variant keyed off the customer's preferred language.
    Punjabi remains the default for pa/mixed/unknown."""
    delivery = order_type == "delivery"
    lang = str(language or "").lower()
    if lang == "en":
        wait = "30 to 40 minutes" if delivery else "20 to 25 minutes"
        return (
            f"Perfect, your order's in! It'll be ready in {wait}. "
            "Thank you so much ji — see you soon!"
        )
    if lang == "hi":
        wait = "30-40 मिनट" if delivery else "20-25 मिनट"
        return (
            f"आपका ऑर्डर मिल गया जी! {wait} में तैयार हो जाएगा। "
            "धन्यवाद जी, फिर मिलेंगे!"
        )
    wait = "30-40 ਮਿੰਟ" if delivery else "20-25 ਮਿੰਟ"
    return (
        f"ਤੁਹਾਡਾ ਆਰਡਰ ਮਿਲ ਗਿਆ ਜੀ! {wait} ਵਿੱਚ ਤਿਆਰ ਹੋ ਜਾਵੇਗਾ। ਬਹੁਤ ਬਹੁਤ ਧੰਨਵਾਦ ਜੀ!"
    )


def _cart_items_str(cart: "OrderCart") -> str:
    """Comma-joined spoken item list for the status template."""
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
    far; the final-confirmation readback is READBACK FACTS (facts.py, PR 078).
    """
    if cart.is_empty:
        return "Your order is empty so far."

    items_str = _cart_items_str(cart)
    if include_price:
        total = _format_dollars(cart.total)
        return f"So far you have — {items_str}, total about {total} dollars."
    return f"So far you have — {items_str}."


def recovery_phrase(*, is_phone: bool) -> str:
    """After missed turn or echo — never re-greet."""
    if is_phone:
        return "Sorry ji — go ahead, I'm listening."
    return "Sorry ji — go ahead whenever you're ready."


# Reprompt variant pools (PR 077) — spoken by code under StopResponse, so no
# LLM turn exists to vary them; a small pool + no-immediate-repeat does it.
# Every fragment here must stay covered by phone_echo._RECOVERY_ECHO_PHRASES
# so an echo of our own reprompt is never treated as caller speech.
_ECHO_RECOVERY_POOL = (
    "ਮੈਂ ਸੁਣ ਰਹੀ ਹਾਂ — go ahead ji.",
    "ਹਾਂ ਜੀ, ਮੈਂ ਸੁਣ ਰਹੀ ਹਾਂ — take your time.",
    "Go ahead ji — I'm listening.",
)

_BACKGROUND_REPEAT_POOL = (
    "Sorry, I didn't catch that — could you repeat please?",
    "Sorry ji, it got a little noisy there — one more time please?",
    "ਮਾਫ਼ ਕਰਨਾ ਜੀ, ਇੱਕ ਵਾਰ ਫਿਰ ਦੱਸੋਗੇ?",
)

_last_variant: dict[str, str] = {}


def _pick_variant(key: str, pool: tuple[str, ...]) -> str:
    options = [line for line in pool if line != _last_variant.get(key)] or list(pool)
    line = random.choice(options)
    _last_variant[key] = line
    return line


def echo_recovery_phrase() -> str:
    """Short reprompt after phone echo drop — avoid echoing Sierra's own prior line."""
    return _pick_variant("echo", _ECHO_RECOVERY_POOL)


def background_repeat_phrase() -> str:
    """One reprompt when background noise caused dropped turns."""
    return _pick_variant("background", _BACKGROUND_REPEAT_POOL)


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
