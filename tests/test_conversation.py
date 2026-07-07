"""Tests for conversation intent, templates, and order flow guidance."""

from restaurant.conversation import (
    ALLERGIES_QUESTION,
    CustomerLanguage,
    UserIntent,
    detect_intent,
    format_order_readback,
    format_order_status,
    format_price_reply,
    is_allergies_step_answer,
    is_confirm_no,
    is_confirm_yes,
    is_likely_pickup_stt,
    is_readback_ack,
    is_readback_all_clear,
    mentions_already_said,
    phrase_phone_saved,
    resolve_intent,
    sanitize_assistant_speech,
)
from restaurant.order_flow import OrderFlowController, OrderPhase
from restaurant.orders import OrderCart


def test_detect_price_intent():
    assert detect_intent("how much is butter chicken") == UserIntent.ASK_PRICE
    assert detect_intent("ਕੀਮਤ ਕਿੰਨੀ ਹੈ") == UserIntent.ASK_PRICE


def test_detect_availability_without_add():
    assert detect_intent("do you have gajar halwa") == UserIntent.ASK_AVAILABILITY
    assert detect_intent("ਮਿੱਠੇ ਚ ਕੀ ਹੈ") == UserIntent.ASK_AVAILABILITY


def test_detect_add_intent():
    assert detect_intent("I want to order butter chicken") == UserIntent.ADD_ITEM
    assert detect_intent("ਮੈਨੂੰ ਇੱਕ ਮੈਂਗੋ ਕੁਲਫੀ ਚਾਹੀਦੀ") == UserIntent.ADD_ITEM


def test_pickup_not_add_item():
    assert detect_intent("ਚਾਹੀਦਾ pickup") == UserIntent.PICKUP
    assert detect_intent("pick up please") == UserIntent.PICKUP


def test_detect_order_done():
    assert detect_intent("that's it") == UserIntent.ORDER_DONE
    assert detect_intent("ਨਹੀਂ ਨਹੀਂ, ਬਸ") == UserIntent.ORDER_DONE


def test_detect_order_status_not_misread_as_add():
    # Live-call regression (PR 042): this exact utterance was classified
    # add_item because _ADD_RE matches the bare word "ਆਰਡਰ", which routed
    # the LLM into freeform generation and it hallucinated a wrong item.
    assert (
        detect_intent("ਮੇਰਾ ਆਰਡਰ ਦੱਸੋ, ਕੀ ਹੈਗਾ ਹੁਣ ਤੱਕਰ? ਕੀ ਆਰਡਰ ਕੀਤਾ ਜੀ ਮੈਂ?")
        == UserIntent.ASK_ORDER_STATUS
    )
    assert detect_intent("what's my order so far?") == UserIntent.ASK_ORDER_STATUS
    assert detect_intent("what did I order?") == UserIntent.ASK_ORDER_STATUS


def test_order_status_does_not_block_genuine_add():
    assert detect_intent("ਆਰਡਰ ਕਰ ਦਿਓ ਗਾਰਲਿਕ ਨਾਨ") == UserIntent.ADD_ITEM


def test_restated_item_after_no_no_is_add_not_confirm_no():
    # Live-call regression (PR 042): caller corrects a missed item by
    # restating it after "ਨਹੀਂ ਨਹੀਂ" (no no); this used to be swallowed as
    # CONFIRM_NO (interpreted as "no allergies") and the item never got
    # added, forcing the caller to repeat it three times.
    assert detect_intent("ਨਹੀਂ ਨਹੀਂ, ਬਟਰ ਨਾਨ ਕਰੋ") == UserIntent.ADD_ITEM


def test_gurmukhi_add_loanword_detected():
    # "ਐਡ" is the common Gurmukhi spelling of the English loanword "add".
    assert detect_intent("ਬਟਰ ਨਾਨ ਐਡ ਕਰੋ") == UserIntent.ADD_ITEM


def test_bas_as_quantifier_is_add_not_done():
    # Live-call regression (PR 051): "ਬਸ ਇੱਕ ਮਸਾਲਾ ਚਾ ਕਰ ਦੋ" (JUST one masala
    # chai) has ਬਸ acting as a quantifier ("just"), not the discourse
    # "that's it/done" _DONE_RE is meant to catch. This used to be
    # misclassified ORDER_DONE and the chai never got added — the caller
    # only discovered it was missing at the final read-back.
    text = "ਚਲੋ ਮਸਾਲਾ ਚਾ ਕਰ ਦੋ ਫਿਰ। ਬਸ ਇੱਕ ਮਸਾਲਾ ਚਾ ਕਰ ਦੋ ਨਾ।"
    assert detect_intent(text) == UserIntent.ADD_ITEM


