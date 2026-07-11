"""Phone background speech filter.

Post-cutover the filter takes a plain intent string (or None — the hybrid
agent's hygiene hook passes None; intent regexes died with conversation.py).
"""

from restaurant.channels.phone_background import is_likely_background_speech


def test_pickup_not_background():
    assert not is_likely_background_speech("Yeah, I'm looking for pickup.", None)


def test_order_not_background():
    assert not is_likely_background_speech(
        "One paneer tikka and two mango shake.", None
    )


def test_short_filler_is_background():
    assert is_likely_background_speech("mm hmm", None)
    assert is_likely_background_speech("thank you", None)


def test_short_meaningful_not_background():
    assert not is_likely_background_speech("pickup", None)
    assert not is_likely_background_speech("haan ji", None)


def test_disabled_never_filters():
    assert not is_likely_background_speech("mm hmm", None, enabled=False)


def test_customer_name_phase_never_filters_single_word():
    assert not is_likely_background_speech(
        "ਸੰਦੀਪ",
        None,
        phase="customer_name",
    )


def test_quantity_van_not_background_while_collecting():
    assert not is_likely_background_speech(
        "ਵਨ।",
        None,
        phase="awaiting_more",
    )


def test_named_answer_not_background():
    # Live-call regression (PR 053): caller answering "which mocktail?" with
    # a proper-noun-style name got dropped as background purely because
    # neither word is in the generic short-reply allowlist.
    assert not is_likely_background_speech("Blue Lagoon.", None, phase="awaiting_more")


def test_filler_prefixed_no_not_background():
    # Live-call regression (PR 053): "ਅਹ, ਨਹੀਂ।" (um, no) answering the
    # allergies question was dropped — the hesitation marker "ਅਹ" dragged
    # down the 2-token all-meaningful check even though "ਨਹੀਂ" is a real
    # answer.
    assert not is_likely_background_speech(
        "ਅਹ, ਨਹੀਂ।", None, phase="special_instructions"
    )


def test_allergies_nahi_nahi_not_background():
    # Live-transcript regression (2026-07-02 allergies stuck).
    assert not is_likely_background_speech("ਨਹੀਂ ਨਹੀਂ,", None)


def test_hello_gurmukhi_not_background():
    assert not is_likely_background_speech("ਹੈਲੋ,", None)


def test_title_case_bypass_does_not_match_long_sentences():
    # The Title-Case bypass itself is capped at 3 words (longer utterances
    # were already not caught by the short-utterance heuristic at all, so
    # this only checks the regex's own scope, not the overall function).
    from restaurant.channels.phone_background import _looks_like_named_answer

    assert not _looks_like_named_answer("Coming Up Next On Channel Five Tonight")
    assert _looks_like_named_answer("Blue Lagoon.")
