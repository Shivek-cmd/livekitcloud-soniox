# Scenario: change_after_readback

- channel: phone
- model: gpt-4.1-mini
- result: PASS

## Transcript

**SIERRA (greeting):** Hi! I'm Sierra, your virtual assistant. I speak English, Hindi, and Punjabi. How can I help you?

**USER:** Hi, one butter chicken please, medium.
> `add_item({"item_query": "butter chicken", "quantity": 1, "spice_level": "medium"})` → ADDED: 1 x Butter Chicken, note: medium. ⏎ ORDER NOW: 1 x Butter Chicken [medium]. total=$19.99 ⏎ GUIDE: confirm the add briefly in the customer's language using the exact dish name and quantity above (quantity spoken as "one", never a digit), then keep the order moving.
**SIERRA:** One Butter Chicken medium, added. Anything else?

**USER:** That's everything.
**SIERRA:** Any allergies I should know about?

**USER:** No allergies.
> `record_allergies({"response": "no"})` → Allergies recorded: none. Continue — pickup or delivery?
**SIERRA:** Pickup or delivery?

**USER:** Pickup.
> `set_order_type({"order_type": "pickup"})` → Set to pickup. Continue the flow.
**SIERRA:** Please tell me your name for the order.

**USER:** Jasleen.
> `set_customer_contact({"name": "Jasleen"})` → Name saved: "Jasleen".
**SIERRA:** And your phone number, please?

**USER:** Four one six five five five two two three three.
> `set_customer_contact({"phone": "4165552233"})` → Phone saved. Read it back as English word digits ONLY: "four, one, six, five, five, five, two, two, three, three".
**SIERRA:** Your phone number is four, one, six, five, five, five, two, two, three, three. Is that correct?

**USER (reactive):** Yes.
> `get_order_readback({})` → READ THIS BACK VERBATIM, then wait for the customer's yes: ⏎ "Okay Jasleen ji — one Butter Chicken (medium), pickup. All good?"
**SIERRA:** Okay Jasleen ji — one Butter Chicken (medium), pickup. All good?

**USER:** Actually, add a garlic naan too.
> `add_item({"item_query": "garlic naan", "quantity": 1})` → ADDED: 1 x ਗਾਰਲਿਕ ਨਾਨ (Garlic Naan). ⏎ ORDER NOW: 1 x Butter Chicken [medium]; 1 x ਗਾਰਲਿਕ ਨਾਨ (Garlic Naan). total=$24.98 ⏎ GUIDE: confirm the add briefly in the customer's language using the exact dish name and quantity above (quantity spoken as "one", never a digit), then keep the order moving.
**SIERRA:** One garlic naan added. Anything else?

**USER:** Yes, that's all correct now.
> `get_order_readback({})` → READ THIS BACK VERBATIM, then wait for the customer's yes: ⏎ "Okay Jasleen ji — one Butter Chicken (medium) and one ਗਾਰਲਿਕ ਨਾਨ, pickup. All good?"
**SIERRA:** Okay Jasleen ji — one Butter Chicken (medium) and one ਗਾਰਲਿਕ ਨਾਨ, pickup. All good?

**USER:** Yes, perfect.
> `confirm_readback({})` → Read-back confirmed. Call place_order now.
> `place_order({})` → Order placed! INTERNAL total $24.979999999999997. Tell customer: "ਤੁਹਾਡਾ ਆਰਡਰ ਮਿਲ ਗਿਆ ਜੀ। 20-25 ਮਿੰਟ ਵਿੱਚ ਤਿਆਰ ਹੋ ਜਾਵੇਗਾ। ਧੰਨਵਾਦ ਜੀ!" Do NOT mention price or dollars.
**SIERRA:** ਤੁਹਾਡਾ ਆਰਡਰ ਮਿਲ ਗਿਆ ਜੀ। 20-25 ਮਿੰਟ ਵਿੱਚ ਤਿਆਰ ਹੋ ਜਾਵੇਗਾ। ਧੰਨਵਾਦ ਜੀ!

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
    },
    {
      "id": "T61J8SX6W8JF2",
      "name": "Garlic Naan",
      "voice_line": "ਗਾਰਲਿਕ ਨਾਨ",
      "qty": 1,
      "unit_price": 4.99,
      "line_total": 4.99,
      "note": "",
      "modifiers": []
    }
  ],
  "order_type": "pickup",
  "delivery_address": null,
  "customer": {
    "name": "Jasleen",
    "phone": "4165552233"
  },
  "subtotal": 24.98,
  "delivery_charge": 0,
  "total": 24.98,
  "eta": "20-25 min",
  "order_id": "82FGTEZXCQ15M"
}
```

## Assertions

- ✅ gates: placed order had a confirmed, current readback — readback_confirmed=True readback_revision=3 cart.revision=3
- ✅ placed — cart.placed=True
- ✅ items: exact set of dishes — cart=['Butter Chicken', 'Garlic Naan']
- ✅ items: Butter Chicken qty == 1 — got qty=1
- ✅ items: Butter Chicken note contains 'medium' — got note='medium'
- ✅ items: Garlic Naan qty == 1 — got qty=1
- ✅ order_type — got 'pickup'
- ✅ customer_name — got 'Jasleen'
- ✅ customer_phone — got '4165552233'
- ✅ allergies_recorded — got True
- ✅ readbacks: at least 2 successful — got 2
