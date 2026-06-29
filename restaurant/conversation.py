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

OPENING_GREETING = (
    "Hi! Sierra from Bizbull here. "
    "I speak English, Hindi, and Punjabi. How can I help?"
)

# ── Customer language (script detection + turn guidance) ────────────────────


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


def language_turn_guidance(lang: CustomerLanguage) -> str:
    """Per-turn LLM hint: conversational language vs fixed English order steps."""
    fixed = "Fixed SAY EXACTLY order steps (allergies, pickup, quantity, read-back) stay English."
    guides = {
        CustomerLanguage.PUNJABI: (
            "Customer language: Punjabi — conversational reply in natural Gurmukhi code-mix. "
            "Use English only for voice_line dish names, prices, digits. "
        ),
        CustomerLanguage.HINDI: (
            "Customer language: Hindi — conversational reply in Devanagari code-mix. "
            "Use English only for voice_line dish names, prices, digits. "
        ),
        CustomerLanguage.ENGLISH: (
            "Customer language: English — conversational reply in English. "
        ),
        CustomerLanguage.MIXED: (
            "Customer language: code-mix — match their Punjabi/Hindi/English mix naturally. "
        ),
    }
    return guides.get(lang, guides[CustomerLanguage.ENGLISH]) + fixed


def phrase_anything_else(lang: CustomerLanguage) -> str:
    return {
        CustomerLanguage.ENGLISH: "Anything else?",
        CustomerLanguage.PUNJABI: "ਹੋਰ ਕੁਝ?",
        CustomerLanguage.HINDI: "और कुछ?",
        CustomerLanguage.MIXED: "Anything else?",
    }.get(lang, "Anything else?")


def phrase_name_for_order(lang: CustomerLanguage) -> str:
    return {
        CustomerLanguage.ENGLISH: "Can I get a name for the order?",
        CustomerLanguage.PUNJABI: "ਆਰਡਰ ਲਈ ਨਾਮ ਦੱਸੋ ਜੀ?",
        CustomerLanguage.HINDI: "ऑर्डर के लिए नाम बता सकते हैं?",
        CustomerLanguage.MIXED: "Can I get a name for the order?",
    }.get(lang, "Can I get a name for the order?")


def phrase_repeat_request(lang: CustomerLanguage) -> str:
    return {
        CustomerLanguage.ENGLISH: "Sorry, could you say that again?",
        CustomerLanguage.PUNJABI: "ਮਾਫ ਕਰਨਾ ਜੀ — ਦੁਬਾਰਾ ਦੱਸੋ?",
        CustomerLanguage.HINDI: "Sorry ji — phir se bol sakte hain?",
        CustomerLanguage.MIXED: "Sorry, could you say that again?",
    }.get(lang, "Sorry, could you say that again?")



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

# Phone STT often hears "pickup" as "one cup" / "one up" (Gurmukhi or English).
_PICKUP_STT_RE = re.compile(
    r"(?:"
    r"ਇ(?:ੱਕ|ਕ)\s*(?:ਕ(?:ੱ?)?(?:ੱਪ|ਪ)|ਅ(?:ੱ?)?(?:ੱਪ|ਪ)|ਅਪ)|"
    r"ਇਕ\s*(?:ਕ(?:ੱ?)?(?:ੱਪ|ਪ)|ਅ(?:ੱ?)?(?:ੱਪ|ਪ))|"
    r"pick\s*up|"
    r"one\s+cup|"
    r"ikk\s+(?:cup|app|up)"
    r")",
    re.I,
)

_ALL_GOOD_RE = re.compile(
    r"(?:all good|al good|aal good|ਆਲ\s*ਗ[uੰ]?[dD]?|ਆਲ\s*ਗ[uੰ]?ਡ)",
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
    r"ਚਾਹੀ(?:ਦਾ|ਦੀ|ਦੇ)|ਆਰਡਰ|ਪਾ ਦ|ਜੋੜ|ਲੈ|ਕਰ ਦ"
    r")\b",
    re.I,
)

