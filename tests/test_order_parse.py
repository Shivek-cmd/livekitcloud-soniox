"""Tests for multi-item order parsing and cashier confirmations."""

from restaurant.conversation import (
    CustomerLanguage,
    confirm_items_added,
    format_add_tool_reply,
)
from restaurant.order_parse import can_auto_add_lines, parse_order_lines
from restaurant.orders import OrderCart


def test_parse_two_items_with_and(clover_menu):
    lines = parse_order_lines("can you please add one gulab jamun and 1 kheer")
    assert len(lines) == 2
    names = {line.item["name"] for line in lines}
    assert any("Gulab Jamun" in n for n in names)
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
    assert 'SAY EXACTLY: "Yes — one Kheer."' in reply


def test_cart_add_uses_concise_reply():
    cart = OrderCart()
    reply = cart.add_item(
        {"name": "Kheer", "voice_line": "ਖੀਰ", "price": 6},
        1,
    )
    assert "SAY EXACTLY" in reply
    assert 'SAY EXACTLY: "Yes — one ਖੀਰ."' in reply
