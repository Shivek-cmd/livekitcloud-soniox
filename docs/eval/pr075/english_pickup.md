# Scenario: english_pickup

- channel: phone
- model: gpt-4.1-mini
- result: PASS

## Transcript

**SIERRA (greeting):** Hi! I'm Sierra, your virtual assistant. I speak English, Hindi, and Punjabi. How can I help you?

**USER:** Hi, can I get two butter chicken and one garlic naan please?
> `add_item({"item_query": "butter chicken", "quantity": 2, "spice_level": "medium"})` → ADDED: 2 x Butter Chicken, note: medium. ⏎ ORDER NOW: 2 x Butter Chicken [medium]. total=$39.98 ⏎ GUIDE: confirm the add briefly in the customer's language using the exact dish name and quantity above (quantity spoken as "two", never a digit), then keep the order moving.
> `add_item({"item_query": "garlic naan", "quantity": 1})` → ADDED: 1 x ਗਾਰਲਿਕ ਨਾਨ (Garlic Naan). ⏎ ORDER NOW: 2 x Butter Chicken [medium]; 1 x ਗਾਰਲਿਕ ਨਾਨ (Garlic Naan). total=$44.97 ⏎ GUIDE: confirm the add briefly in the customer's language using the exact dish name and quantity above (quantity spoken as "one", never a digit), then keep the order moving.
**SIERRA:** Two Butter Chicken and one ਗਾਰਲਿਕ ਨਾਨ added. Anything else?

**USER:** Medium is fine.
**SIERRA:** Anything else you want to add?

**USER:** That's everything, thanks.
**SIERRA:** Any allergies I should know about?

**USER:** No allergies.
> `record_allergies({"response": "no allergies"})` → Allergies recorded: none. Continue — pickup or delivery?
**SIERRA:** Pickup or delivery?

**USER:** Pickup please.
> `set_order_type({"order_type": "pickup"})` → Set to pickup. Continue the flow.
**SIERRA:** Can I have your name for the order?

**USER:** My name is Harpreet.
> `set_customer_contact({"name": "Harpreet"})` → Name saved: "Harpreet".
**SIERRA:** Please provide your phone number.

**USER:** Six four seven five five five one two one two.
> `set_customer_contact({"phone": "six four seven five five five one two one two"})` → Phone saved. Read it back as English word digits ONLY: "six, four, seven, five, five, five, one, two, one, two".
> `get_order_readback({})` → READ THIS BACK VERBATIM, then wait for the customer's yes: ⏎ "Okay Harpreet ji — two Butter Chicken (medium) and one ਗਾਰਲਿਕ ਨਾਨ, pickup. All good?"
**SIERRA:** Okay Harpreet ji — two Butter Chicken (medium) and one ਗਾਰਲਿਕ ਨਾਨ, pickup. All good?

**USER:** Yes, that's correct.
> `confirm_readback({})` → Read-back confirmed. Call place_order now.
> `place_order({})` → Order placed! INTERNAL total $44.97. Tell customer: "ਤੁਹਾਡਾ ਆਰਡਰ ਮਿਲ ਗਿਆ ਜੀ। 20-25 ਮਿੰਟ ਵਿੱਚ ਤਿਆਰ ਹੋ ਜਾਵੇਗਾ। ਧੰਨਵਾਦ ਜੀ!" Do NOT mention price or dollars.
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
      "qty": 2,
      "unit_price": 19.99,
      "line_total": 39.98,
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
    "name": "Harpreet",
    "phone": "6475551212"
  },
  "subtotal": 44.97,
  "delivery_charge": 0,
  "total": 44.97,
  "eta": "20-25 min",
  "order_id": "R4KFP7YHAGSV6"
}
```

## Assertions

- ✅ gates: placed order had a confirmed, current readback — readback_confirmed=True readback_revision=3 cart.revision=3
- ✅ placed — cart.placed=True
- ✅ items: exact set of dishes — cart=['Butter Chicken', 'Garlic Naan']
- ✅ items: Butter Chicken qty == 2 — got qty=2
- ✅ items: Butter Chicken note contains 'medium' — got note='medium'
- ✅ items: Garlic Naan qty == 1 — got qty=1
- ✅ order_type — got 'pickup'
- ✅ customer_name — got 'Harpreet'
- ✅ customer_phone — got '6475551212'
- ✅ allergies_recorded — got True
- ✅ readbacks: at least 1 successful — got 1
