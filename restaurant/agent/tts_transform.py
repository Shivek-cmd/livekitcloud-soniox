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


def tts_dish_english_enforce_enabled() -> bool:
    """`TTS_DISH_ENGLISH_ENFORCE` env — default ON; `0`/`false`/`off` rollback."""
    raw = (os.getenv("TTS_DISH_ENGLISH_ENFORCE") or "").strip().lower()
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


# --- PR 085 (Gap 5): English dish-name backstop ------------------------------

from restaurant.clover.match import normalize as _match_normalize  # noqa: E402

_GURMUKHI_CHAR_RE = re.compile(r"[਀-੿]")
# A maximal run of Gurmukhi tokens (with internal whitespace) — surrounding
# whitespace/text is left untouched by re.sub so spacing is preserved exactly.
_GURMUKHI_RUN_RE = re.compile(r"[਀-੿]+(?:\s+[਀-੿]+)*")


def _has_gurmukhi_tok(tok: str) -> bool:
    return bool(_GURMUKHI_CHAR_RE.search(tok))


class DishNameFilter:
    """Incremental filter that rewrites any Gurmukhi rendition of an
    english-mode dish back to its English voice_line (e.g. ਲੈਮ ਬਿਰਿਆਨੀ → Lamb
    Biryani). Same pure sync feed/flush shape as PhoneSpeechFilter so it
    unit-tests without livekit. `get_map` is called at emit time so the map is
    picked up once the menu cache is loaded.

    Only an *open trailing Gurmukhi run* is held back (a dish name can grow
    across chunk boundaries), and even that hold is bounded to the trailing
    key-sized window: earlier tokens of the run whose greedy-match decision is
    already final stream out immediately, so a pure-Punjabi reply is not
    buffered whole. Deliberate gurmukhi-mode dishes are absent from the map,
    so they pass through unchanged."""

    def __init__(self, get_map: Callable[[], dict[str, str]]):
        self._get_map = get_map
        self._buf = ""

    def feed(self, chunk: str) -> str:
        self._buf += chunk
        emit, hold = self._split_emit_hold(self._buf)
        if hold:
            committed, hold = self._commit_prefix(hold)
            emit += committed
        if len(hold) > _MAX_HOLD:
            emit, hold = emit + hold, ""
        self._buf = hold
        return self._transform(emit)

    def flush(self) -> str:
        out = self._transform(self._buf)
        self._buf = ""
        return out

    @staticmethod
    def _split_emit_hold(buf: str) -> tuple[str, str]:
        """Split into (safe to emit now, open trailing Gurmukhi run to keep)."""
        tokens = re.split(r"(\s+)", buf)
        i = len(tokens)
        hold_has_gurmukhi = False

        last = tokens[-1] if tokens else ""
        if last and not last[-1].isspace():
            if _has_gurmukhi_tok(last):
                i -= 1
                hold_has_gurmukhi = True
            else:
                # Trailing complete non-Gurmukhi token — any run before it is
                # already boundary-terminated, so everything is safe to emit.
                return buf, ""

        while i > 0:
            tok = tokens[i - 1]
            if not tok or tok.isspace():
                i -= 1
            elif _has_gurmukhi_tok(tok):
                i -= 1
                hold_has_gurmukhi = True
            else:
                break

        if not hold_has_gurmukhi:
            return buf, ""
        return "".join(tokens[:i]), "".join(tokens[i:])

    def _commit_prefix(self, hold: str) -> tuple[str, str]:
        """Bound the hold: split into (already-final prefix, trailing window).

        Rewrites happen per Gurmukhi run (`_GURMUKHI_RUN_RE`), so only the
        run that reaches the buffer's open end can still be changed by future
        chunks — every earlier run is boundary-terminated and final. Inside
        the open run, `_rewrite_run`'s greedy walk at token k only ever looks
        at windows of ≤ max-key-length tokens, so once that whole window lies
        within the tokens already complete, the decision at k is final and the
        token can be emitted. Net effect: the hold never exceeds ~one dish
        name (plus a partial token), instead of a whole Punjabi sentence."""
        mapping = self._get_map()
        maxlen = max((len(k.split()) for k in mapping), default=1)

        runs = list(_GURMUKHI_RUN_RE.finditer(hold))
        if not runs:
            return hold, ""
        last = runs[-1]
        if hold[last.end():].strip():
            # Last run is closed by trailing non-Gurmukhi text (punctuation);
            # nothing in the hold can be extended by future chunks.
            return hold, ""

        toks = last.group(0).split()
        # The final token is still open (may grow) unless whitespace follows it.
        complete = len(toks) if last.end() < len(hold) else len(toks) - 1

        k = 0
        while k + maxlen <= complete:
            step = 1
            for end in range(min(k + maxlen, complete), k, -1):
                if _match_normalize(" ".join(toks[k:end])) in mapping:
                    step = end - k
                    break
            k += step
        if k == 0:
            return hold[: last.start()], hold[last.start() :]
        if k >= len(toks):
            return hold, ""
        tok_starts = [m.start() for m in re.finditer(r"\S+", last.group(0))]
        split_at = last.start() + tok_starts[k]
        return hold[:split_at], hold[split_at:]

    def _transform(self, text: str) -> str:
        if not text:
            return text
        mapping = self._get_map()
        if not mapping:
            return text
        return _GURMUKHI_RUN_RE.sub(lambda m: self._rewrite_run(m.group(0), mapping), text)

    @staticmethod
    def _rewrite_run(run: str, mapping: dict[str, str]) -> str:
        """Greedy longest-match over a Gurmukhi token run; unmatched tokens
        (e.g. deliberate gurmukhi-mode dishes) pass through."""
        toks = run.split()
        out: list[str] = []
        k = 0
        while k < len(toks):
            hit: str | None = None
            for end in range(len(toks), k, -1):
                key = _match_normalize(" ".join(toks[k:end]))
                if key in mapping:
                    hit = mapping[key]
                    k = end
                    break
            if hit is not None:
                out.append(hit)
            else:
                out.append(toks[k])
                k += 1
        return " ".join(out)


async def dish_english_enforced_stream(
    text: AsyncIterable[str],
    get_map: Callable[[], dict[str, str]],
) -> AsyncIterator[str]:
    """Wrap a tts_node text stream with the English dish-name backstop."""
    filt = DishNameFilter(get_map)
    async for chunk in text:
        out = filt.feed(chunk)
        if out:
            yield out
    tail = filt.flush()
    if tail:
        yield tail


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
