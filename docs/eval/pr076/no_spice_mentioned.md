# Scenario: no_spice_mentioned

- channel: phone
- model: gpt-4.1-mini
- result: PASS

## Transcript

**SIERRA (greeting):** Hi! I'm Sierra, your virtual assistant. I speak English, Hindi, and Punjabi. How can I help you?

**USER:** Hi, one butter chicken and one garlic naan please.
> `add_item({"item_query": "Butter Chicken", "quantity": 1})` → ADDED: 1 x Butter Chicken. ⏎ ORDER NOW: 1 x Butter Chicken. total=$19.99 ⏎ GUIDE: confirm the add briefly in the customer's language using the exact dish name and quantity above (quantity spoken as "one", never a digit), then keep the order moving.
> `add_item({"item_query": "Garlic Naan", "quantity": 1})` → ADDED: 1 x ਗਾਰਲਿਕ ਨਾਨ (Garlic Naan). ⏎ ORDER NOW: 1 x Butter Chicken; 1 x ਗਾਰਲਿਕ ਨਾਨ (Garlic Naan). total=$24.98 ⏎ GUIDE: confirm the add briefly in the customer's language using the exact dish name and quantity above (quantity spoken as "one", never a digit), then keep the order moving.
**SIERRA:** One Butter Chicken and one ਗਾਰਲਿਕ ਨਾਨ (Garlic Naan) added. Anything else?

**USER:** That's everything.
**SIERRA:** Any spice preferences, allergies, or special instructions for your order?

**USER:** No, nothing — all good.
> `record_additional_requests({"response": "no"})` → ADDITIONAL REQUESTS RECORDED: none. ⏎ SPICE DEFAULTED: Butter Chicken set to medium (no preference stated — use set_item_spice if the customer actually named a level). ⏎ ORDER NOW: 1 x Butter Chicken [medium]; 1 x ਗਾਰਲਿਕ ਨਾਨ (Garlic Naan). total=$24.98 ⏎ GUIDE: acknowledge briefly in the customer's language — do NOT re-ask about spice or allergies — then keep the order moving (pickup or delivery next if not set yet).
**SIERRA:** No problem, all set with spice and allergies. Would you like pickup or delivery?

**USER:** Pickup.
> `set_order_type({"order_type": "pickup"})` → Set to pickup. Continue the flow.
**SIERRA:** Please tell me your name for the order.

**USER:** My name is Karan.
> `set_customer_contact({"name": "Karan"})` → NAME SAVED: "Karan". ⏎ GUIDE: confirm the name briefly in the customer's language. Then ask for their phone number.
**SIERRA:** Thank you, Karan. Now, may I have your phone number?

**USER:** Four one six five five five one two three four.
> `set_customer_contact({"phone": "4165551234"})` → PHONE SAVED: four, one, six, five, five, five, one, two, three, four. ⏎ GUIDE: the number is already saved — do NOT ask the customer to repeat or re-say it. Confirm it back once yourself, speaking it as English word digits exactly as in PHONE SAVED (never numerals, never Punjabi/Hindi number words), then continue the order.
> `get_order_readback({})` → READ THIS BACK VERBATIM, then wait for the customer's yes: ⏎ "Okay Karan ji — one Butter Chicken (medium) and one ਗਾਰਲਿਕ ਨਾਨ, pickup. All good?"
**SIERRA:** Okay Karan ji — one Butter Chicken (medium) and one ਗਾਰਲਿਕ ਨਾਨ, pickup. All good?

**USER:** Yes, that's right.
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
    "name": "Karan",
    "phone": "4165551234"
  },
  "subtotal": 24.98,
  "delivery_charge": 0,
  "total": 24.98,
  "eta": "20-25 min",
  "order_id": "Y8MDSH1X060FC"
}
```

## Assertions

- ✅ gates: placed order had a confirmed, current readback — readback_confirmed=True readback_revision=4 cart.revision=4
- ✅ placed — cart.placed=True
- ✅ items: exact set of dishes — cart=['Butter Chicken', 'Garlic Naan']
- ✅ items: Butter Chicken qty == 1 — got qty=1
- ✅ items: Butter Chicken note contains 'medium' — got note='medium'
- ✅ items: Garlic Naan qty == 1 — got qty=1
- ✅ order_type — got 'pickup'
- ✅ customer_name — got 'Karan'
- ✅ customer_phone — got '4165551234'
- ✅ additional_requests_recorded — got True
- ✅ readbacks: at least 1 successful — got 1
