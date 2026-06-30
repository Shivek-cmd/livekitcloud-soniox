"""Tests for session analytics recorder."""

from restaurant.orders import OrderCart
from restaurant.order_flow import OrderFlowController
from restaurant.session_recorder import SessionRecorder


def test_finalize_placed_order():
    recorder = SessionRecorder()
    recorder.start(room_name="phone-abc", channel="phone")
    recorder.begin_user_turn("one butter chicken")
    recorder.complete_turn(intent="add_item", phase="collecting_items")
    recorder.append_sierra("Yes — one Butter Chicken.")

    cart = OrderCart()
    item = {
        "name": "Butter Chicken",
        "voice_line": "Butter Chicken",
        "price": 13.99,
    }
    cart.add_item(item, 1)
    cart.order_type = "pickup"
    cart.customer_name = "Test"
    cart.customer_phone = "7805551234"
    cart.mark_placed(eta="20-25 min")
    recorder.set_outcome("placed")

    flow = OrderFlowController(is_phone=True)
    payload = recorder.finalize(cart, flow)

    assert payload["session"]["outcome"] == "placed"
    assert payload["session"]["channel"] == "phone"
    assert payload["session"]["turn_count"] == 1
    assert payload["order"] is not None
    assert payload["order"]["total"] == 13.99


def test_mark_filtered_echo():
    recorder = SessionRecorder()
    recorder.start(room_name="phone-x", channel="phone")
    recorder.begin_user_turn("hello sierra")
    recorder.mark_filtered("echo")

    cart = OrderCart()
    flow = OrderFlowController(is_phone=True)
    payload = recorder.finalize(cart, flow)

    assert payload["session"]["echo_filter_count"] == 1
    assert payload["turns"][0]["was_filtered"] is True
    assert payload["turns"][0]["filter_reason"] == "echo"
