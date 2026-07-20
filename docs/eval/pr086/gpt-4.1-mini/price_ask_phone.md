# Scenario: price_ask_phone

- channel: phone
- model: gpt-4.1-mini
- result: PASS

## Transcript

**SIERRA (greeting):** Hi! I'm Sierra, your virtual assistant. I speak English, Hindi, and Punjabi. How can I help you?

**USER:** One butter chicken please, medium.
> `add_item({"item_query": "butter chicken", "quantity": 1, "spice_level": "medium"})` → ADDED: 1 x Butter Chicken, note: medium. ⏎ ORDER NOW: 1 x Butter Chicken [medium]. total=$19.99 ⏎ GUIDE: confirm the add in the customer's language — warm and in your own words, never reading these lines aloud — using the exact dish name and quantity above (quantity spoken as "one", never a digit), then keep the order moving.
**SIERRA:** Sure thing, I've got one Butter Chicken with medium spice for you. Anything else you'd like to add?

**USER:** How much will that be?
**SIERRA:** The Butter Chicken is nineteen dollars and ninety-nine cents. Would you like to add anything else to your order?

**USER:** Okay, that's all I need for now, thanks.
> `record_additional_requests({"response": "no"})` → ADDITIONAL REQUESTS RECORDED: none. ⏎ ORDER NOW: 1 x Butter Chicken [medium]. total=$19.99 ⏎ GUIDE: acknowledge warmly in the customer's language, in your own words — do NOT re-ask about spice or allergies — then keep the order moving (pickup or delivery next if not set yet).
**SIERRA:** Alright, no special requests then. Would you like to pick up your order or have it delivered?

## Final cart

```json
{
  "v": 1,
  "status": "building",
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
  "order_type": null,
  "delivery_address": null,
  "customer": {
    "name": null,
    "phone": null
  },
  "subtotal": 19.99,
  "delivery_charge": 0,
  "total": 19.99,
  "eta": null,
  "order_id": null
}
```

## Assertions

- ✅ placed — cart.placed=False
- ✅ items: exact set of dishes — cart=['Butter Chicken']
- ✅ items: Butter Chicken qty == 1 — got qty=1
- ✅ items: Butter Chicken note contains 'medium' — got note='medium'