def test_bare_bas_without_item_still_order_done():
    # A bare "ਬਸ" with no dish/imperative must still mean "that's it."
    assert detect_intent("ਬਸ") == UserIntent.ORDER_DONE
    assert detect_intent("ਨਹੀਂ ਨਹੀਂ, ਬਸ") == UserIntent.ORDER_DONE


def test_plain_negation_without_item_still_confirm_no():
    assert detect_intent("ਨਹੀਂ ਨਹੀਂ") == UserIntent.CONFIRM_NO
    assert detect_intent("nahi") == UserIntent.CONFIRM_NO


def test_leading_no_is_confirm_no():
    assert is_confirm_no("no")
    assert is_confirm_no("nahi ji")
    assert is_confirm_no("ਨਹੀਂ, ਛੋਲੇ ਬਟੂਰੇ ਨਹੀਂ ਹਨ।")


def test_embedded_negation_is_not_confirm_no():
    # Live-call regression (PR 047): "ਛੋਲੇ ਬਟੂਰੇ ਨਹੀਂ ਹਨ" (chole bhature isn't
    # available) has no leading "no" — the negation is a predicate deep in a
    # sentence about food, not an answer to a yes/no question. This used to be
    # misread as CONFIRM_NO purely because "ਨਹੀਂ" appeared anywhere in the
    # text, which let is_allergies_step_answer() treat it as "no allergies"
    # and skip straight to pickup/delivery without allergies ever being asked.
    assert not is_confirm_no("ਛੋਲੇ ਬਟੂਰੇ ਨਹੀਂ ਹਨ।")
    assert detect_intent("ਛੋਲੇ ਬਟੂਰੇ ਨਹੀਂ ਹਨ।") != UserIntent.CONFIRM_NO
    assert is_allergies_step_answer("ਛੋਲੇ ਬਟੂਰੇ ਨਹੀਂ ਹਨ।", UserIntent.GENERAL) is False


def test_leading_no_still_answers_allergies():
    # The genuine "no [more items], and by the way..." case must keep working.
    text = "ਨਹੀਂ, ਛੋਲੇ ਬਟੂਰੇ ਨਹੀਂ ਹਨ।"
    intent = detect_intent(text)
    assert intent == UserIntent.CONFIRM_NO
    assert is_allergies_step_answer(text, intent) is True


def test_mentions_already_said_detects_correction_phrasing():
    # Live-call regression (PR 052): caller naming ONE missed item after
    # Sierra's confirmation — a correction, not a fresh order request.
    assert mentions_already_said("ਦਾਲਮਖਨੀ ਵੀ ਕਿਹਾ ਮੈਂ।") is True
    assert mentions_already_said("ਚਾਇ, ਚਾਇ ਵੀ ਬੋਲੀ ਸੀ ਮੈਂ ਨੇ।") is True
    assert mentions_already_said("I also said one naan") is True


def test_mentions_already_said_false_for_fresh_add():
    assert mentions_already_said("add one naan") is False
    assert mentions_already_said("ਇੱਕ ਨਾਨ ਕਰ ਦਿਓ") is False


def test_format_order_status():
    cart = OrderCart()
    assert format_order_status(cart) == "Your order is empty so far."

    cart.add_item({"name": "Amritsari Fish", "voice_line": "Amritsari Fish", "price": 15.0}, 1)
    status = format_order_status(cart, include_price=False)
    assert "Amritsari Fish" in status
    assert "dollar" not in status.lower()
    assert "All good" not in status


def test_format_price_reply():
    assert format_price_reply(6.99) == "That's about 7 dollars ji."
    assert format_price_reply(13.48) == "That's about 13.48 dollars ji."


