"""PR 035 — respectful Punjabi/Hindi register guard."""

from restaurant.conversation import sanitize_assistant_speech
from restaurant.respect_speech import INFORMAL_REGISTER_MARKERS, apply_respectful_register

# Live transcript (2026-07-02) — informal LLM lines
_TURN3 = "\u0a24\u0a42\u0a02 \u0a15\u0a3f\u0a39\u0a21\u0a40 \u0a2e\u0a38\u0a3e\u0a32\u0a47 \u0a26\u0a40 \u0a2a\u0a38\u0a02\u0a26 \u0a15\u0a30\u0a47\u0a17\u0a06?"
_TURN11 = "\u0a39\u0a41\u0a23 \u0a24\u0a47\u0a30\u0a3e \u0a06\u0a30\u0a21\u0a30 \u0a2a\u0a21\u0a2c \u0a15\u0a47 \u0a26\u0a38\u0a26\u0a40 \u0a39\u0a3e\u0a02\u0964"
_FORMAL = "\u0a24\u0a41\u0a38\u0a40\u0a02 \u0a15\u0a3f\u0a39\u0a21\u0a40 \u0a38\u0a2a\u0a3e\u0a07\u0a38 \u0a32\u0a47\u0a35\u0a32 \u0a1a\u0a3e\u0a39\u0a4b\u0a17\u0a47?"
_GOODBYE = "\u0a24\u0a41\u0a39\u0a3e\u0a21\u0a3e \u0a06\u0a30\u0a21\u0a30 \u0a2e\u0a3f\u0a32 \u0a17\u0a3f\u0a06 \u0a1c\u0a40\u0964"


def test_turn3_informal_spice_question():
    out = apply_respectful_register(_TURN3)
    assert "\u0a24\u0a42\u0a02" not in out
    assert "\u0a24\u0a41\u0a38\u0a40\u0a02" in out
    assert "\u0a15\u0a30\u0a4b\u0a17\u0a47" in out
    assert "\u0a15\u0a30\u0a47\u0a17\u0a06" not in out


def test_turn11_informal_possessive():
    out = apply_respectful_register(_TURN11)
    assert "\u0a24\u0a47\u0a30\u0a3e" not in out
    assert "\u0a24\u0a41\u0a39\u0a3e\u0a21\u0a3e" in out


def test_formal_line_unchanged():
    assert apply_respectful_register(_FORMAL) == _FORMAL


def test_goodbye_template_unchanged():
    assert apply_respectful_register(_GOODBYE) == _GOODBYE


def test_hindi_informal_pronoun():
    raw = "\u0924\u0942 \u0915\u094d\u092f\u093e \u091a\u093e\u0939\u094b\u0917\u0947?"
    out = apply_respectful_register(raw)
    assert "\u0924\u0942" not in out
    assert "\u0906\u092a" in out


def test_sanitize_applies_register_guard():
    raw = _TURN3
    out = sanitize_assistant_speech(raw, allow_greeting=False)
    assert "\u0a24\u0a42\u0a02" not in out
    assert "\u0a24\u0a41\u0a38\u0a40\u0a02" in out


def test_informal_markers_cover_live_bug_words():
    assert "\u0a24\u0a42\u0a02" in INFORMAL_REGISTER_MARKERS
    assert "\u0a24\u0a47\u0a30\u0a3e" in INFORMAL_REGISTER_MARKERS
    assert "\u0924\u0942" in INFORMAL_REGISTER_MARKERS
