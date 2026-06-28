"""Tests for customer language detection and turn guidance."""

from restaurant.conversation import (
    OPENING_GREETING,
    CustomerLanguage,
    UserIntent,
    detect_customer_language,
    language_turn_guidance,
    phrase_anything_else,
    update_preferred_language,
)
from restaurant.order_flow import OrderFlowController
from restaurant.orders import OrderCart


def test_opening_greeting_trilingual():
    assert "English, Hindi, or Punjabi" in OPENING_GREETING
    assert "Bizbull Restaurant" in OPENING_GREETING


def test_detect_punjabi_script():
    assert detect_customer_language("ਹਾਂ ਜੀ, ਮੈਨੂੰ paneer chahida") == CustomerLanguage.PUNJABI


def test_detect_hindi_script():
    assert detect_customer_language("क्या paneer hai?") == CustomerLanguage.HINDI


def test_detect_english():
    assert detect_customer_language("I want butter chicken please") == CustomerLanguage.ENGLISH


def test_preferred_language_sticky_then_switch():
    lang = update_preferred_language(None, "Hello, I'd like to order")
    assert lang == CustomerLanguage.ENGLISH
    lang = update_preferred_language(lang, "ਹਾਂ ਜੀ, paneer tikka chahida")
    assert lang == CustomerLanguage.PUNJABI


def test_turn_guidance_includes_punjabi():
    g = language_turn_guidance(CustomerLanguage.PUNJABI)
    assert "Punjabi" in g
    assert "stay English" in g


def test_flow_sets_lang_on_web_punjabi_turn():
    flow = OrderFlowController(is_phone=False)
    cart = OrderCart()
    plan = flow.build_turn_plan(
        "ਹਾਂ ਜੀ, ਕੀ ਤੁਹਾਡੇ ਕੋਲ paneer hai?",
        UserIntent.ASK_AVAILABILITY,
        cart,
    )
    assert flow.state.preferred_language == CustomerLanguage.PUNJABI
    assert "lang=pa" in plan.guidance
    assert "Punjabi" in plan.guidance


def test_anything_else_punjabi_in_guidance():
    flow = OrderFlowController(is_phone=False)
    cart = OrderCart()
    cart.add_item({"name": "Paneer Tikka", "voice_line": "Paneer Tikka", "price": 14}, 1)
    flow.on_item_added()
    plan = flow.build_turn_plan("ਹਾਂ ਜੀ paneer", UserIntent.GENERAL, cart)
    assert flow.state.preferred_language == CustomerLanguage.PUNJABI
    assert phrase_anything_else(CustomerLanguage.PUNJABI) in plan.guidance
