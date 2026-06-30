"""Regression tests for PR 030 — strict auto-add, final confirm, menu aliases."""

from restaurant import menu_provider
from restaurant.conversation import UserIntent, format_final_order_confirm
from restaurant.order_flow import OrderFlowController, OrderPhase
from restaurant.order_parse import can_auto_add_lines, parse_order_lines
from restaurant.orders import OrderCart


def test_find_item_strict_blocks_qty_only(clover_menu):
    assert menu_provider.find_item_strict("one") is None
    assert menu_provider.find_item_strict("two") is None
    assert menu_provider.find_item_strict("ਇੱਕ") is None


def test_find_item_fuzzy_blocks_single_qty_token(clover_menu):
    assert menu_provider.find_item("one") is None


def test_shikanji_alias_resolves_nimbu_pani(clover_menu):
    hit = menu_provider.find_item_strict("shikanji")
    assert hit is not None
    assert hit["name"] == "Nimbu Pani"


def test_strict_parse_rejects_fuzzy_segment(clover_menu):
    lines = parse_order_lines("add one gulab jamun and one mystery platter", strict=True)
    assert lines == []


def test_strict_parse_two_clear_items(clover_menu):
    lines = parse_order_lines("one gulab jamun and one kheer", strict=True)
    assert len(lines) == 2
    names = {line.item["name"] for line in lines}
    assert any("Gulab Jamun" in n for n in names)
    assert "Kheer" in names


def test_can_auto_add_requires_segment_parity(clover_menu):
    lines = parse_order_lines("one gulab jamun and one kheer", strict=True)
    assert can_auto_add_lines(lines, "one gulab jamun and one kheer") is True
    assert can_auto_add_lines(lines, "one gulab jamun and one kheer and one lassi") is False


def test_final_confirm_phase_after_name_and_phone():
    flow = OrderFlowController(is_phone=True)
    cart = OrderCart()
    cart.add_item({"name": "Kheer", "voice_line": "Kheer", "price": 6}, 1)
    flow.mark_items_complete()
    flow.mark_special_instructions_done()
    cart.order_type = "pickup"
    flow.mark_readback_confirmed()
    cart.customer_name = "Raj"
    cart.customer_phone = "7805551234"
    flow.sync_from_cart(cart)
    assert flow.state.phase == OrderPhase.FINAL_CONFIRM


def test_final_confirmed_stays_on_final_confirm_phase():
    flow = OrderFlowController(is_phone=True)
    cart = OrderCart()
    cart.add_item({"name": "Kheer", "voice_line": "Kheer", "price": 6}, 1)
    flow.mark_items_complete()
    flow.mark_special_instructions_done()
    cart.order_type = "pickup"
    flow.mark_readback_confirmed()
    cart.customer_name = "Raj"
    cart.customer_phone = "7805551234"
    flow.mark_final_confirmed()
    flow.sync_from_cart(cart)
    assert flow.state.phase == OrderPhase.FINAL_CONFIRM
    assert flow.state.final_confirmed is True


def test_build_turn_plan_place_order_after_final_yes():
    flow = OrderFlowController(is_phone=True)
    cart = OrderCart()
    cart.add_item({"name": "Kheer", "voice_line": "Kheer", "price": 6}, 1)
    flow.mark_items_complete()
    flow.mark_special_instructions_done()
    cart.order_type = "pickup"
    flow.mark_readback_confirmed()
    cart.customer_name = "Raj"
    cart.customer_phone = "7805551234"
    flow.sync_from_cart(cart)

    plan = flow.build_turn_plan("yes please", UserIntent.CONFIRM_YES, cart)
    assert "place_order()" in plan.guidance
    assert flow.state.final_confirmed is True


def test_format_final_order_confirm_includes_name_and_phone():
    cart = OrderCart()
    cart.add_item({"name": "Kheer", "voice_line": "Kheer", "price": 6}, 1)
    cart.order_type = "pickup"
    cart.customer_name = "Raj"
    cart.customer_phone = "7805551234"
    line = format_final_order_confirm(cart, include_price=False)
    assert "Raj" in line
    assert "7805551234" in line
    assert "Shall I place this order?" in line


def test_punjabi_order_verb_stripping_strict(clover_menu):
    lines = parse_order_lines(
        "ਹਾਂ ਜੀ ਆਪਣੀ ਦੋ ਛੋਲੇ ਭਟੂਰੇ ਕੌਂਬੋ ਕਰ ਦਿਓ",
        strict=True,
    )
    assert len(lines) == 1
    assert lines[0].quantity == 2
    assert "Chole Bhature" in lines[0].item["name"]
