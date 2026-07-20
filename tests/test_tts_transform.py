"""Tests for restaurant.agent.tts_transform — PR 079 streaming phone-digit
enforcement in the TTS path (first-time hard guarantee for English phone
digits; replaces the deleted log-only sanitize_assistant_speech guard)."""

import asyncio

import pytest

from restaurant.agent.tts_transform import (
    DishNameFilter,
    PhoneSpeechFilter,
    dish_english_enforced_stream,
    phone_enforced_stream,
    tts_dish_english_enforce_enabled,
    tts_phone_enforce_enabled,
)

_PHONE = "9413752688"
_ENGLISH = "nine, four, one, three, seven, five, two, six, eight, eight"


def _run(chunks: list[str], phone: str | None = _PHONE) -> str:
    filt = PhoneSpeechFilter(lambda: phone)
    out = "".join(filt.feed(c) for c in chunks)
    return out + filt.flush()


def test_normal_text_passes_through_unchanged():
    chunks = ["Sure thing — ", "two Butter Chicken ", "coming right up!"]
    assert _run(chunks) == "".join(chunks)


def test_normal_text_not_buffered():
    # No digit-ish content → each feed emits everything so far (no latency).
    filt = PhoneSpeechFilter(lambda: _PHONE)
    assert filt.feed("Sure thing, ") == "Sure thing, "
    assert filt.feed("anything else?") == "anything else?"
    assert filt.flush() == ""


def test_word_digit_chain_split_across_chunks():
    out = _run(["Your number is nine four one ", "three seven five two six eight eight, correct?"])
    assert out.startswith("Your number is")
    assert _ENGLISH in out
    assert "correct?" in out


def test_ascii_digit_run_split_across_chunks():
    out = _run(["I have 94137 ", "52688 for you."])
    assert _ENGLISH in out
    assert "94137" not in out
    assert "for you." in out


def test_indic_numerals_rewritten():
    out = _run(["ਤੁਹਾਡਾ ਨੰਬਰ ੯੪੧੩੭ ੫੨੬੮੮ ਹੈ ਜੀ।"])
    assert _ENGLISH in out
    assert "੯" not in out


def test_partial_digit_word_across_chunk_boundary():
    # "sev" could still become "seven" — must be held, never split mid-run.
    out = _run(["nine four one three sev", "en five two six eight eight done"])
    assert _ENGLISH in out
    assert "done" in out


def test_quantity_words_untouched():
    text = "two Butter Chicken and three Garlic Naan added."
    assert _run([text]) == text


def test_no_phone_stored_passes_through():
    text = "nine four one three seven five two six eight eight"
    assert _run([text], phone=None) == text


def test_dhanyavaad_fixup():
    assert _run(["Dhanyavaad ji, see you soon!"]) == "ਧੰਨਵਾਦ ji, see you soon!"


def test_bounded_buffering_force_flush():
    # A digit-ish stream longer than the hold ceiling must not buffer forever.
    filt = PhoneSpeechFilter(lambda: _PHONE)
    emitted = ""
    for _ in range(100):
        emitted += filt.feed("nine 1 two 2 three 3 four 4 ")
    assert emitted  # force-flushed before flush()


def test_env_flag_default_on(monkeypatch):
    monkeypatch.delenv("TTS_PHONE_ENFORCE", raising=False)
    assert tts_phone_enforce_enabled()
    for off in ("0", "false", "off"):
        monkeypatch.setenv("TTS_PHONE_ENFORCE", off)
        assert not tts_phone_enforce_enabled()
    monkeypatch.setenv("TTS_PHONE_ENFORCE", "1")
    assert tts_phone_enforce_enabled()


def test_async_stream_wrapper():
    async def _source():
        yield "Your number is nine four one "
        yield "three seven five two six eight eight, correct?"

    async def _collect() -> str:
        return "".join(
            [c async for c in phone_enforced_stream(_source(), lambda: _PHONE)]
        )

    out = asyncio.run(_collect())
    assert _ENGLISH in out
    assert "correct?" in out


# ---------------------------------------------------------------------------
# PR 085 (Gap 5): DishNameFilter — English dish-name backstop
#
# Map keys are normalized Gurmukhi speak_as token-sequences of english-mode
# items; deliberate gurmukhi-mode dishes (ਸਮੋਸਾ ਚਾਟ) are ABSENT so they pass
# through untouched.
_DISH_MAP = {
    "ਲੈਮ ਬਿਰਿਆਨੀ": "Lamb Biryani",
    "ਚਿਕਨ ਬਿਰਿਆਨੀ": "Chicken Biryani",
    "ਬਟਰ ਚਿਕਨ": "Butter Chicken",
    "ਤੰਦੂਰੀ ਲੈਮ ਚਾਪ": "Tandoori Lamb Chops",
}


def _dish_run(chunks: list[str], mapping=_DISH_MAP) -> str:
    filt = DishNameFilter(lambda: mapping)
    out = "".join(filt.feed(c) for c in chunks)
    return out + filt.flush()


def test_dish_rewrite_chunked_live_repro():
    # The live bug in miniature: a dish name split across chunk boundaries.
    out = _dish_run(["…and ਲੈਮ ਬਿਰਿ", "ਆਨੀ as tasty…"])
    assert out == "…and Lamb Biryani as tasty…"


