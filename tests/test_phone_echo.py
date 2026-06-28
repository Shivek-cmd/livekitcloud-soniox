"""Tests for phone echo filter (Tier B-1)."""

from restaurant.conversation import UserIntent, detect_intent
from restaurant.phone_echo import is_likely_phone_echo, should_bypass_phone_echo_filter


def test_pickup_answer_not_echo():
    agent_lines = [
        "No problem! Are you looking for a pickup or delivery order?",
    ]
    user = "Yeah, I'm looking for pickup."
    intent = detect_intent(user)
    assert intent == UserIntent.PICKUP
    assert should_bypass_phone_echo_filter(user, intent)
    assert not is_likely_phone_echo(user, agent_lines, intent=intent)


def test_order_with_dish_names_not_echo():
    agent_lines = [
        "ਹਾਂ ਜੀ, ਸਾਡੇ ਕੋਲ ਪਾਲਕ ਪਨੀਰ ਅਤੇ ਪਨੀਰ ਬਟਰ ਮਸਾਲਾ ਹੈ — ਕਿਹੜਾ ਚਾਹੀਦਾ ਹੈ?",
    ]
    user = "ਹਾਂ, ਆਪਣੇ 1 ਪਨੀਰ ਬਟਰ ਮਸਾਲਾ ਕਰ ਦਿਓ, ਤੇ 2 ਮੈਂਗੋ ਸ਼ੇਕ ਕਰ ਦਿਓ, ਠੀਕ ਹੈ?"
    intent = detect_intent(user)
    assert intent == UserIntent.ADD_ITEM
    assert not is_likely_phone_echo(user, agent_lines, intent=intent)


def test_greeting_tail_still_echo():
    user = "how can i help you today"
    assert is_likely_phone_echo(user, [], intent=UserIntent.GENERAL)


def test_exact_agent_repeat_is_echo():
    line = "Are you looking for a pickup or delivery order?"
    assert is_likely_phone_echo(line, [line], intent=UserIntent.GENERAL)


def test_qty_item_intent():
    assert detect_intent("One paneer tikka, and two mango shake.") == UserIntent.ADD_ITEM
    assert detect_intent("ਮੈਂ ਕਿਹਾ 1 ਪਨੀਰ ਟਿੱਕਾ, ਤੇ 2 ਮੈਂਗੋ ਸ਼ੇਕ।") == UserIntent.ADD_ITEM


def test_allergy_no_mixed():
    assert detect_intent("ਨਹੀਂ ਨਹੀਂ ਜੀ, not not at all.") == UserIntent.CONFIRM_NO
