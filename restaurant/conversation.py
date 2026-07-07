"""Intent detection, spoken templates, and assistant speech guards (Tier B-5/B-6/B-7)."""

from __future__ import annotations

import re
from enum import Enum

from restaurant.customer_info import (
    enforce_english_phone_in_speech,
    looks_like_phone_utterance,
    parse_customer_name,
)
from restaurant.orders import OrderCart
from restaurant.text_match import indic_word_re, word_bounded

# ── Fixed spoken lines (Canadian Punjabi restaurant code-mix) ─────────────────

ALLERGIES_QUESTION = "Any allergies or special instructions?"
PICKUP_DELIVERY_QUESTION = "Will that be pickup or delivery?"
QUANTITY_QUESTION = "How many — one or two?"
CONFIRM_CLOSE = "All good?"

OPENING_GREETING = (
    "Hi! I'm Sierra, your virtual assistant. "
    "I speak English, Hindi, and Punjabi. How can I help you?"
)


def order_placed_goodbye(*, order_type: str | None) -> str:
    """Fixed Punjabi closing line after a successful order."""
    wait = "30-40 ਮਿੰਟ" if order_type == "delivery" else "20-25 ਮਿੰਟ"
    return (
        f"ਤੁਹਾਡਾ ਆਰਡਰ ਮਿਲ ਗਿਆ ਜੀ। {wait} ਵਿੱਚ ਤਿਆਰ ਹੋ ਜਾਵੇਗਾ। ਧੰਨਵਾਦ ਜੀ!"
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
    fixed = (
        "Fixed SAY EXACTLY order steps (allergies, pickup, quantity, read-back) stay English. "
        "Never say ਪੁਸ਼ਟੀ/push confirm — use English confirm/read-back lines only. "
        "Phone numbers ALWAYS spoken as English words (nine, four, one, …) — NEVER Punjabi/Hindi digits."
    )
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


def phrase_ask_phone(lang: CustomerLanguage, name: str) -> str:
    """After name saved — ask for phone; preserve exact name spelling."""
    if lang == CustomerLanguage.PUNJABI:
        return f"{name} ਜੀ — ਫੋਨ ਨੰਬਰ ਦੱਸੋ ਜੀ?"
    if lang == CustomerLanguage.HINDI:
        return f"{name} ji — phone number bata sakte hain?"
    return f"Thanks {name} ji — what's the phone number?"


def phrase_phone_saved(lang: CustomerLanguage, phone_spoken: str) -> str:
    """Phone readback — English digits only in the spoken part."""
    if lang in (CustomerLanguage.PUNJABI, CustomerLanguage.MIXED):
        return f"ਧੰਨਵਾਦ ਜੀ — {phone_spoken}."
    if lang == CustomerLanguage.HINDI:
        return f"ਧੰਨਵਾਦ ਜੀ — {phone_spoken}."
    return f"Got it — {phone_spoken}."



class UserIntent(str, Enum):
    GENERAL = "general"
    ASK_PRICE = "ask_price"
    ASK_AVAILABILITY = "ask_availability"
    ASK_ORDER_STATUS = "ask_order_status"
    ADD_ITEM = "add_item"
    ORDER_DONE = "order_done"
    CONFIRM_YES = "confirm_yes"
    CONFIRM_NO = "confirm_no"
    PICKUP = "pickup"
    DELIVERY = "delivery"
    HUMAN = "human"
    UNCLEAR = "unclear"


# NOTE (PR 034): plain \b is broken for Gurmukhi/Devanagari — matras and bindi
# are not \w, so \bਨਹੀਂ\b never matches. Multi-script patterns use indic_word_re.
_PRICE_RE = indic_word_re(
    r"price|prices|cost|how much|kithe da|kitna|kina|kine da|"
    r"ਕੀਮਤ|ਕਿਨਾ|ਕਿੰਨੇ|ਦਾਮ|rate|"
    r"how many dollars|what.?s the price"
)

_AVAIL_RE = indic_word_re(
    r"do you have|have you got|is there|available|hai\??|hain\??|"
    r"mil.?ega|mil.?egi|kya hai|kya hain|"
    r"ਕੀ\s*ਹੈ|ਕੀ\s*ਹਨ|ਮਿਲੇਗ|ਚ\s*ਕੀ\s*ਹੈ"
)

# Customer asking what's already in their order — must win over _ADD_RE below,
# which contains the bare word "order"/"ਆਰਡਰ" and would otherwise misclassify
# a status question ("ਕੀ ਆਰਡਰ ਕੀਤਾ ਜੀ ਮੈਂ?") as a new add request (PR 042).
_ORDER_STATUS_RE = indic_word_re(
    r"what.?s my order|what is my order|what do i have|what did i order|"
    r"what have i ordered|what.?s in my order|what.?s on my order|"
    r"read (?:back )?my order|repeat my order|tell me my order|order so far|"
    r"ਮੇਰਾ ਆਰਡਰ|ਆਰਡਰ ਦੱਸੋ|ਕੀ ਆਰਡਰ ਕੀਤਾ|ਆਰਡਰ ਕੀ ਹੈ|ਹੁਣ ਤੱਕ.*ਕੀ|"
    r"मेरा ऑर्डर|ऑर्डर बताओ|क्या ऑर्डर"
)

_PICKUP_RE = indic_word_re(
    r"pickup|pick up|pick-up|takeaway|take away|"
    r"ਪਿਕਅੱਪ|ਪਿਕ ਅੱਪ|ਪਿਕ.*ਕਰ|pick.*up"
)

_READBACK_ACK_RE = indic_word_re(
    r"check|chacko|chakko|theek|thik|ok|okay|"
    r"ਚੈਕ|ਚੈਕੋ|ਠੀਕ|ਠੀਕ\s*ਐ|ਹਾਂ\s*ਠੀਕ"
)

_READBACK_ALL_CLEAR_RE = re.compile(
    r"(?:"
    r"ਕੋਈ\s*ਗ(?:\u0a71)?(?:ੱ)?(?:ਾ)?ਲ\s*ਨਹੀ|"
    r"koi gall nahi|no problem|no issues|sab thik|sab theek|"
    r"ਨਹੀ[^\s,]*\s*ਜੀ\s*,?\s*ਕੋਈ\s*ਗ(?:\u0a71)?(?:ੱ)?(?:ਾ)?ਲ"
    r")",
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

_DELIVERY_RE = indic_word_re(
    r"delivery|deliver|home delivery|ਡਿਲਿਵਰੀ|ਘਰ.*ਡਿਲਿਵਰ"
)

_ADD_RE = indic_word_re(
    r"add|order|want|need|get me|give me|i.?ll take|i want|"
    r"i'd like|chahiye|dedo|de do|lao|"
    r"order karo|order kar|add karo|add kar|"
    r"ਚਾਹੀ(?:ਦਾ|ਦੀ|ਦੇ)|ਆਰਡਰ|ਪਾ ਦ|ਜੋੜ|ਲੈ|ਕਰ ਦ|ਐਡ|"
    # Devanagari (Hindi script) equivalents — live-call regression: a
    # caller's Hindi-script add request ("एक प्लेन राइस भी कर दियो") was
    # never recognized because these patterns previously only covered
    # Gurmukhi and Latin script, despite the greeting itself advertising
    # Hindi support.
    r"चाहि(?:ए|ये|या)|ऑर्डर|डाल द|जोड़|ले|कर द|एड"
)

_QTY_ITEM_RE = re.compile(
    word_bounded(
        r"one|two|three|four|five|six|seven|eight|nine|ten|"
        r"ਇੱਕ|ਐਕ|ਦੋ|ਤਿੰਨ|"
        r"\d+"
    )
    + r"\s+\w+",
    re.I,
)

_I_SAID_RE = indic_word_re(r"i said|ਕਿਹਾ")

_ALLERGY_NO_RE = re.compile(
    r"\b("
    r"not at all|no allergy|no allergies|none at all|nothing at all|"
    r"not really|don't have any|do not have any|"
    r"not not"
    r")\b",
    re.I,
)

_WANT_ORDER_ONLY_RE = indic_word_re(
    r"i want to order|want to order|order karna|order kar|"
    r"ਆਰਡਰ ਕਰ|ਕੁਝ ਆਰਡਰ"
)

_DONE_RE = indic_word_re(
    r"that.?s it|that.?s all|nothing else|no more|bas|bus|"
    r"done ordering|i.?m done|finish|"
    r"ਬਸ|ਹੋ ਗਿਆ|ਔਰ ਨਹੀ|ਕੁਝ ਨਹੀ|ਨਹੀਂ.*ਬਸ|"
    r"बस|हो गया"
)

_ENOUGH_RE = indic_word_re(
    r"enough|that.?s enough|bahut|bohot|"
    r"ਬਹੁਤ|काफी|bahut hai"
)

_YES_RE = re.compile(
    r"^(yes|yeah|yep|yup|correct|right|ok|okay|all good|"
    r"haan|han|ha ji|ji|"
    r"ਹਾਂ|ਠੀਕ|ਬਿਲਕੁਲ|ਜੀ|"
    r"हाँ|ठीक|बिल्कुल|जी)"
    r"(?:\s+(ji|ਜੀ|hai|ਹੈ|जी))?"
    r"[\s\.।,!?]*$",
    re.I,
)

_NO_RE = indic_word_re(
    r"^no\.?$|nope|nah|nothing|none|"
    r"nahi|nahin|na|"
    r"ਨਹੀਂ|ਨਹੀ|ਕੋਈ.*ਨਹੀਂ|ਕੁਝ ਨਹੀ|"
    r"नहीं|नही"
)

# Leading-only negative — the entire utterance must OPEN with a negative word
# (mirrors _YES_RE's anchoring). Unlike _NO_RE above (unanchored, matches "no/not"
# ANYWHERE), this does not fire when the negation is buried inside an unrelated
# sentence, e.g. a predicate negation like "ਛੋਲੇ ਬਟੂਰੇ ਨਹੀਂ ਹਨ" (chole bhature
# isn't available) — live-call bug: that sentence was misread as CONFIRM_NO purely
# because it contains "ਨਹੀਂ", and the checkout ladder treated it as "no allergies"
# and skipped straight to pickup/delivery without the allergies question ever
# actually being answered.
_LEADING_NO_RE = re.compile(
    r"^\s*" + word_bounded(r"no\.?|nope|nah|nahi|nahin|na|ਨਹੀਂ|ਨਹੀ|नहीं|नही"),
    re.I,
)

_HUMAN_RE = indic_word_re(
    r"human|person|staff|manager|someone else|real person|"
    r"operator|agent|connect me|talk to someone|"
    r"ਬੰਦਾ|ਆਦਮੀ|manager|staff"
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
    if re.search(r"ਪਿਕ.*(?:ਕਰ|ਲ(?:ਾ|ੈ))", t):
        return True
    if _I_SAID_RE.search(t) and re.search(
        r"ਕ(?:ੱ?)?(?:ੱਪ|ਪ)|ਅ(?:ੱ?)?(?:ੱਪ|ਪ)|cup|pick|pickup",
        t,
        re.I,
    ):
        return True
    return False


def is_readback_ack(text: str) -> bool:
    """Short confirm at read-back — e.g. ਚੈਕੋ, check, theek."""
    t = re.sub(r"[\s\.।,!?]+$", "", (text or "").strip())
    if not t or len(t) > 32:
        return False
    return bool(_READBACK_ACK_RE.search(t))


def is_readback_all_clear(text: str) -> bool:
    """Caller confirms order is fine — 'no problem', 'ਕੋਈ ਗੱਲ ਨਹੀਂ'."""
    t = (text or "").strip()
    if not t:
        return False
    if _READBACK_ALL_CLEAR_RE.search(t):
        return True
    return False


def is_done_ordering(text: str) -> bool:
    """Caller finished adding items — including Punjabi 'ਨਹੀਂ ਨਹੀਂ, ਬਹੁਤ ਹੈ'."""
    t = (text or "").strip()
    if not t:
        return False
    if _DONE_RE.search(t):
        return True
    if _ENOUGH_RE.search(t) and _NO_RE.search(t):
        return True
    if re.search(r"ਨਹੀਂ\s+ਨਹੀਂ", t) and (_ENOUGH_RE.search(t) or "ਬਸ" in t):
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


def is_confirm_no(text: str) -> bool:
    """Leading/bare negative — 'no', 'ਨਹੀਂ,', 'nahi ji' — answering a yes/no
    question. Does NOT match a negation embedded later in an unrelated sentence
    (e.g. "ਛੋਲੇ ਬਟੂਰੇ ਨਹੀਂ ਹਨ" — chole bhature isn't available); see _LEADING_NO_RE."""
    t = (text or "").strip()
    if not t:
        return False
    return bool(_LEADING_NO_RE.match(t))


_ADD_IMPERATIVE_RE = re.compile(
    r"ਕਰੋ|ਕਰ ਦ|ਦਿਓ|ਦਿਉ|ਐਡ|\badd\b|"
    r"करो|कर द|दो|दिया|दियो|दीजिए",
    re.I,
)


def _add_item_with_action_cue(text: str) -> bool:
    """Named dish + an add-style verb — wins over a leading negation/filler
    word. Live-call regression (PR 042): "ਨਹੀਂ ਨਹੀਂ, ਗਾਰਲਿਕ ਨਾਨ ਕਰੋ" (customer
    restating/correcting an item after Sierra misheard) was classified
    CONFIRM_NO purely because it starts with "ਨਹੀਂ ਨਹੀਂ" — the explicit dish
    + imperative later in the same sentence was never considered, so the
    order-flow ladder advanced past allergies/pickup while the item was
    still never added.
    """
    if not _ADD_IMPERATIVE_RE.search(text):
        return False
    return menu_item_hint_in_text(text)


def detect_intent(text: str) -> UserIntent:
    t = (text or "").strip()
    if not t:
        return UserIntent.UNCLEAR
    if _HUMAN_RE.search(t):
        return UserIntent.HUMAN
    if _ORDER_STATUS_RE.search(t):
        return UserIntent.ASK_ORDER_STATUS
    if _PRICE_RE.search(t):
        return UserIntent.ASK_PRICE
    # Named dish + add-imperative wins over _DONE_RE — live-call regression
    # (PR 051): "ਬਸ ਇੱਕ ਮਸਾਲਾ ਚਾ ਕਰ ਦੋ" (JUST one masala chai) has "ਬਸ" acting
    # as a quantifier ("just"), not the discourse "that's it/done" _DONE_RE is
    # meant to catch — but the unanchored keyword match fired anyway, so the
    # order-done branch silently swallowed a live item order. Same class of
    # bug as PR 042's "ਨਹੀਂ ਨਹੀਂ, ਕਰੋ" fix, checked earlier here so it also
    # wins over _DONE_RE (not just the later is_confirm_no check).
    if _add_item_with_action_cue(t):
        return UserIntent.ADD_ITEM
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
    if re.search(r"ਚਾਹੀ(?:ਦਾ|ਦੀ|ਦੇ)|चाहि(?:ए|ये|या)", t):
        return UserIntent.ADD_ITEM
    if _I_SAID_RE.search(t) or _QTY_ITEM_RE.search(t):
        return UserIntent.ADD_ITEM
    if is_confirm_no(t):
        return UserIntent.CONFIRM_NO
    if _ADD_RE.search(t):
        return UserIntent.ADD_ITEM
    if _AVAIL_RE.search(t):
        return UserIntent.ASK_AVAILABILITY
    return UserIntent.GENERAL


def resolve_intent(text: str, *, phase: str | None = None) -> UserIntent:
    """Phase-aware intent — e.g. pickup STT at order_type before qty-add false positive."""
    if looks_like_phone_utterance(text):
        return UserIntent.GENERAL

    intent = detect_intent(text)

    if phase == "customer_name":
        if parse_customer_name(text):
            return UserIntent.GENERAL
        if intent == UserIntent.ADD_ITEM:
            return UserIntent.GENERAL
    if phase == "customer_phone":
        return UserIntent.GENERAL

    if phase == "awaiting_more":
        if is_done_ordering(text):
            return UserIntent.ORDER_DONE
        if intent == UserIntent.CONFIRM_NO:
            return UserIntent.ORDER_DONE

    if phase == "order_type":
        if is_likely_pickup_stt(text):
            return UserIntent.PICKUP
        if _DELIVERY_RE.search(text):
            return UserIntent.DELIVERY
    if phase == "readback":
        if is_readback_ack(text) or is_readback_all_clear(text):
            return UserIntent.CONFIRM_YES
        if is_confirm_yes(text):
            return UserIntent.CONFIRM_YES
    return intent


def is_add_intent(text: str) -> bool:
    return detect_intent(text) == UserIntent.ADD_ITEM


_ALREADY_SAID_RE = indic_word_re(
    r"i said|already said|also said|i mentioned|i told you|"
    r"ਕਿਹਾ|ਬੋਲਿਆ|ਬੋਲੀ|ਬੋਲੇ"
)


def mentions_already_said(text: str) -> bool:
    """Caller is referencing something they say they ALREADY told the agent
    (e.g. "I also said dal makhani", "ਦਾਲਮਖਨੀ ਵੀ ਕਿਹਾ ਮੈਂ") — a correction
    naming ONE missed item, not a request to redo the whole order. Live-call
    regression (PR 052): the LLM re-called add_to_order for an item already
    in the cart while also (correctly) adding the missed one, doubling it —
    "two Palak Paneer" appeared when the caller only ever asked for one.
    Deliberately a separate, narrower check from _I_SAID_RE (used for hard
    intent classification elsewhere) so broadening it here can't affect
    detect_intent()'s ADD_ITEM/pickup-STT paths."""
    t = (text or "").strip()
    if not t:
        return False
    return bool(_ALREADY_SAID_RE.search(t))


_CORRECTION_CUE_RE = re.compile(
    r"(?:"
    r"\bnot\s+(?:one|two|three|four|five|six|seven|eight|nine|ten|\d+)\b|"
    r"\bi\s+said\b|\bi\s+meant\b|\bi\s+didn'?t\s+say\b|"
    r"\bmake\s+(?:it|that)\b|\bchange\s+(?:it|that)?\s*to\b|"
    r"\bshould\s+be\b|\bnot\s+that\s+many\b|"
    r"ਕਿਹਾ\s*ਸੀ|ਗਲਤ|ਬਦਲ|ਨਹੀਂ\s*ਕਿਹਾ|"
    r"कहा\s*था|ग़लत|गलत|बदल"
    r")",
    re.I,
)


def is_quantity_correction(text: str) -> bool:
    """Caller is CORRECTING a quantity already in the order (e.g. 'I said one,
    not two', 'make it three'), not adding more. This must route to
    update_item_quantity (exact set), never the additive add_to_order — which
    would compound the very mistake the caller is fixing. Code detects the
    correction intent; the LLM/tool own the exact number (language → state)."""
    t = (text or "").strip()
    if not t:
        return False
    return bool(_CORRECTION_CUE_RE.search(t))


def looks_like_order_phrasing(text: str) -> bool:
    """True when the utterance contains a recognized add/order verb (English
    or Punjabi/Hindi) — the single source of truth for "does this sound like
    a genuine order" so other modules (e.g. stt_noise's noise heuristic) don't
    maintain their own narrower, drifting keyword list."""
    t = (text or "").strip()
    if not t:
        return False
    return bool(_ADD_RE.search(t))


_META_QUESTION_RE = re.compile(
    r"\?|^\s*(?:why|what|did you|do you understand|are you|should you|you should not)\b",
    re.I,
)


def is_allergies_step_answer(text: str, intent: UserIntent) -> bool:
    """Caller answered the allergies / special-instructions question."""
    if intent in (UserIntent.CONFIRM_NO, UserIntent.PICKUP, UserIntent.DELIVERY):
        return True
    t = (text or "").lower()
    if _ALLERGY_NO_RE.search(text):
        return True
    # Live-call regression (PR 048): "allerg" appearing ANYWHERE used to count
    # as answered — including a caller complaining "why are you asking for
    # allergies?", which is a question about the process, not an answer.
    # _META_QUESTION_RE excludes question-shaped pushback so only an actual
    # allergy mention (e.g. "peanut allergy") still counts.
    if ("allerg" in t or "ਐਲਰਜੀ" in text) and not _META_QUESTION_RE.search(text):
        return True
    if intent == UserIntent.CONFIRM_YES and ("instruction" in t or "special" in t):
        return True
    # Modifier-style special note during allergies step:
    # "ਤੰਦੂਰੀ ਰੋਟੀ ਤੇ ਅਜਵਾਇਨ ਐਡ ਕਰ ਦੇਣਾ"
    if (
        intent == UserIntent.ADD_ITEM
        and menu_item_hint_in_text(text)
        and not _QTY_ITEM_RE.search(text)
    ):
        return True
    if intent == UserIntent.CONFIRM_NO:
        return True
    if intent == UserIntent.GENERAL and (is_confirm_no(text) or _ALLERGY_NO_RE.search(text)):
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


def format_update_tool_reply(quantity: int, voice_line: str) -> str:
    """Correction confirm — distinct from add so it never reads as a second add."""
    word = _qty_word(quantity)
    confirm = f"Got it — {word} {voice_line}, fixed."
    return (
        "INTERNAL: quantity corrected (not added).\n"
        f'SAY EXACTLY: "{confirm}"\n'
        "Do NOT mention price, cart, or menu."
    )


def _cart_items_str(cart: OrderCart) -> str:
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


def format_order_status(cart: OrderCart, *, include_price: bool = True) -> str:
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


def format_order_readback(cart: OrderCart, *, include_price: bool = True) -> str:
    """Exact spoken read-back line for final confirmation (Step E)."""
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
    r"about \d+(?:\.\d+)?\s*dollars?|"
    r"(?:,\s*)?(?:\u0a15\u0a41\u0a71?\s*)?(?:total|\u0a15\u0a41\u0a71?|\u0a24\u0a15\u0a30\u0a40\u0a2c(?:\u0a28)?)"
    r"[^.?!]*(?:dollars?|\u0a21\u0a3e\u0a32\u0a30)|"
    r"[\d.]+\s*(?:\u0a21\u0a3e\u0a32\u0a30|dollars?)"
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
