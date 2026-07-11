"""PR 034 — Indic-safe word boundaries.

The intent matrix that used to live here died with conversation.py at the
hybrid cutover (PR 062); quantity-word coverage lives in test_stt_noise.
"""

from __future__ import annotations

import re

from restaurant.text_match import indic_word_re, word_bounded


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
