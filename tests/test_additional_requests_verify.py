"""PR 095 — the spoken additional-requests question verifier."""

import pytest

from restaurant.agent.additional_requests_verify import (
    additional_requests_verify_mode,
    asks_additional_requests,
)


@pytest.mark.parametrize(
    "line",
    [
        "Any allergies or special instructions?",
        "Before we go on — do you have any allergies I should tell the kitchen about?",
        "Anything special for the kitchen, any dietary restrictions?",
        "Koi allergy ਜਾਂ special request?",
        "ਕੋਈ ਐਲਰਜੀ ਜਾਂ ਖਾਸ ਹਿਦਾਇਤ?",
        "क्या कोई एलर्जी या खास निर्देश हैं?",
        # Not phrased as a question, but the subject was still raised out loud.
        "Let me know about any allergies before I read your order back.",
    ],
)
def test_recognises_the_question(line):
    assert asks_additional_requests(line)


@pytest.mark.parametrize(
    "line",
    [
        # The per-item prompt is NOT this question — asking it dozens of times
        # must never clear the allergies gate.
        "Anything else for you?",
        "Anything else I can get you today?",
        "ਹੋਰ ਕੁਝ ਚਾਹੀਦਾ ਹੈ ਜੀ?",
        # Request vocabulary in a plain acknowledgement, not a question.
        "Sure, I have noted your request.",
        "Your dietary note is on the order.",
        "ਤੁਹਾਡੀ ਖਾਸ ਹਿਦਾਇਤ ਲਿਖ ਲਈ ਹੈ।",
        "ਹਾਂ ਜੀ, ਹੋਰ ਕੁਝ?",
        "That's two Garlic Naan and one Butter Chicken, medium.",
        "Is this for pickup or delivery?",
        "Can I get your name please?",
        "",
    ],
)
def test_ignores_unrelated_speech(line):
    assert not asks_additional_requests(line)


def test_mode_defaults_to_strict(monkeypatch):
    monkeypatch.delenv("ADDITIONAL_REQUESTS_VERIFY", raising=False)
    assert additional_requests_verify_mode() == "strict"
    monkeypatch.setenv("ADDITIONAL_REQUESTS_VERIFY", "WARN")
    assert additional_requests_verify_mode() == "warn"
    monkeypatch.setenv("ADDITIONAL_REQUESTS_VERIFY", "off")
    assert additional_requests_verify_mode() == "off"
    monkeypatch.setenv("ADDITIONAL_REQUESTS_VERIFY", "nonsense")
    assert additional_requests_verify_mode() == "strict"
