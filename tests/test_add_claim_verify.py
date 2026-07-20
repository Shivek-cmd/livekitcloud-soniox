"""Tests for restaurant.agent.add_claim_verify (PR 081) — the pure
post-refusal false-add-claim checker. Positive vectors come from the real
2026-07-18 call (room restaurant-797b550c) where add_item refused
"Chana Masala" and Sierra claimed the add anyway."""

from restaurant.agent.add_claim_verify import (
    add_claim_verify_mode,
    falsely_claims_add,
)

_QUERY = "Chana Masala"


# ── positives ────────────────────────────────────────────────────────────────

def test_real_call_false_claim_detected():
    assert falsely_claims_add(
        "Great choice! I've added one Chana Masala for you.", _QUERY
    )


def test_cross_script_gurmukhi_claim_detected():
    assert falsely_claims_add(
        "ਬਹੁਤ ਵਧੀਆ ਜੀ — ਇੱਕ ਚਨਾ ਮਸਾਲਾ ਲਿਖ ਲਈ ਹੈ।", _QUERY
    )


def test_devanagari_claim_detected():
    assert falsely_claims_add("मैंने एक चना मसाला जोड़ दिया है।", _QUERY)


def test_got_it_down_phrasing_detected():
    assert falsely_claims_add("Got one Chana Masala down for you ji!", _QUERY)


# ── negatives — honest refusal / clarify speech must never trip ─────────────

def test_honest_refusal_not_flagged():
    assert not falsely_claims_add(
        "Sorry, Chana Masala isn't on our menu.", _QUERY
    )


def test_contraction_negation_not_flagged():
    assert not falsely_claims_add("I couldn't add that.", _QUERY)


def test_clarify_question_not_flagged():
    assert not falsely_claims_add("Did you mean Chana Chaat?", _QUERY)


def test_unrelated_line_not_flagged():
    assert not falsely_claims_add("Anything else you'd like?", _QUERY)


def test_gurmukhi_refusal_not_flagged():
    assert not falsely_claims_add(
        "ਮਾਫ਼ ਕਰਨਾ ਜੀ, ਚਨਾ ਮਸਾਲਾ ਸਾਡੇ ਮੀਨੂ ਤੇ ਨਹੀਂ ਹੈ।", _QUERY
    )


def test_devanagari_refusal_not_flagged():
    assert not falsely_claims_add("माफ़ कीजिए, चना मसाला नहीं है।", _QUERY)


def test_mention_without_verb_not_flagged():
    assert not falsely_claims_add("Chana Masala, was it?", _QUERY)


def test_verb_without_mention_not_flagged():
    assert not falsely_claims_add("I've added one Garlic Naan for you.", _QUERY)


def test_empty_inputs_not_flagged():
    assert not falsely_claims_add("", _QUERY)
    assert not falsely_claims_add("I've added it.", "")


def test_short_collision_prone_query_abstains():
    # Every token's phonetic key is shorter than 3 — no distinctive token to
    # anchor a mention, so the checker abstains rather than guessing.
    assert not falsely_claims_add("I've added one for you.", "Chai")


# ── env mode parsing ─────────────────────────────────────────────────────────

def test_mode_default_strict(monkeypatch):
    monkeypatch.delenv("ADD_CLAIM_VERIFY", raising=False)
    assert add_claim_verify_mode() == "strict"


def test_mode_warn_off(monkeypatch):
    monkeypatch.setenv("ADD_CLAIM_VERIFY", "warn")
    assert add_claim_verify_mode() == "warn"
    monkeypatch.setenv("ADD_CLAIM_VERIFY", "OFF")
    assert add_claim_verify_mode() == "off"
    monkeypatch.setenv("ADD_CLAIM_VERIFY", "bogus")
    assert add_claim_verify_mode() == "strict"
