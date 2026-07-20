# Scenario: price_ask_phone

- channel: phone
- model: gemini-3.1-flash-lite
- result: PASS

## Transcript

**SIERRA (greeting):** Hi! I'm Sierra, your virtual assistant. I speak English, Hindi, and Punjabi. How can I help you?

**USER:** One butter chicken please, medium.
> `add_item({"spice_level": "medium", "item_query": "butter chicken", "quantity": 1})` → ADDED: 1 x Butter Chicken, note: medium. ⏎ ORDER NOW: 1 x Butter Chicken [medium]. total=$19.99 ⏎ GUIDE: confirm the add in the customer's language — warm and in your own words, never reading these lines aloud — using the exact dish name and quantity above (quantity spoken as "one", never a digit), then keep the order moving.
**SIERRA:** Sure thing, I've got one Butter Chicken, medium, down for you. Anything else I can get you with that?

**USER:** How much will that be?
> `get_order_summary({})` → ORDER SO FAR (state ONLY these items — never from memory): 1 x Butter Chicken [medium]. total=$19.99 ⏎ GUIDE: state the order conversationally in the customer's language, in your own words, using exactly these dish names and quantities (quantities as words, never digits).
**SIERRA:** That will be $19.99 for the Butter Chicken. Would you like to add anything else to your order?

**USER:** Okay, that's all I need for now, thanks.
> `record_additional_requests({"response": "none"})` → ADDITIONAL REQUESTS RECORDED: none. ⏎ ORDER NOW: 1 x Butter Chicken [medium]. total=$19.99 ⏎ GUIDE: acknowledge warmly in the customer's language, in your own words — do NOT re-ask about spice or allergies — then keep the order moving (pickup or delivery next if not set yet).
**SIERRA:** Got it. Would you like to pick that up, or would you like us to deliver it to you?

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
