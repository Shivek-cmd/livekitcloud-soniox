"""Drop phone turns that look like background chatter, not the caller ordering."""

from __future__ import annotations

import re

from restaurant.clover.match import phonetic_key
from restaurant.channels.phone_echo import _ORDER_SIGNAL_RE, should_bypass_phone_echo_filter
from restaurant.channels.stt_noise import is_likely_stt_noise, parse_standalone_quantity

# Short replies that are valid even when intent stays GENERAL.
_SHORT_MEANINGFUL: frozenset[str] = frozenset(
    {
        "yes",
        "yeah",
        "yep",
        "no",
        "nope",
        "ok",
        "okay",
        "pickup",
        "delivery",
        "haan",
        "han",
        "ji",
        "na",
        "hello",
        "hi",
        "hey",
        "stop",
        "wait",
        "human",
        "person",
        "operator",
        "menu",
        "one",
        "two",
        "three",
        "four",
        "five",
        "van",
        "wan",
        # Live-call regression (PR 053): "ਨਹੀਂ" phonetic-folds to "nhn", which
        # only "nahin" (not the shorter "na" already above) also folds to —
        # so a caller's plain "no" answer, when transcribed as the fuller
        # ਨਹੀਂ/nahin spelling, had no matching allowlist entry and was
        # misread as an unrecognized (non-meaningful) token.
        "nahin",
    }
)

# Filler/hesitation sounds — ignored rather than counted as "not meaningful,"
# so "ਅਹ, ਨਹੀਂ" (um, no) isn't dragged down to background just because the
# hesitation marker itself isn't a real answer (PR 053 live-call regression:
# this exact phrase, answering the allergies question, was dropped as
# background — the caller had to say "hello" to get Sierra's attention back).
_FILLER_TOKENS: frozenset[str] = frozenset({"ah", "um", "uh", "erm", "hmm", "ਅਹ", "ਉਹ"})

# Phonetic keys for the Latin allowlist — matches Gurmukhi/Devanagari equivalents.
_SHORT_MEANINGFUL_KEYS: frozenset[str] = frozenset(
    phonetic_key(w) for w in _SHORT_MEANINGFUL if phonetic_key(w)
)


def _token_is_meaningful(token: str) -> bool:
    if token in _SHORT_MEANINGFUL:
        return True
    key = phonetic_key(token)
    return bool(key) and key in _SHORT_MEANINGFUL_KEYS


def _drop_fillers(tokens: list[str]) -> list[str]:
    stripped = [t for t in tokens if t not in _FILLER_TOKENS]
    return stripped or tokens


# Common background / side-conversation fragments (not order-related).
_BACKGROUND_FRAGMENT_RE = re.compile(
    r"\b("
    r"thank you|thanks|welcome|please subscribe|breaking news|"
    r"la la|na na|oh oh|mm hmm|uh huh|"
    r"shh|quiet|listen"
    r")\b",
    re.I,
)


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().strip())


def _tokens(text: str) -> list[str]:
    # Do not use [^\w\s] — Gurmukhi/Devanagari matras are not \w and would
    # split words like ਹੈਲੋ into meaningless single-letter tokens.
    cleaned = re.sub(r"[.,!?;:\"]+", " ", _normalize(text))
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return [t for t in cleaned.split() if t]


# Every word capitalized (this STT pipeline's convention for a recognized
# name/item, e.g. "Blue Lagoon", "Palak Paneer") — a plausible answer naming
# something (a dish, drink, place), not background chatter. Live-call
# regression (PR 053): a caller answering "which mocktail?" with "Blue
# Lagoon." was dropped as background purely because neither word is in the
# generic short-reply allowlist — which can never scale to cover every
# possible dish/drink name a caller might say. Deliberately limited to short
# (<=3 word) phrases so it can't swallow long, genuinely-capitalized TV
# dialogue; checked AFTER _BACKGROUND_FRAGMENT_RE so known junk phrases
# ("Thank You") are still caught regardless of case.
_TITLE_CASE_RE = re.compile(r"^(?:[A-Z][a-zA-Z']*\.?\s*){1,3}$")


def _looks_like_named_answer(raw_text: str) -> bool:
    return bool(_TITLE_CASE_RE.match(raw_text.strip()))


def is_likely_background_speech(
    user_text: str,
    intent: str | None,
    *,
    enabled: bool = True,
    phase: str | None = None,
) -> bool:
    """True when STT text is probably background TV / nearby speaker, not the customer.

    `intent` is the plain intent value ("general", "add_item", …) or None
    (None is treated like an unclassified turn).
    """
    if not enabled:
        return False

    text = user_text.strip()
    if not text:
        return True

    # Never drop short replies during checkout contact capture.
    if phase in ("customer_name", "customer_phone", "readback"):
        return False

    # Quantity answers while collecting (one, van, ਇੱਕ).
    if phase in ("awaiting_more", "collecting_items", "browsing"):
        if parse_standalone_quantity(text) is not None:
            return False

    if should_bypass_phone_echo_filter(text, intent):
        return False

    if intent not in ("general", "unclear", None):
        return False

    if _ORDER_SIGNAL_RE.search(text):
        return False

    # PR 073 — meaningful-token rescue runs before `_BACKGROUND_FRAGMENT_RE`
    # so a real short reply like "No, thanks." ("no" is meaningful) isn't
    # swallowed by the TV-chatter fragment regex matching "thanks".
    tokens = _drop_fillers(_tokens(text))
    if len(tokens) <= 3 and any(_token_is_meaningful(t) for t in tokens):
        return False

    if _BACKGROUND_FRAGMENT_RE.search(text):
        return True

    if is_likely_stt_noise(text) and intent in ("general", "unclear", None):
        return True

    if _looks_like_named_answer(text):
        return False

    if not tokens:
        return True

    # Very short side speech with no order/menu signal and no meaningful
    # token (the rescue above already returned False otherwise).
    if len(tokens) <= 2:
        return True

    return False