def test_dish_gurmukhi_mode_item_untouched_in_same_stream():
    # ਸਮੋਸਾ ਚਾਟ is not in the map → passes through; the english-mode dish next
    # to it is still rewritten.
    out = _dish_run(["ਦੋ ਸਮੋਸਾ ਚਾਟ ਤੇ ਇੱਕ ਲੈਮ ਬਿਰਿਆਨੀ"])
    assert out == "ਦੋ ਸਮੋਸਾ ਚਾਟ ਤੇ ਇੱਕ Lamb Biryani"


def test_dish_flush_tail_rewrite():
    # Run sits at the very end of the stream — only flush() emits it.
    filt = DishNameFilter(lambda: _DISH_MAP)
    assert filt.feed("Sure, one ") == "Sure, one "
    assert filt.feed("ਬਟਰ ਚਿਕਨ") == ""  # open trailing run held
    assert filt.flush() == "Butter Chicken"


def test_dish_multi_token_longest_match():
    # "ਤੰਦੂਰੀ ਲੈਮ ਚਾਪ" must match the 3-token entry, not stop at a shorter one.
    out = _dish_run(["one ਤੰਦੂਰੀ ਲੈਮ ਚਾਪ please"])
    assert out == "one Tandoori Lamb Chops please"


def test_dish_normal_english_passes_through():
    chunks = ["Sure thing — ", "two Butter Chicken ", "coming right up!"]
    assert _dish_run(chunks) == "".join(chunks)


def test_dish_empty_map_noop():
    out = _dish_run(["one ਲੈਮ ਬਿਰਿਆਨੀ please"], mapping={})
    assert out == "one ਲੈਮ ਬਿਰਿਆਨੀ please"


def test_dish_normal_text_not_buffered():
    filt = DishNameFilter(lambda: _DISH_MAP)
    assert filt.feed("Sure thing, ") == "Sure thing, "
    assert filt.feed("anything else?") == "anything else?"
    assert filt.flush() == ""


def test_dish_pure_punjabi_streams_incrementally():
    # Bounded hold: a pure-Punjabi reply must NOT be buffered whole — earlier
    # tokens of the open run stream out as soon as their greedy decision is
    # final (map keys are ≤ 3 tokens), so TTS can start before the LLM finishes.
    filt = DishNameFilter(lambda: _DISH_MAP)
    words = "ਹਾਂ ਜੀ ਬਿਲਕੁਲ ਮੈਂ ਤੁਹਾਡਾ ਆਰਡਰ ਲਿਖ ਲਿਆ ਹੈ ਜੀ".split()
    fed_out = "".join(filt.feed(w + " ") for w in words)
    assert fed_out  # something emitted before flush
    assert fed_out + filt.flush() == " ".join(words) + " "


def test_dish_rewrite_survives_bounded_hold():
    # Dish name deep inside a long Punjabi sentence, split across chunks —
    # eager emission of earlier tokens must not break the rewrite.
    out = _dish_run(["ਹਾਂ ਜੀ ਮੈਂ ਇੱਕ ", "ਲੈਮ ਬਿਰਿ", "ਆਨੀ ਲਿਖ ਲਈ ਹੈ ਜੀ"])
    assert out == "ਹਾਂ ਜੀ ਮੈਂ ਇੱਕ Lamb Biryani ਲਿਖ ਲਈ ਹੈ ਜੀ"


def test_dish_punctuation_closes_run_before_flush():
    # A run terminated by punctuation is final — it must be emitted (rewritten)
    # from feed, not sit in the hold until flush.
    filt = DishNameFilter(lambda: _DISH_MAP)
    out = filt.feed("ਲੈਮ ਬਿਰਿਆਨੀ, ਠੀਕ?")
    assert out == "Lamb Biryani, ਠੀਕ?"
    assert filt.flush() == ""


def test_dish_env_flag_default_on(monkeypatch):
    monkeypatch.delenv("TTS_DISH_ENGLISH_ENFORCE", raising=False)
    assert tts_dish_english_enforce_enabled()
    for off in ("0", "false", "off"):
        monkeypatch.setenv("TTS_DISH_ENGLISH_ENFORCE", off)
        assert not tts_dish_english_enforce_enabled()
    monkeypatch.setenv("TTS_DISH_ENGLISH_ENFORCE", "1")
    assert tts_dish_english_enforce_enabled()


def test_dish_then_phone_chain():
    # tts_node chains dish filter FIRST, then phone enforcement. One stream with
    # both a Gurmukhi dish name and spoken digits must come out correct on both.
    async def _source():
        yield "So one ਲੈਮ ਬਿਰਿਆਨੀ and your number nine four one "
        yield "three seven five two six eight eight, right?"

    async def _collect() -> str:
        chained = dish_english_enforced_stream(_source(), lambda: _DISH_MAP)
        chained = phone_enforced_stream(chained, lambda: _PHONE)
        return "".join([c async for c in chained])

    out = asyncio.run(_collect())
    assert "Lamb Biryani" in out
    assert "ਲੈਮ ਬਿਰਿਆਨੀ" not in out
    assert _ENGLISH in out


def test_dish_async_stream_wrapper():
    async def _source():
        yield "one ਲੈਮ ਬਿਰਿ"
        yield "ਆਨੀ please"

    async def _collect() -> str:
        return "".join(
            [c async for c in dish_english_enforced_stream(_source(), lambda: _DISH_MAP)]
        )

    assert asyncio.run(_collect()) == "one Lamb Biryani please"
