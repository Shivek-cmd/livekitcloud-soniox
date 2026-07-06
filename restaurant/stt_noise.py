"""STT noise detection and standalone quantity parsing (PR 044)."""

from __future__ import annotations

import re

from restaurant.conversation import looks_like_order_phrasing
from restaurant.order_parse import _QTY_WORDS, _extract_qty

# TV / YouTube / side-conversation fragments common in phone STT.
_STT_NOISE_RE = re.compile(
    r"(?:"
    r"subscription|subscribe|subscrib|"
    r"beginner|बिगिनर|बिग्नर|सब्सक्रिप्शन|सबस्क्रिप्शन|"
    r"breaking news|please subscribe|like and subscribe|"
    r"connection\s*\?|कनेक्शन|"
    r"thank you for watching|bell icon"
    r")",
    re.I,
)

# Roman Punjabi / STT variants for standalone quantity answers.
_STANDALONE_QTY_EXTRA: dict[str, int] = {
    "van": 1,
    "wan": 1,
    "won": 1,
    "one": 1,
    "two": 2,
    "three": 3,
    "a": 1,
    "an": 1,
    "ਵਨ": 1,
    "ਵਾਨ": 1,
}

_QTY_TOKENS = {**_QTY_WORDS, **_STANDALONE_QTY_EXTRA}


def parse_standalone_quantity(text: str) -> int | None:
    """Parse a short quantity-only reply (one, van, ਇੱਕ, 2)."""
    raw = (text or "").strip()
    raw = re.sub(r"[.,!?;:\u0964]+", "", raw).strip()
    if not raw or len(raw) > 24:
        return None
    cleaned = re.sub(r"\s+", " ", raw.lower())
    if cleaned.isdigit():
        n = int(cleaned)
        return n if 1 <= n <= 10 else None
    token = cleaned.rstrip(".")
    if token in _QTY_TOKENS:
        return _QTY_TOKENS[token]
    # Gurmukhi/Devanagari single token
    for word, qty in _QTY_WORDS.items():
        if token == word.lower():
            return qty
    return None


def utterance_has_explicit_quantity(text: str) -> bool:
    """True when the caller already said how many in this utterance."""
    raw = (text or "").strip()
    if not raw:
        return False
    if parse_standalone_quantity(raw) is not None and len(raw) <= 16:
        return True
    qty, rest = _extract_qty(raw)
    if qty > 1:
        return True
    # qty=1 default from _extract_qty when no token — require a visible qty word
    return bool(
        re.search(
            r"(?:^|\s)(?:one|two|three|four|five|six|seven|eight|nine|ten|"
            r"a|an|\d+|"
            r"ਇੱਕ|ਐਕ|ਦੋ|ਤਿੰਨ|"
            r"van|wan|won|"
            r"वन|एक|दो|तीन)(?:\s|$|[.,!?])",
            raw,
            re.I,
        )
    )


def is_likely_stt_noise(text: str) -> bool:
    """True when transcript looks like background media, not the caller ordering."""
    raw = (text or "").strip()
    if not raw:
        return True
    if _STT_NOISE_RE.search(raw):
        return True
    # Long mixed-script ramble with no order verb — often TV + partial echo.
    # Live-call regression (PR 049): the old inline keyword check
    # (chahid|chaah|order|add|menu|allergy-style narrow list) didn't recognize
    # "kar dio" (do it/make it) — an extremely common, completely normal
    # Punjabi way to place an order — so genuine multi-item orders in natural
    # code-mixed speech were silently discarded as noise. Now reuses the same,
    # more complete add/order-verb detection conversation.py already uses.
    if len(raw) > 40:
        scripts = sum(
            1
            for pat in (
                r"[\u0A00-\u0A7F]",
                r"[\u0900-\u097F]",
                r"[A-Za-z]",
            )
            if re.search(pat, raw)
        )
        if scripts >= 2 and not looks_like_order_phrasing(raw):
            return True
    return False


def agent_recently_asked_quantity(recent_agent_lines: list[str]) -> bool:
    for line in recent_agent_lines[-4:]:
        lower = line.lower()
        if "how many" in lower or "one or two" in lower:
            return True
    return False
