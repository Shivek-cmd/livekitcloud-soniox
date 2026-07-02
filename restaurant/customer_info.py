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


def format_phone_spoken(digits: str) -> str:
    """English ASCII digits, space-separated — never Punjabi/Hindi number words."""
    clean = re.sub(r"\D", "", digits or "")
    if not clean:
        return ""
    return " ".join(clean)


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
    r"this is"
    r")\s+",
    re.I,
)


def parse_customer_name(text: str) -> str | None:
    """Best-effort name from a short utterance — keep STT spelling exactly."""
    raw = (text or "").strip()
    if not raw or looks_like_phone_utterance(raw):
        return None
    if len(raw) > 48:
        return None
    cleaned = _NAME_FILLER_RE.sub("", raw).strip(" ,.")
    if not cleaned or looks_like_phone_utterance(cleaned):
        return None
    words = cleaned.split()
    if len(words) > 3 or len(cleaned) < 2:
        return None
    if re.search(r"\d", cleaned):
        return None
    from restaurant.conversation import _QTY_ITEM_RE, menu_item_hint_in_text

    if _QTY_ITEM_RE.search(cleaned) or menu_item_hint_in_text(cleaned):
        return None
    return cleaned
