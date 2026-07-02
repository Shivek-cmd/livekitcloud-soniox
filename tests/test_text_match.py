"""PR 034 — Indic-safe word boundaries, intent matrix, live-transcript regression."""

from __future__ import annotations

import re

from restaurant.conversation import UserIntent, detect_intent, resolve_intent
from restaurant.order_parse import _extract_qty
from restaurant.phone_background import is_likely_background_speech
from restaurant.text_match import indic_word_re, word_bounded


# ── Boundary unit tests ───────────────────────────────────────────────────────


def test_word_bounded_matches_gurmukhi_no_at_word_end():
    pat = indic_word_re(r"ਨਹੀਂ|ਨਹੀ")
    assert pat.search("ਨਹੀਂ ਨਹੀਂ,")
    assert pat.search("ਕੋਈ ਨਹੀਂ")
    assert not pat.search("xyzਨਹੀਂ")


def test_word_bounded_rejects_mid_word_gurmukhi():
    # ਲੈ must not match inside a longer token when used as a standalone stem guard.
    pat = indic_word_re(r"ਲੈ")
    assert pat.search("ਲੈ ਜਾਓ")
    assert not pat.search("ਮਿਲੈਗਾ")


def test_word_bounded_allows_stem_continuation():
    add = indic_word_re(r"ਕਰ ਦ")
    assert add.search("ਕਰ ਦਿਓ")
    avail = indic_word_re(r"ਮਿਲੇਗ")
    assert avail.search("ਮਿਲੇਗਾ")
    want = indic_word_re(r"ਚਾਹੀ(?:ਦਾ|ਦੀ|ਦੇ)")
    assert want.search("ਚਾਹੀਦਾ")


def test_word_bounded_plain_regex_still_works_for_latin():
    pat = re.compile(word_bounded(r"hello|hi"), re.I)
    assert pat.search("hello there")
    assert not pat.search("shellow")


# ── Three-script intent matrix ────────────────────────────────────────────────


def test_confirm_no_en_pa_hi():
    assert detect_intent("no") == UserIntent.CONFIRM_NO
    assert detect_intent("nahin") == UserIntent.CONFIRM_NO
    assert detect_intent("ਨਹੀਂ") == UserIntent.CONFIRM_NO
    assert detect_intent("नहीं") == UserIntent.CONFIRM_NO


def test_confirm_yes_en_pa_hi():
    assert detect_intent("yes") == UserIntent.CONFIRM_YES
    assert detect_intent("haan ji") == UserIntent.CONFIRM_YES
    assert detect_intent("ਹਾਂ") == UserIntent.CONFIRM_YES
    assert detect_intent("ठीक") == UserIntent.CONFIRM_YES


def test_order_done_en_pa_hi():
    assert detect_intent("that's all") == UserIntent.ORDER_DONE
    assert detect_intent("bas") == UserIntent.ORDER_DONE
    assert detect_intent("ਬਸ") == UserIntent.ORDER_DONE
    assert detect_intent("हो गया") == UserIntent.ORDER_DONE


def test_delivery_and_human_pa():
    assert detect_intent("ਡਿਲਿਵਰੀ") == UserIntent.DELIVERY
    assert detect_intent("ਬੰਦਾ") == UserIntent.HUMAN


def test_qty_two_gurmukhi():
    qty, _rest = _extract_qty("ਦੋ ਸਮੋਸੇ")
    assert qty == 2


# ── Live-transcript regression (2026-07-02 allergies stuck) ───────────────────


def test_allergies_nahi_nahi_not_general():
    text = "ਨਹੀਂ ਨਹੀਂ,"
    assert resolve_intent(text) == UserIntent.CONFIRM_NO


def test_allergies_nahi_nahi_not_background_filtered():
    text = "ਨਹੀਂ ਨਹੀਂ,"
    intent = resolve_intent(text)
    assert intent == UserIntent.CONFIRM_NO
    assert not is_likely_background_speech(text, intent)


def test_hello_gurmukhi_not_background():
    text = "ਹੈਲੋ,"
    intent = resolve_intent(text)
    assert not is_likely_background_speech(text, intent)


def test_true_background_still_filtered():
    assert is_likely_background_speech("mm hmm", UserIntent.GENERAL)
    assert is_likely_background_speech("thank you", UserIntent.GENERAL)
    assert is_likely_background_speech("la la", UserIntent.GENERAL)
