# Scenario: price_ask_phone

- channel: phone
- model: gpt-4.1-mini
- result: PASS

## Transcript

**SIERRA (greeting):** Hi! I'm Sierra, your virtual assistant. I speak English, Hindi, and Punjabi. How can I help you?

**USER:** One butter chicken please, medium.
> `add_item({"item_query": "butter chicken", "quantity": 1, "spice_level": "medium"})` → INTERNAL: item saved. ⏎ SAY EXACTLY: "Yes — one Butter Chicken." ⏎ Do NOT mention price, cart, menu, pieces, or say I can add / I've added.
**SIERRA:** Yes — one Butter Chicken. Anything else?

**USER:** How much will that be?
**SIERRA:** I can share the price if you want, but first, would you like to add anything else to your order?

**USER:** Okay, that's all I need for now, thanks.
**SIERRA:** Any allergies I should know about?

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
