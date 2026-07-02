"""Tests for multi-item order parsing and cashier confirmations."""

from restaurant.conversation import (
    CustomerLanguage,
    confirm_items_added,
    format_add_tool_reply,
)
from restaurant.order_parse import can_auto_add_lines, parse_order_lines
from restaurant.orders import OrderCart


def test_parse_two_items_with_and():
    lines = parse_order_lines("can you please add one gulab jamun and 1 kheer")
    assert len(lines) == 2
    names = {line.item["name"] for line in lines}
    assert "Gulab Jamun" in names
    assert "Kheer" in names
    assert all(line.quantity == 1 for line in lines)


def test_parse_merged_stt_segment():
    lines = parse_order_lines("add one rasmalai gulabjabuyn and 1 kheer")
    assert len(lines) == 2
    assert lines[1].item["name"] == "Kheer"
    assert lines[0].quantity == 1


def test_can_auto_add_simple_desserts():
    lines = parse_order_lines("one gulab jamun and one kheer")
    assert can_auto_add_lines(lines) is True


def test_live_web_turn2_punjabi_multi_auto_add():
    """Web transcript turn 2 — spring roll + sarson in one sentence."""
    text = (
        "ਹਾਂ ਜੀ, ਆਪਣੇ ਇੱਕ ਵੈਜ ਸਪ੍ਰਿੰਗ ਰੋਲ ਕਰ ਦਿਓ, "
        "ਤੇ ਆਪਣੇ ਇੱਕ ਸਰਸੋਂ ਦਾ ਸਾਗ ਕਰ ਦਿਓ।"
    )
    lines = parse_order_lines(text)
    assert len(lines) == 2
    names = {line.item["name"] for line in lines}
    assert "Veg Spring Rolls (6 pcs)" in names
    assert "Sarson da Saag" in names
    assert can_auto_add_lines(lines) is True


def test_clean_segment_strips_kar_dio():
    lines = parse_order_lines("ਆਪਣੇ ਇੱਕ ਵੈਜ ਸਪ੍ਰਿੰਗ ਰੋਲ ਕਰ ਦਿਓ")
    assert len(lines) == 1
    assert lines[0].item["name"] == "Veg Spring Rolls (6 pcs)"


def test_confirm_two_items_english():
    line = confirm_items_added(
        [(1, "Rasmalai"), (1, "Kheer")],
        CustomerLanguage.ENGLISH,
    )
    assert line == "Yes — one Rasmalai and one Kheer."


def test_confirm_two_items_punjabi():
    line = confirm_items_added(
        [(1, "ਰਸਮਲਾਈ"), (1, "ਖੀਰ")],
        CustomerLanguage.PUNJABI,
    )
    assert "ਠੀਕ ਹੈ" in line
    assert "ਰਸਮਲਾਈ" in line
    assert "ਖੀਰ" in line


def test_format_add_tool_reply_no_cart_language():
    reply = format_add_tool_reply([(1, "Kheer")])
    assert "SAY EXACTLY" in reply
    assert "cart" not in reply.lower()
    assert "Yes — one Kheer." in reply


def test_parse_two_items_punjabi_danda():
    text = "1 ਦਾਲ ਮੱਖਣੀ ਕਰ ਦਿਓ। 2 ਸਰਸੋਂ ਦਾ ਸਾਗ ਕਰ ਦਿਓ।"
    lines = parse_order_lines(text)
    assert len(lines) == 2
    names = {line.item["name"] for line in lines}
    assert "Dal Makhani" in names
    assert "Sarson da Saag" in names
    assert lines[0].quantity == 1
    assert lines[1].quantity == 2


def test_cart_add_uses_concise_reply():
    cart = OrderCart()
    reply = cart.add_item(
        {"name": "Kheer", "voice_line": "ਖੀਰ", "price": 6},
        1,
    )
    assert "SAY EXACTLY" in reply
    assert "cart" not in reply.lower()
