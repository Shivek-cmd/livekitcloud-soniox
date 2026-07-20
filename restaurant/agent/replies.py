"""Status templates and canned lines (goodbye, reprompt pools).

Salvaged from conversation.py. The SAY EXACTLY tool-reply formatters were
replaced by structured facts in restaurant/agent/facts.py (PR 075); the
VERBATIM readback template by READBACK FACTS + the spoken verifier in
restaurant/agent/readback_verify.py (PR 078); the log-only regex speech guard
(sanitize_assistant_speech) was deleted in PR 079 — phone-digit enforcement
now lives in the real TTS path (restaurant/agent/tts_transform.py).
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

from restaurant.agent.facts import _qty_word

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
