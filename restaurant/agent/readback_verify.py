"""PR 078 — post-speech readback verifier (money path, pure, LLM-free).

The LLM phrases the readback naturally in the customer's language; this module
checks the SPOKEN text (captured via note_agent_speech while readback_pending)
actually contained every item, its quantity, and the order type before
confirm_readback may succeed. Anything unverifiable across languages that
cannot corrupt money (inflection, honorifics, notes/spice, phrasing order) is
deliberately NOT checked — false negatives fail safe toward a re-read.

READBACK_VERIFY env: "warn" (default — log + analytics, allow), "strict"
(refuse confirmation), "off" (emergency rollback).
"""

from __future__ import annotations

import os
import re
import unicodedata
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from restaurant.orders import OrderCart


def readback_verify_mode() -> str:
    """'warn' (default) | 'strict' | 'off' via the READBACK_VERIFY env var."""
    mode = (os.getenv("READBACK_VERIFY") or "").strip().lower()
    return mode if mode in ("strict", "off") else "warn"


# ── trilingual quantity lexicon 1–20 (matches core._MAX_ITEM_QTY) ────────────

_EN_WORDS = (
    "one two three four five six seven eight nine ten eleven twelve thirteen "
    "fourteen fifteen sixteen seventeen eighteen nineteen twenty"
).split()

_PA_WORDS = (
    "ਇੱਕ ਦੋ ਤਿੰਨ ਚਾਰ ਪੰਜ ਛੇ ਸੱਤ ਅੱਠ ਨੌਂ ਦਸ ਗਿਆਰਾਂ ਬਾਰਾਂ ਤੇਰਾਂ ਚੌਦਾਂ ਪੰਦਰਾਂ "
    "ਸੋਲਾਂ ਸਤਾਰਾਂ ਅਠਾਰਾਂ ਉੱਨੀ ਵੀਹ"
).split()

_HI_WORDS = (
    "एक दो तीन चार पांच छह सात आठ नौ दस ग्यारह बारह तेरह चौदह पंद्रह "
    "सोलह सत्रह अठारह उन्नीस बीस"
).split()

# Common alternate spellings STT/LLM output produces.
_ALT_WORDS = {
    "ਇਕ": 1,   # ਇੱਕ without addak
    "ਨੌ": 9,   # ਨੌਂ without bindi
    "पाँच": 5,  # chandrabindu variant
    "छे": 6,
    "पंद्राह": 15,
}

_GURMUKHI_DIGITS = "੦੧੨੩੪੫੬੭੮੯"
_DEVANAGARI_DIGITS = "०१२३४५६७८९"


def _digit_forms(n: int) -> list[str]:
    ascii_s = str(n)
    return [
        ascii_s,
        "".join(_GURMUKHI_DIGITS[int(c)] for c in ascii_s),
        "".join(_DEVANAGARI_DIGITS[int(c)] for c in ascii_s),
    ]


def _build_qty_lexicon() -> dict[str, int]:
    lex: dict[str, int] = {}
    for words in (_EN_WORDS, _PA_WORDS, _HI_WORDS):
        for i, w in enumerate(words, start=1):
            lex[_norm_token(w)] = i
    for w, n in _ALT_WORDS.items():
        lex[_norm_token(w)] = n
    for n in range(1, 21):
        for form in _digit_forms(n):
            lex[form] = n
    return lex


# ── normalization ────────────────────────────────────────────────────────────


def _norm_token(token: str) -> str:
    return unicodedata.normalize("NFC", token).casefold()


def normalize_tokens(text: str) -> list[str]:
    """NFC → casefold → strip punctuation preserving Indic codepoints → tokens."""
    text = unicodedata.normalize("NFC", text or "").casefold()
    # Anything not alphanumeric (any script) becomes a separator — keeps
    # Gurmukhi/Devanagari letters and numerals, drops dashes/quotes/commas.
    # Indic matras/diacritics are combining marks (Mn/Mc), not isalnum(),
    # but splitting on them would shred ਚਿਕਨ into pieces — keep them.
    cleaned = "".join(
        ch if ch.isalnum() or unicodedata.category(ch) in ("Mn", "Mc") else " "
        for ch in text
    )
    return cleaned.split()


_QTY_LEXICON = _build_qty_lexicon()

_PAREN_RE = re.compile(r"\([^)]*\)")