def test_format_order_readback():
    cart = OrderCart()
    cart.add_item(
        {
            "name": "Paneer Tikka",
            "voice_line": "Paneer Tikka",
            "price": 14.99,
        },
        1,
        note="medium",
    )
    cart.add_item(
        {"name": "Gulab Jamun", "voice_line": "ਗੁਲਾਬ ਜਾਮੁਨ", "price": 6.99},
        2,
    )
    cart.order_type = "pickup"
    cart.customer_name = "Shivek"
    line = format_order_readback(cart)
    assert "one Paneer Tikka (medium)" in line
    assert "two ਗੁਲਾਬ ਜਾਮੁਨ" in line
    assert "pickup" in line
    assert "All good?" in line
    assert " ik " not in f" {line.lower()} "
    assert " do " not in f" {line.lower()} "


def test_sanitize_removes_regreeting():
    raw = "ਸਤ ਸ੍ਰੀ ਅਕਾਲ! How can I help?"
    out = sanitize_assistant_speech(raw, allow_greeting=False)
    assert "ਸਤ ਸ੍ਰੀ ਅਕਾਲ" not in out
    assert out


def test_quantity_gate_on_availability():
    cart = OrderCart()
    flow = OrderFlowController(is_phone=True)
    plan = flow.build_turn_plan("do you have gajar halwa", UserIntent.ASK_AVAILABILITY, cart)
    assert "Do NOT ask how many" in plan.guidance
    assert plan.quantity_allowed is False


def test_quantity_allowed_on_add():
    cart = OrderCart()
    flow = OrderFlowController(is_phone=True)
    plan = flow.build_turn_plan("add mango kulfi", UserIntent.ADD_ITEM, cart)
    assert plan.quantity_allowed is True
    assert "SAY EXACTLY" in plan.guidance or "add_to_order" in plan.guidance


def test_quantity_not_allowed_when_explicit_in_utterance():
    cart = OrderCart()
    flow = OrderFlowController(is_phone=True)
    plan = flow.build_turn_plan(
        "ਮੈਨੂੰ ਇੱਕ ਚਿਕਨ ਟਿੱਕਾ ਚਾਹੀਦਾ",
        UserIntent.ADD_ITEM,
        cart,
    )
    assert plan.quantity_allowed is False
    assert "How many" not in plan.guidance


def test_multi_item_add_guidance():
    cart = OrderCart()
    flow = OrderFlowController(is_phone=True)
    plan = flow.build_turn_plan(
        "add one gulab jamun and one kheer",
        UserIntent.ADD_ITEM,
        cart,
    )
    assert "listed 2 items" in plan.guidance
    assert "Do NOT ask what the second item is" in plan.guidance
    assert "Anything else?" in plan.guidance


def test_order_done_uses_allergies_template():
    cart = OrderCart()
    cart.add_item({"name": "Kulfi", "voice_line": "Mango Kulfi", "price": 6.99}, 1)
    flow = OrderFlowController(is_phone=True)
    plan = flow.build_turn_plan("that's all", UserIntent.ORDER_DONE, cart)
    assert flow.state.phase == OrderPhase.SPECIAL_INSTRUCTIONS
    assert "Still needed before you can place this order" in plan.guidance


def test_phase_advances_after_no_allergy():
    cart = OrderCart()
    cart.add_item({"name": "Kulfi", "voice_line": "Mango Kulfi", "price": 6.99}, 1)
    flow = OrderFlowController(is_phone=True)
    flow.mark_items_complete()
    flow.mark_allergies_asked()
    plan = flow.build_turn_plan("ਨਹੀਂ, ਕੋਈ ਐਲਰਜੀ ਨਹੀਂ", UserIntent.CONFIRM_NO, cart)
    assert flow.state.special_instructions_done is True
    assert flow.state.phase == OrderPhase.ORDER_TYPE
    assert "Still needed before you can place this order" in plan.guidance


def test_unrelated_repeat_does_not_skip_allergies():
    # Live-call regression (PR 047): caller repeats an unresolved food-
    # availability statement instead of answering allergies. The ladder must
    # stay at SPECIAL_INSTRUCTIONS, not silently advance to ORDER_TYPE.
    cart = OrderCart()
    cart.add_item({"name": "Kulfi", "voice_line": "Mango Kulfi", "price": 6.99}, 1)
    flow = OrderFlowController(is_phone=True)
    flow.mark_items_complete()
    flow.mark_allergies_asked()

    text = "ਛੋਲੇ ਬਟੂਰੇ ਨਹੀਂ ਹਨ।"
    intent = resolve_intent(text, phase=OrderPhase.SPECIAL_INSTRUCTIONS.value)
    flow.build_turn_plan(text, intent, cart)

    assert flow.state.special_instructions_done is False
    assert flow.state.phase == OrderPhase.SPECIAL_INSTRUCTIONS