_QTY_ITEM_RE = re.compile(
    r"\b("
    r"one|two|three|four|five|six|seven|eight|nine|ten|"
    r"ਇੱਕ|ਐਕ|ਦੋ|ਤਿੰਨ|"
    r"\d+"
    r")\s+\w+",
    re.I,
)

_I_SAID_RE = re.compile(r"\b(i said|ਕਿਹਾ)\b", re.I)

_ALLERGY_NO_RE = re.compile(
    r"\b("
    r"not at all|no allergy|no allergies|none at all|nothing at all|"
    r"not really|don't have any|do not have any|"
    r"not not"
    r")\b",
    re.I,
)

_WANT_ORDER_ONLY_RE = re.compile(
    r"\b("
    r"i want to order|want to order|order karna|order kar|"
    r"ਆਰਡਰ ਕਰ|ਕੁਝ ਆਰਡਰ"
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
    r"^(yes|yeah|yep|yup|correct|right|ok|okay|all good|"
    r"haan|han|ha ji|ji|"
    r"ਹਾਂ|ਠੀਕ|ਬਿਲਕੁਲ|ਜੀ)"
    r"(?:\s+(ji|ਜੀ|hai|ਹੈ))?"
    r"[\s\.।,!?]*$",
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
    r"(sat\s*sri\s*akal|ਸਤ\s*ਸ੍ਰੀ\s*ਅਕਾਲ|welcome to bizbull|"
    r"how may i help you today|how can i help|"
    r"sierra from bizbull|i.?m sierra from bizbull|"
    r"i speak english|english,?\s*hindi,?\s*(?:and|or)\s*punjabi|"
    r"i can help you in english)",
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


def is_want_to_order_only(text: str) -> bool:
    """Caller wants to order but has not named a dish yet."""
    t = (text or "").strip()
    if not t or not _WANT_ORDER_ONLY_RE.search(t):
        return False
    if _QTY_ITEM_RE.search(t) or menu_item_hint_in_text(t):
        return False
    return True


def menu_item_hint_in_text(text: str) -> bool:
    """Heuristic: utterance names a likely menu item (used for intent routing)."""
    from restaurant import menu_provider

    return menu_provider.resolve_item_in_text(text) is not None


def is_likely_pickup_stt(text: str) -> bool:
    """Misheard pickup on phone — e.g. ਇੱਕ ਕੱਪ, ਇੱਕ ਅੱਪ, pick up."""
    t = (text or "").strip()
    if not t or _DELIVERY_RE.search(t):
        return False
    if _PICKUP_RE.search(t) or _PICKUP_STT_RE.search(t):
        return True
    if _I_SAID_RE.search(t) and re.search(
        r"ਕ(?:ੱ?)?(?:ੱਪ|ਪ)|ਅ(?:ੱ?)?(?:ੱਪ|ਪ)|cup|pick|pickup",
        t,
        re.I,
    ):
        return True
    return False


def is_confirm_yes(text: str) -> bool:
    """Short affirmative — haan ji / ਹਾਂ ਜੀ / yes / ok / all good."""
    t = re.sub(r"[\s\.।,!?]+$", "", (text or "").strip())
    if not t:
        return False
    if _YES_RE.match(t):
        return True
    # STT sometimes drops ji: "haan" or lone "ji" / "ਜੀ" after All good?
    if re.match(r"^(haan|han|ਹਾਂ|ji|ਜੀ|ok|okay|yes|yeah)$", t, re.I):
        return True
    if _ALL_GOOD_RE.search(t):
        return True
    if re.search(r"(yes|yeah|yep|yup|ਯੇਸ)", t, re.I) and _ALL_GOOD_RE.search(t):
        return True
    if re.search(r"ਹਾਂ", t) and (_ALL_GOOD_RE.search(t) or re.search(r"\bgood\b", t, re.I)):
        return True
    return False


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
    if is_confirm_yes(t):
        return UserIntent.CONFIRM_YES
    if _PICKUP_RE.search(t) and not _DELIVERY_RE.search(t):
        return UserIntent.PICKUP
    if _DELIVERY_RE.search(t):
        return UserIntent.DELIVERY
    if _ALLERGY_NO_RE.search(t):
        return UserIntent.CONFIRM_NO
    if re.search(r"ਚਾਹੀ(?:ਦਾ|ਦੀ|ਦੇ)", t):
        return UserIntent.ADD_ITEM
    if _I_SAID_RE.search(t) or _QTY_ITEM_RE.search(t):
        return UserIntent.ADD_ITEM
    if _NO_RE.search(t):
        return UserIntent.CONFIRM_NO
    if _ADD_RE.search(t):
        return UserIntent.ADD_ITEM
    if _AVAIL_RE.search(t):
        return UserIntent.ASK_AVAILABILITY
    return UserIntent.GENERAL


def resolve_intent(text: str, *, phase: str | None = None) -> UserIntent:
    """Phase-aware intent — e.g. pickup STT at order_type before qty-add false positive."""
    intent = detect_intent(text)
    if phase == "order_type":
        if is_likely_pickup_stt(text):
            return UserIntent.PICKUP
        if _DELIVERY_RE.search(text):
            return UserIntent.DELIVERY
    return intent


def is_add_intent(text: str) -> bool:
    return detect_intent(text) == UserIntent.ADD_ITEM


def is_allergies_step_answer(text: str, intent: UserIntent) -> bool:
    """Caller answered the allergies / special-instructions question."""
    if intent in (UserIntent.CONFIRM_NO, UserIntent.PICKUP, UserIntent.DELIVERY):
        return True
    t = (text or "").lower()
    if _ALLERGY_NO_RE.search(text):
        return True
    if "allerg" in t or "ਐਲਰਜੀ" in text:
        return True
    if intent == UserIntent.CONFIRM_YES and ("instruction" in t or "special" in t):
        return True
    if intent == UserIntent.CONFIRM_NO:
        return True
    if intent == UserIntent.GENERAL and (_NO_RE.search(text) or _ALLERGY_NO_RE.search(text)):
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


def format_order_readback(cart: OrderCart, *, include_price: bool = True) -> str:
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


def background_repeat_phrase() -> str:
    """One reprompt when background noise caused dropped turns."""
    return "Sorry, I didn't catch that — could you repeat please?"


# ── Assistant output guard (B-6) ──────────────────────────────────────────────


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
    r"about \d+(?:\.\d+)?\s*dollars?"
    r")",
    re.I,
)


def sanitize_assistant_speech(text: str, *, allow_greeting: bool, is_phone: bool = True) -> str:
    """Strip mid-call re-greetings; normalize common script slips."""
    if not text or allow_greeting:
        return text

    out = text
    if _GREETING_RE.search(out):
        out = _GREETING_RE.sub("", out).strip()
        if not out or len(out) < 8:
            out = recovery_phrase(is_phone=True)

    if _META_SPEECH_RE.search(out):
        out = _META_SPEECH_RE.sub("", out)
        out = re.sub(r"\s{2,}", " ", out).strip(" ,.-")
        if not out or len(out) < 6:
            out = "Sure."

    if is_phone and _PRICE_SPEECH_RE.search(out):
        out = _PRICE_SPEECH_RE.sub("", out)
        out = re.sub(r"\s{2,}", " ", out).strip(" ,.-")
        if not out or len(out) < 8:
            out = "Sure."

    replacements = {
        "ਸوری": "ਮਾਫ ਕਰਨਾ",
        "سوری": "ਮਾਫ ਕਰਨਾ",
    }
    for bad, good in replacements.items():
        out = out.replace(bad, good)

    return out.strip()
