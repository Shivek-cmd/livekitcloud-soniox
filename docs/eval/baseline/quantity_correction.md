# Scenario: quantity_correction

- channel: phone
- model: gpt-4.1-mini
- result: PASS

## Transcript

**SIERRA (greeting):** Hi! I'm Sierra, your virtual assistant. I speak English, Hindi, and Punjabi. How can I help you?

**USER:** Two butter chicken please, medium spice.
> `add_item({"item_query": "butter chicken", "quantity": 2, "spice_level": "medium"})` → INTERNAL: item saved. ⏎ SAY EXACTLY: "Yes — two Butter Chicken." ⏎ Do NOT mention price, cart, menu, pieces, or say I can add / I've added.
**SIERRA:** Yes — two Butter Chicken. Anything else?

**USER:** Wait — I said one, not two.
> `set_item_quantity({"item_query": "butter chicken", "quantity": 1})` → INTERNAL: quantity corrected (not added). ⏎ SAY EXACTLY: "Got it — one Butter Chicken, fixed." ⏎ Do NOT mention price, cart, or menu.
**SIERRA:** Got it — one Butter Chicken, fixed. Anything else?

**USER:** That's all.
**SIERRA:** Any allergies I should know about?

**USER:** No allergies.
> `record_allergies({"response": "no"})` → Allergies recorded: none. Continue — pickup or delivery?
**SIERRA:** Pickup or delivery?

**USER:** Pickup.
> `set_order_type({"order_type": "pickup"})` → Set to pickup. Continue the flow.
**SIERRA:** Can I have your name for the order?

**USER:** It's Simran.
> `set_customer_contact({"name": "Simran"})` → Name saved: "Simran".
**SIERRA:** Please provide your phone number.

**USER:** Nine zero five five five five one one two two.
> `set_customer_contact({"phone": "9055551122"})` → Phone saved. Read it back as English word digits ONLY: "nine, zero, five, five, five, five, one, one, two, two".
**SIERRA:** Your order is one Butter Chicken, medium spice, for pickup under the name Simran, phone number nine, zero, five, five, five, five, one, one, two, two. Is that correct?

**USER (reactive):** Yes.
> `confirm_readback({})` → No read-back has been given yet — call get_order_readback first and read it to the customer.
> `get_order_readback({})` → READ THIS BACK VERBATIM, then wait for the customer's yes: ⏎ "Okay Simran ji — one Butter Chicken (medium), pickup. All good?"
**SIERRA:** Okay Simran ji — one Butter Chicken (medium), pickup. All good?

**USER:** Yes, perfect.
> `confirm_readback({})` → Read-back confirmed. Call place_order now.
> `place_order({})` → Order placed! INTERNAL total $19.99. Tell customer: "ਤੁਹਾਡਾ ਆਰਡਰ ਮਿਲ ਗਿਆ ਜੀ। 20-25 ਮਿੰਟ ਵਿੱਚ ਤਿਆਰ ਹੋ ਜਾਵੇਗਾ। ਧੰਨਵਾਦ ਜੀ!" Do NOT mention price or dollars.
**SIERRA:** ਤੁਹਾਡਾ ਆਰਡਰ ਮਿਲ ਗਿਆ ਜੀ। 20-25 ਮਿੰਟ ਵਿੱਚ ਤਿਆਰ ਹੋ ਜਾਵੇਗਾ। ਧੰਨਵਾਦ ਜੀ!

**USER:** Yes.
**SIERRA:** If you need anything else, just call. Have a great day!

## Final cart

```json
{
  "v": 1,
  "status": "placed",
  "items": [
    {
      "id": "DB4GJPSG6EZ0R",
      "name": "Butter Chicken",
      "voice_line": "Butter Chicken",
      "qty": 1,
      "unit_price": 19.99,
      "line_total": 19.99,
      "note": "medium",
      "modifiers": [
        "medium"
      ]
    }
  ],
  "order_type": "pickup",
  "delivery_address": null,
  "customer": {
    "name": "Simran",
    "phone": "9055551122"
  },
  "subtotal": 19.99,
  "delivery_charge": 0,
  "total": 19.99,
  "eta": "20-25 min",
  "order_id": "4QTSXTM56DWHW"
}
```

## Assertions

- ✅ gates: placed order had a confirmed, current readback — readback_confirmed=True readback_revision=3 cart.revision=3
- ✅ placed — cart.placed=True
- ✅ items: exact set of dishes — cart=['Butter Chicken']
- ✅ items: Butter Chicken qty == 1 — got qty=1
- ✅ items: Butter Chicken note contains 'medium' — got note='medium'
- ✅ order_type — got 'pickup'
- ✅ customer_name — got 'Simran'
- ✅ customer_phone — got '9055551122'
- ✅ allergies_recorded — got True
- ✅ readbacks: at least 1 successful — got 1
