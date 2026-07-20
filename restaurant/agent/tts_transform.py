"""TTS-path phone-digit enforcement (PR 079, Step 6).

First-time HARD guarantee for the English-phone-digits rule: the filter sits in
RestaurantAgent.tts_node, so whatever the LLM wrote, the TTS engine only ever
hears the stored customer phone as English word digits. The old
sanitize_assistant_speech guard was log-only and is deleted in this PR.

Design: normal text streams through untouched. Only an *open digit-ish tail*
(ASCII/Indic digit runs, spoken digit words in en/pa/hi, or a trailing partial
token that could still grow into a digit word) is held back until its run
boundary arrives — bounded buffering, no latency on normal speech. Emitted
segments that contain digit-ish tokens are rewritten with
customer_info.enforce_english_phone_in_speech.
"""

from __future__ import annotations

import os
import re
from typing import AsyncIterable, AsyncIterator, Callable

from restaurant.customer_info import (
    _DOUBLE_TRIPLE_WORDS,
    _SPOKEN_DIGIT_WORDS,
    enforce_english_phone_in_speech,
)


def tts_phone_enforce_enabled() -> bool:
    """`TTS_PHONE_ENFORCE` env — default ON; `0`/`false`/`off` is the rollback."""
    raw = (os.getenv("TTS_PHONE_ENFORCE") or "").strip().lower()
    return raw not in ("0", "false", "off")


# Word fixups salvaged from the deleted sanitizer — only the trivially reliable
# whole-word Roman→Gurmukhi case (TTS misreads Roman "Dhanyavaad"); NO general
# transliteration.
_DHANYAVAAD_RE = re.compile(r"\bdhanyavaad\b", re.I)

_TOKEN_PUNCT = ".,:;!?—-()\"'"

_DIGIT_WORD_KEYS = frozenset(_SPOKEN_DIGIT_WORDS) | frozenset(_DOUBLE_TRIPLE_WORDS)

# Force-flush ceiling — a full spoken phone chain is <100 chars; anything this
# long is not a phone readback still in progress.
_MAX_HOLD = 600


def _is_digitish_token(tok: str) -> bool:
    """Token is (part of) a possible phone rendition: contains a digit in any
    script, or is a spoken digit word / double-triple prefix."""
    key = tok.lower().strip(_TOKEN_PUNCT)
    if not key:
        return False
    if key in _DIGIT_WORD_KEYS:
        return True
    return any(c.isdigit() for c in tok)


def _could_grow_digitish(partial: str) -> bool:
    """A trailing partial token that might complete into a digit word next
    chunk (e.g. "sev" + "en") — hold it so the run is never split."""
    key = partial.lower().strip(_TOKEN_PUNCT)
    if not key:
        return False
    return any(word.startswith(key) for word in _DIGIT_WORD_KEYS)


class PhoneSpeechFilter:
    """Incremental text filter — pure sync feed/flush so it unit-tests without
    livekit. `get_phone` is called at emit time, so enforcement picks up the
    stored number the moment set_customer_contact saves it."""

    def __init__(self, get_phone: Callable[[], str | None]):
        self._get_phone = get_phone
        self._buf = ""

    def feed(self, chunk: str) -> str:
        self._buf += chunk
        emit, hold = self._split_emit_hold(self._buf)
        if len(hold) > _MAX_HOLD:
            emit, hold = self._buf, ""
        self._buf = hold
        return self._transform(emit)

    def flush(self) -> str:
        out = self._transform(self._buf)
        self._buf = ""
        return out

    @staticmethod
    def _split_emit_hold(buf: str) -> tuple[str, str]:
        """Split into (safe to emit now, open digit-ish tail to keep)."""
        tokens = re.split(r"(\s+)", buf)
        i = len(tokens)
        hold_has_digit = False

        # Trailing partial token (no whitespace after it yet) — hold only if
        # it is or could still become digit-ish.
        last = tokens[-1] if tokens else ""
        if last and not last[-1].isspace():
            if _is_digitish_token(last) or _could_grow_digitish(last):
                i -= 1
                hold_has_digit = True
            else:
                # Complete-word region ends before this partial; emitting the
                # partial is fine (downstream concatenates the stream anyway).
                return buf, ""

        while i > 0:
            tok = tokens[i - 1]
            if not tok or tok.isspace():
                i -= 1
            elif _is_digitish_token(tok):
                i -= 1
                hold_has_digit = True
            else:
                break

        if not hold_has_digit:
            return buf, ""
        return "".join(tokens[:i]), "".join(tokens[i:])

    def _transform(self, text: str) -> str:
        if not text:
            return text
        out = _DHANYAVAAD_RE.sub("ਧੰਨਵਾਦ", text)
        if any(_is_digitish_token(tok) for tok in out.split()):
            phone = self._get_phone()
            if phone:
                out = enforce_english_phone_in_speech(out, phone)
        return out


async def phone_enforced_stream(
    text: AsyncIterable[str],
    get_phone: Callable[[], str | None],
) -> AsyncIterator[str]:
    """Wrap a tts_node text stream with phone-digit enforcement."""
    filt = PhoneSpeechFilter(get_phone)
    async for chunk in text:
        out = filt.feed(chunk)
        if out:
            yield out
    tail = filt.flush()
    if tail:
        yield tail