def test_allergies_step_accepts_modifier_note_without_qty():
    text = "ਤੰਦੂਰੀ ਰੋਟੀ ਤੇ ਥੋੜ੍ਹੀ ਅਜਵਾਇਨ ਐਡ ਕਰ ਦੇਣਾ ਜੀ"
    assert detect_intent(text) == UserIntent.ADD_ITEM
    assert is_allergies_step_answer(text, UserIntent.ADD_ITEM) is True


def test_allergies_step_does_not_swallow_explicit_new_qty_add():
    text = "ਇੱਕ ਹੋਰ ਗਾਰਲਿਕ ਨਾਨ ਐਡ ਕਰੋ"
    assert detect_intent(text) == UserIntent.ADD_ITEM
    assert is_allergies_step_answer(text, UserIntent.ADD_ITEM) is False


def test_allergies_complaint_is_not_an_answer():
    # Live-call regression (PR 048): is_allergies_step_answer() matched the
    # bare substring "allerg" anywhere in the text, so a caller complaining
    # "why are you asking for allergies and special instructions?" counted
    # as answering — the ladder then advanced to pickup/delivery without the
    # caller ever actually being asked again or given a real answer.
    complaint = (
        "Did you understand what I asked you? Like, why are you asking "
        "for allergies and special instructions?"
    )
    assert is_allergies_step_answer(complaint, UserIntent.GENERAL) is False


def test_real_allergy_mention_still_counts_as_answer():
    assert is_allergies_step_answer("I have a peanut allergy", UserIntent.GENERAL) is True
    assert (
        is_allergies_step_answer("ਮੈਨੂੰ ਐਲਰਜੀ ਹੈ ਮੂੰਗਫਲੀ ਤੋਂ", UserIntent.GENERAL)
        is True
    )


def test_confirming_readback_template():
    cart = OrderCart()
    cart.add_item({"name": "Kulfi", "voice_line": "Mango Kulfi", "price": 6.99}, 1)
    cart.order_type = "pickup"
    flow = OrderFlowController(is_phone=True)
    flow.mark_items_complete()
    flow.mark_special_instructions_done()
    flow.sync_from_cart(cart)
    assert flow.state.phase == OrderPhase.READBACK
    plan = flow.build_turn_plan("yes", UserIntent.CONFIRM_YES, cart)
    assert flow.state.readback_confirmed is True
    assert flow.state.phase == OrderPhase.CUSTOMER_NAME
    assert "Still needed before you can place this order" in plan.guidance


def test_want_to_order_asks_pickup_delivery():
    cart = OrderCart()
    flow = OrderFlowController(is_phone=True)
    plan = flow.build_turn_plan(
        "ਹਾਂ ਜੀ, ਮੈਂ ਕੁਝ ਆਰਡਰ ਕਰਨਾ ਸੀ ਜੀ।",
        UserIntent.ADD_ITEM,
        cart,
    )
    assert "pick items first" in plan.guidance.lower() or "Do NOT ask pickup" in plan.guidance


def test_readback_before_name():
    cart = OrderCart()
    cart.add_item({"name": "Kulfi", "voice_line": "Mango Kulfi", "price": 6.99}, 1)
    cart.order_type = "pickup"
    flow = OrderFlowController(is_phone=True)
    flow.mark_items_complete()
    flow.mark_special_instructions_done()
    flow.sync_from_cart(cart)
    assert flow.state.phase == OrderPhase.READBACK
    assert flow.state.readback_confirmed is False


def test_ikk_cup_pickup_at_order_type():
    assert resolve_intent("ਇੱਕ ਕੱਪ?", phase="order_type") == UserIntent.PICKUP
    assert resolve_intent("ਇੱਕ ਅੱਪ।", phase="order_type") == UserIntent.PICKUP
    assert resolve_intent("ਇੱਕ ਕੱਪ, ਆਈ ਸੈਡ।", phase="order_type") == UserIntent.PICKUP
    assert is_likely_pickup_stt("pick up please") is True


def test_confirm_yes_all_good_code_mix():
    assert is_confirm_yes("ਹਾਂ ਜੀ, ਆਲ ਗੁੱਡ") is True
    assert is_confirm_yes("ਯੇਸ, ਆਲ ਗੁੱਡ") is True
    assert is_confirm_yes("yes all good") is True
    assert resolve_intent("ਹਾਂ ਜੀ, ਆਲ ਗੁੱਡ") == UserIntent.CONFIRM_YES


