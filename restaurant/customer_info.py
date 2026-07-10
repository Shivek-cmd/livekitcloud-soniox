"""Parse and format customer name / phone from STT (PR 037)."""

from __future__ import annotations

import re

# 10-digit local, optional +1 / +91 country prefix.
_PHONEISH = re.compile(r"^[\d\s\-\+\(\)\.]+$")

# Gurmukhi / Devanagari numerals → ASCII (Sierra must never speak these for phone).
_INDIC_NUMERAL_MAP = str.maketrans(
    {
        **{c: str(i) for i, c in enumerate("੦੧੨੩੪੫੬੭੮੯")},
        **{c: str(i) for i, c in enumerate("०१२३४५६७८९")},
    }
)

# Spoken number words Sierra sometimes wrongly uses for phone readback.
_SPOKEN_DIGIT_WORDS: dict[str, str] = {
    "zero": "0",
    "oh": "0",
    "o": "0",
    "one": "1",
    "two": "2",
    "three": "3",
    "four": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "nine": "9",
    "saat": "7",
    "aath": "8",
    "nau": "9",
    "char": "4",
    "chaar": "4",
    "ek": "1",
    "do": "2",
    "teen": "3",
    "paanch": "5",
    "chhe": "6",
    "ਸਿਫ਼ਰ": "0",
    "ਸਫ਼ਰ": "0",
    "ਇੱਕ": "1",
    "ਐਕ": "1",
    "ਦੋ": "2",
    "ਤਿੰਨ": "3",
    "ਚਾਰ": "4",
    "ਪੰਜ": "5",
    "ਛੇ": "6",
    "ਸੱਤ": "7",
    "ਅੱਠ": "8",
    "ਨੌ": "9",
    "एक": "1",
    "दो": "2",
    "तीन": "3",
    "चार": "4",
    "पांच": "5",
    "छह": "6",
    "सात": "7",
    "आठ": "8",
    "नौ": "9",
    "शून्य": "0",
}


def extract_phone_digits(text: str) -> str | None:
    """Return 10-digit phone or None."""
    raw = (text or "").strip()
    if not raw:
        return None
    normalized = raw.translate(_INDIC_NUMERAL_MAP)
    digits = re.sub(r"\D", "", normalized)
    if len(digits) == 10:
        return digits
    if len(digits) == 11 and digits.startswith("1"):
        return digits[1:]
    if len(digits) == 12 and digits.startswith("91"):
        return digits[2:]
    return None


def looks_like_phone_utterance(text: str) -> bool:
    """True when STT is mostly a phone number (not a menu order)."""
    raw = (text or "").strip()
    if not raw:
        return False
    if extract_phone_digits(raw):
        return True
    return bool(_PHONEISH.match(raw) and sum(c.isdigit() for c in raw.translate(_INDIC_NUMERAL_MAP)) >= 7)


_DIGIT_ENGLISH = (
    "zero",
    "one",
    "two",
    "three",
    "four",
    "five",
    "six",
    "seven",
    "eight",
    "nine",
)


def format_phone_spoken(digits: str) -> str:
    """English word digits for TTS — Indic voices misread ASCII numerals as Hindi/Punjabi."""
    clean = re.sub(r"\D", "", digits or "")
    if not clean:
        return ""
    return ", ".join(_DIGIT_ENGLISH[int(d)] for d in clean)


def enforce_english_phone_in_speech(text: str, phone_digits: str | None) -> str:
    """Rewrite phone readback to English digits if LLM used Indic numerals or words."""
    if not text or not phone_digits:
        return text

    english = format_phone_spoken(phone_digits)
    out = text.translate(_INDIC_NUMERAL_MAP)

    grouped = f"{phone_digits[:5]} {phone_digits[5:]}"
    for old in (phone_digits, grouped, grouped.replace(" ", "-")):
        if old in out:
            out = out.replace(old, english)

    # Collapse spoken-word digit chains (e.g. "nine four one three seven") when long enough.
    tokens = re.split(r"(\s+)", out)
    rebuilt: list[str] = []
    digit_run: list[str] = []
    for tok in tokens:
        key = tok.lower().strip(".,")
        if key in _SPOKEN_DIGIT_WORDS:
            digit_run.append(_SPOKEN_DIGIT_WORDS[key])
            continue
        if digit_run:
            run = "".join(digit_run)
            if len(run) >= 7:
                out = english
                return out
            digit_run.clear()
        rebuilt.append(tok)
    if digit_run:
        run = "".join(digit_run)
        if len(run) >= 7 and run == phone_digits:
            return re.sub(re.escape(run), english, out, count=1)

    # Any 7+ digit ASCII run that matches stored phone → canonical English form.
    for match in re.finditer(r"\d[\d\s\-]{6,}\d", out):
        chunk = re.sub(r"\D", "", match.group(0))
        if chunk == phone_digits:
            out = out[: match.start()] + english + out[match.end() :]
            break

    return out