# Closed checkout vocab — English first (the checkout-English prompt rule),
# plus the exact phonetic Gurmukhi/Devanagari transliterations gpt-4.1-mini
# actually produces mid-Punjabi/Hindi ("ਪਿਕਅਪ", "पिकअप"): the customer heard
# the order type, so failing those would be a pure false negative. Still a
# closed list — never fuzzy matching. "pick up" normalizes to two tokens.
_ORDER_TYPE_VOCAB: dict[str, tuple[tuple[str, ...], ...]] = {
    "pickup": (
        ("pickup",),
        ("pick", "up"),
        ("ਪਿਕਅਪ",),
        ("ਪਿੱਕਅਪ",),
        ("पिकअप",),
    ),
    "delivery": (
        ("delivery",),
        ("deliver",),
        ("delivered",),
        ("ਡਿਲੀਵਰੀ",),
        ("ਡਿਲਿਵਰੀ",),
        ("डिलीवरी",),
        ("डिलिवरी",),
    ),
}

_DOLLARS_RE = re.compile(
    r"(?:\$\s*(\d+(?:\.\d{1,2})?))|(?:\b(\d+(?:\.\d{1,2})?)\s*dollars?\b)",
    re.I,
)

# How many tokens before an item alias may carry its quantity.
_QTY_WINDOW = 3


@dataclass
class ReadbackCheck:
    problems: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.problems


def _item_aliases(name: str, voice_line: str) -> list[list[str]]:
    """Normalized token sequences that count as 'the item was spoken'."""
    aliases: list[list[str]] = []
    for raw in (voice_line, name):
        if not raw:
            continue
        tokens = normalize_tokens(_PAREN_RE.sub(" ", raw))
        if tokens and tokens not in aliases:
            aliases.append(tokens)
    return aliases


def _find_occurrences(tokens: list[str], alias: list[str]) -> list[int]:
    """Start indices where alias appears as a contiguous token run."""
    n, m = len(tokens), len(alias)
    return [i for i in range(n - m + 1) if tokens[i : i + m] == alias]


def _qty_before(tokens: list[str], start: int) -> int | None:
    """Nearest quantity token within the window before an alias occurrence."""
    for i in range(start - 1, max(start - 1 - _QTY_WINDOW, -1), -1):
        qty = _QTY_LEXICON.get(tokens[i])
        if qty is not None:
            return qty
    return None


def _check_item(tokens: list[str], name: str, voice_line: str, quantity: int) -> str | None:
    """None if the item passes, else the problem description."""
    label = voice_line or name
    aliases = _item_aliases(name, voice_line)
    occurrences = [
        (alias, start)
        for alias in aliases
        for start in _find_occurrences(tokens, alias)
    ]
    if not occurrences:
        return f"you never said '{label}'"

    found_qtys: list[int] = []
    for _alias, start in occurrences:
        qty = _qty_before(tokens, start)
        if qty == quantity:
            return None
        if qty is not None:
            found_qtys.append(qty)
    if found_qtys:
        return (
            f"'{label}' quantity is wrong — you said {found_qtys[0]}, "
            f"the order has {quantity}"
        )
    if quantity >= 2:
        return f"you never said the quantity for '{label}' — the order has {quantity}"
    # Quantity 1 with no number spoken is fine ("and a Garlic Naan").
    return None


def _check_order_type(tokens: list[str], order_type: str) -> str | None:
    sequences = _ORDER_TYPE_VOCAB.get(order_type)
    if not sequences:  # unknown type — nothing verifiable
        return None
    for seq in sequences:
        if _find_occurrences(tokens, list(seq)):
            return None
    return f"you never said the order type '{order_type}' (say it in English)"


def _check_total(spoken: str, total: float) -> str | None:
    """Warn-level: a spoken numeric dollar amount must equal the cart total."""
    for m in _DOLLARS_RE.finditer(unicodedata.normalize("NFC", spoken)):
        amount = float(m.group(1) or m.group(2))
        if abs(amount - total) > 0.005:
            return (
                f"you said ${amount:.2f} but the order total is ${total:.2f}"
            )
    return None


def verify_readback(
    spoken: str, cart: "OrderCart", *, check_total: bool = False
) -> ReadbackCheck:
    """Verify the captured spoken readback covers every item/qty/order-type.

    `spoken` is the joined readback_spoken buffer. Problems block confirmation
    in strict mode; warnings (total mismatch, web only) never block.
    """
    check = ReadbackCheck()
    tokens = normalize_tokens(spoken)

    for item in cart.items:
        problem = _check_item(tokens, item.name, item.voice_line, item.quantity)
        if problem:
            check.problems.append(problem)

    if cart.order_type:
        problem = _check_order_type(tokens, cart.order_type)
        if problem:
            check.problems.append(problem)

    if check_total:
        warning = _check_total(spoken, cart.total)
        if warning:
            check.warnings.append(warning)

    return check
