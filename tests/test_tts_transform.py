"""Tests for restaurant.agent.tts_transform — PR 079 streaming phone-digit
enforcement in the TTS path (first-time hard guarantee for English phone
digits; replaces the deleted log-only sanitize_assistant_speech guard)."""

import asyncio

import pytest

from restaurant.agent.tts_transform import (
    PhoneSpeechFilter,
    phone_enforced_stream,
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