def test_confirming_advances_on_all_good():
    cart = OrderCart()
    cart.add_item({"name": "Kulfi", "voice_line": "Mango Kulfi", "price": 6.99}, 1)
    cart.order_type = "pickup"
    flow = OrderFlowController(is_phone=True)
    flow.mark_items_complete()
    flow.mark_special_instructions_done()
    flow.sync_from_cart(cart)
    plan = flow.build_turn_plan("ਹਾਂ ਜੀ, ਆਲ ਗੁੱਡ", UserIntent.GENERAL, cart)
    assert flow.state.readback_confirmed is True
    assert flow.state.phase == OrderPhase.CUSTOMER_NAME
    assert "Still needed before you can place this order" in plan.guidance


def test_readback_without_price_on_phone():
    cart = OrderCart()
    cart.add_item({"name": "Kulfi", "voice_line": "Mango Kulfi", "price": 6.99}, 1)
    cart.order_type = "pickup"
    line = format_order_readback(cart, include_price=False)
    assert "dollar" not in line.lower()
    assert "All good?" in line
    assert "pickup" in line


def test_sanitize_strips_price_on_phone():
    raw = "Okay — one Kulfi, pickup, total about 33 dollars. All good?"
    out = sanitize_assistant_speech(raw, allow_greeting=False, is_phone=True)
    assert "dollar" not in out.lower()
    assert "33" not in out


def test_sanitize_strips_price_on_web():
    raw = (
        "ਠੀਕ ਹੈ ਜੀ — ਇਕ ਵੈਜ ਸਪ੍ਰਿੰਗ ਰੋਲ, ਇਕ ਸਰ੍ਹੋਂ ਦਾ ਸਾਗ, "
        "ਤੇ ਦੋ ਬਟਰ ਨਾਨ, pickup, ਕੁੱਲ ਤਕਰੀਬਨ ਤੀਹ ਡਾਲਰ। ਬਿਲਕੁਲ ਠੀਕ?"
    )
    out = sanitize_assistant_speech(raw, allow_greeting=False, is_phone=False)
    assert "ਡਾਲਰ" not in out
    assert "dollar" not in out.lower()
    assert "ਵੈਜ ਸਪ੍ਰਿੰਗ ਰੋਲ" in out


def test_readback_ack_chacko():
    assert is_readback_ack("ਚੈਕੋ")
    assert is_readback_ack("ਚੈਕੋ।")
    assert resolve_intent("ਚੈਕੋ", phase="readback") == UserIntent.CONFIRM_YES


def test_readback_all_clear_not_confirm_no():
    text = "ਨਹੀਂ ਜੀ, ਕੋਈ ਗੱਲ ਨਹੀਂ"
    assert is_readback_all_clear(text)
    assert resolve_intent(text, phase="readback") == UserIntent.CONFIRM_YES
    assert detect_intent(text) == UserIntent.CONFIRM_NO


def test_readback_all_clear_advances_phase():
    cart = OrderCart()
    cart.add_item({"name": "Kulfi", "voice_line": "Mango Kulfi", "price": 6.99}, 1)
    cart.order_type = "pickup"
    flow = OrderFlowController(is_phone=True)
    flow.mark_items_complete()
    flow.mark_special_instructions_done()
    flow.sync_from_cart(cart)
    plan = flow.build_turn_plan("ਨਹੀਂ ਜੀ, ਕੋਈ ਗੱਲ ਨਹੀਂ", UserIntent.CONFIRM_NO, cart)
    assert flow.state.readback_confirmed is True
    assert flow.state.phase == OrderPhase.CUSTOMER_NAME
    assert "phone" in plan.guidance.lower()


def test_phone_saved_uses_gurmukhi_not_hindi_loanword():
    line = phrase_phone_saved(CustomerLanguage.MIXED, "nine, four, one")
    assert "Dhanyavaad" not in line
    assert "ਧੰਨਵਾਦ" in line


def test_sanitize_rewrites_dhanyavaad():
    raw = "Dhanyavaad ji — nine, four, one."
    out = sanitize_assistant_speech(raw, allow_greeting=False)
    assert "Dhanyavaad" not in out
    assert "ਧੰਨਵਾਦ" in out