_NAME_FILLER_RE = re.compile(
    r"^(?:"
    r"my name is|i am|i'm|im|"
    r"naam|name|"
    r"haan|han|ji|ਜੀ|yes|yeah|"
    r"ah|um|uh|erm|"
    r"ਅਹ|ਉਹ|"
    r"this is"
    r")\s*,?\s*",
    re.I,
)

_NAME_PATTERNS = (
    re.compile(
        r"(?:naam|name|\u0a28\u0a3e\u0a02)\s+"
        r"(?:mera|my|\u0a2e\u0a47\u0a30\u0a3e)\s+"
        r"([\u0900-\u097F\u0A00-\u0A7F\u0A01-\u0A4Da-zA-Z]+)",
        re.I,
    ),
    re.compile(
        r"(?:mera|my|\u0a2e\u0a47\u0a30\u0a3e)\s+"
        r"(?:naam|name|\u0a28\u0a3e\u0a02)\s+"
        r"(?:hai\s+|\u0a39\u0a48\s+)?"
        r"([\u0900-\u097F\u0A00-\u0A7F\u0A01-\u0A4Da-zA-Z]+)",
        re.I,
    ),
)


from restaurant.text_match import indic_word_re, word_bounded

# Private copies of the pickup/delivery/qty-item patterns (formerly lazy
# imports from conversation.py — severed in PR 060 so that module can be
# deleted at cutover).
_PICKUP_RE = indic_word_re(
    r"pickup|pick up|pick-up|takeaway|take away|"
    r"ਪਿਕਅੱਪ|ਪਿਕ ਅੱਪ|ਪਿਕ.*ਕਰ|pick.*up"
)

_DELIVERY_RE = indic_word_re(
    r"delivery|deliver|home delivery|ਡਿਲਿਵਰੀ|ਘਰ.*ਡਿਲਿਵਰ"
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


def _menu_item_hint_in_text(text: str) -> bool:
    """Utterance names a likely menu item (same check conversation.py used)."""
    from restaurant import menu_provider

    return menu_provider.resolve_item_in_text(text) is not None


# Checkout / intent words — never valid customer names (e.g. STT "ਪਿਕਅੱਪ" alone).
_BLOCKED_NAME_RE = indic_word_re(
    r"pickup|pick up|pick-up|pickup|takeaway|take away|"
    r"delivery|deliver|"
    r"ਪਿਕਅੱਪ|ਪਿਕ ਅੱਪ|ਡਿਲਿਵਰੀ|"
    r"डिलिवरी|डिलीवरी|"
    r"all good|allgood|"
    r"^(?:yes|no|ok|okay|haan|han|ji|ਜੀ|nahi|nahin|ਨਹੀਂ|हाँ)$"
)


def is_valid_customer_name(name: str) -> bool:
    """False for pickup/delivery and other checkout tokens misheard as names."""
    n = (name or "").strip()
    if len(n) < 2 or re.search(r"\d", n):
        return False
    if _BLOCKED_NAME_RE.search(n):
        # Allow longer strings that merely mention pickup in a sentence — not for names.
        if len(n.split()) == 1:
            return False
    if len(n.split()) == 1:
        if _PICKUP_RE.search(n) or _DELIVERY_RE.search(n):
            return False
    return True


def _clean_name_token(token: str) -> str | None:
    name = (token or "").strip(" ,.-")
    if not name or not is_valid_customer_name(name):
        return None
    if _QTY_ITEM_RE.search(name) or _menu_item_hint_in_text(name):
        return None
    return name


def parse_customer_name(text: str) -> str | None:
    """Best-effort name from a short utterance — keep STT spelling exactly."""
    raw = (text or "").strip()
    if not raw or looks_like_phone_utterance(raw):
        return None
    if len(raw) > 64:
        return None

    for pattern in _NAME_PATTERNS:
        match = pattern.search(raw)
        if match:
            parsed = _clean_name_token(match.group(1))
            if parsed:
                return parsed

    if extract_phone_digits(raw) and not re.search(
        r"[\u0900-\u097F\u0A00-\u0A7F]", raw
    ):
        return None

    cleaned = _NAME_FILLER_RE.sub("", raw).strip(" ,.")
    cleaned = re.sub(
        r"(?:\s+(?:hai|ha|ਹੈ|haan|han))[\s\.।,!?]*$",
        "",
        cleaned,
        flags=re.I,
    ).strip(" ,.")
    if not cleaned or looks_like_phone_utterance(cleaned):
        return None
    words = cleaned.split()
    if len(words) > 4 or len(cleaned) < 2:
        return None
    if re.search(r"\d", cleaned):
        return None
    if _QTY_ITEM_RE.search(cleaned) or _menu_item_hint_in_text(cleaned):
        return None
    if len(words) == 2:
        pair = " ".join(words)
        if is_valid_customer_name(pair):
            return pair
    if len(words) == 1:
        return _clean_name_token(words[0])
    if len(words) == 3:
        pair = " ".join(words[-2:])
        if is_valid_customer_name(pair):
            return pair
    if len(words) <= 3:
        candidate = _clean_name_token(words[-1])
        if candidate:
            return candidate
    return None
