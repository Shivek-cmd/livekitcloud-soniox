"""Tests for phone echo filter (Tier B-1).

Post-cutover the filters take a plain intent string (or None — the hybrid
agent's hygiene hook passes None; intent regexes died with conversation.py).
"""

from restaurant.channels.phone_echo import (
    is_likely_phone_echo,
    is_recovery_phrase_echo,
    should_bypass_phone_echo_filter,
)


def test_pickup_answer_not_echo():
    agent_lines = [
        "No problem! Are you looking for a pickup or delivery order?",
    ]
    user = "Yeah, I'm looking for pickup."
    assert should_bypass_phone_echo_filter(user, "pickup")
    assert not is_likely_phone_echo(user, agent_lines, intent="pickup")


def test_order_with_dish_names_not_echo():
    agent_lines = [
        "ਹਾਂ ਜੀ, ਸਾਡੇ ਕੋਲ ਪਾਲਕ ਪਨੀਰ ਅਤੇ ਪਨੀਰ ਬਟਰ ਮਸਾਲਾ ਹੈ — ਕਿਹੜਾ ਚਾਹੀਦਾ ਹੈ?",
    ]
    user = "ਹਾਂ, ਆਪਣੇ 1 ਪਨੀਰ ਬਟਰ ਮਸਾਲਾ ਕਰ ਦਿਓ, ਤੇ 2 ਮੈਂਗੋ ਸ਼ੇਕ ਕਰ ਦਿਓ, ਠੀਕ ਹੈ?"
    assert not is_likely_phone_echo(user, agent_lines, intent=None)


def test_greeting_tail_still_echo():
    user = "how can i help you today"
    assert is_likely_phone_echo(user, [], intent=None)


def test_exact_agent_repeat_is_echo():
    line = "Are you looking for a pickup or delivery order?"
    assert is_likely_phone_echo(line, [line], intent=None)


def test_order_signal_bypasses_without_intent():
    # The hybrid agent passes intent=None — order phrasing itself must bypass.
    assert should_bypass_phone_echo_filter(
        "One paneer tikka, and two mango shake.", None
    )
    assert should_bypass_phone_echo_filter("ਇੱਕ ਪਨੀਰ ਟਿੱਕਾ ਕਰ ਦਿਓ", None)


def test_recovery_phrase_echo():
    assert is_recovery_phrase_echo("ਹਾਂ ਜੀ, go ahead, I'm listening.")
    assert is_likely_phone_echo(
        "What would you like to know from the—",
        ["What would you like to know from the menu?"],
        intent=None,
    )
