# Scenario: quantity_correction

- channel: phone
- model: gpt-4.1-mini
- result: PASS

## Transcript

**SIERRA (greeting):** Hi! I'm Sierra, your virtual assistant. I speak English, Hindi, and Punjabi. How can I help you?

**USER:** Two butter chicken please, medium spice.
> `add_item({"item_query": "butter chicken", "quantity": 2, "spice_level": "medium"})` → ADDED: 2 x Butter Chicken, note: medium. ⏎ ORDER NOW: 2 x Butter Chicken [medium]. total=$39.98 ⏎ GUIDE: confirm the add briefly in the customer's language using the exact dish name and quantity above (quantity spoken as "two", never a digit), then keep the order moving.
**SIERRA:** Two Butter Chicken, medium spice, added. Anything else?

**USER:** Wait — I said one, not two.
> `set_item_quantity({"item_query": "butter chicken", "quantity": 1})` → CORRECTED (not added): Butter Chicken is now 1 total. ⏎ ORDER NOW: 1 x Butter Chicken [medium]. total=$19.99 ⏎ GUIDE: confirm the correction briefly in the customer's language — it is a fix to "one" total, not a second add.
**SIERRA:** Butter Chicken quantity corrected to one. Anything else?

**USER:** That's all.
> `record_additional_requests({"response": "medium spice, no allergies, no special instructions"})` → ADDITIONAL REQUESTS RECORDED for the kitchen: "medium spice, no allergies, no special instructions". ⏎ ORDER NOW: 1 x Butter Chicken [medium]. total=$19.99 ⏎ GUIDE: acknowledge briefly in the customer's language — do NOT re-ask about spice or allergies — then keep the order moving (pickup or delivery next if not set yet).
**SIERRA:** Medium spice noted, no allergies or special instructions. Pickup or delivery?

**USER:** No allergies, nothing else.
**SIERRA:** Please tell me, is this order for pickup or delivery?

**USER:** Pickup.
> `set_order_type({"order_type": "pickup"})` → Set to pickup. Continue the flow.
**SIERRA:** Great, pickup it is. May I have your name for the order?

**USER:** It's Simran.
> `set_customer_contact({"name": "Simran"})` → NAME SAVED: "Simran". ⏎ GUIDE: confirm the name briefly in the customer's language. Then ask for their phone number.
**SIERRA:** Simran, got it. Please provide your phone number.

**USER:** Nine zero five five five five one one two two.
> `set_customer_contact({"phone": "9055551122"})` → PHONE SAVED: nine, zero, five, five, five, five, one, one, two, two. ⏎ GUIDE: the number is already saved — do NOT ask the customer to repeat or re-say it. Confirm it back once yourself, speaking it as English word digits exactly as in PHONE SAVED (never numerals, never Punjabi/Hindi number words), then continue the order.
> `get_order_readback({})` → READ THIS BACK VERBATIM, then wait for the customer's yes: ⏎ "Okay Simran ji — one Butter Chicken (medium), pickup. All good?"
**SIERRA:** Okay Simran ji — one Butter Chicken (medium), pickup. All good?

**USER:** Yes, perfect.
> `confirm_readback({})` → Read-back confirmed. Call place_order now.
> `place_order({})` → Order placed! INTERNAL total $19.99. Tell customer: "ਤੁਹਾਡਾ ਆਰਡਰ ਮਿਲ ਗਿਆ ਜੀ। 20-25 ਮਿੰਟ ਵਿੱਚ ਤਿਆਰ ਹੋ ਜਾਵੇਗਾ। ਧੰਨਵਾਦ ਜੀ!" Do NOT mention price or dollars.
**SIERRA:** ਤੁਹਾਡਾ ਆਰਡਰ ਮਿਲ ਗਿਆ ਜੀ। 20-25 ਮਿੰਟ ਵਿੱਚ ਤਿਆਰ ਹੋ ਜਾਵੇਗਾ। ਧੰਨਵਾਦ ਜੀ!

**USER:** Yes.
**SIERRA:** If you need anything else later, just call. Have a great day!

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
  "order_id": "7NQ36Y4X6JBB2"
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
- ✅ additional_requests_recorded — got True
- ✅ readbacks: at least 1 successful — got 1
