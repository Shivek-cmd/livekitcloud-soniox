# Scenario: ambiguous_fish

- channel: phone
- model: gpt-4.1-mini
- result: PASS

## Transcript

**SIERRA (greeting):** Hi! I'm Sierra, your virtual assistant. I speak English, Hindi, and Punjabi. How can I help you?

**USER:** Can I get the fish?
> `search_menu({"query": "fish"})` → Browse result for 'fish' (mention at most TWO in ONE casual sentence — never a numbered list): Amritsari Fish Pakora → say "Fish Pakora" | Punjabi Fish Curry → say "Punjabi Fish Curry". Good: "ਹਾਂ ਜੀ, ਸਾਡੇ ਕੋਲ X ਤੇ Y ਹੈ — ਕਿਹੜਾ?" Bad: "1 X, 2 Y" or "first X, second Y". Ask which they would like.
**SIERRA:** ਹਾਂ ਜੀ, ਸਾਡੇ ਕੋਲ Fish Pakora ਤੇ Punjabi Fish Curry ਹੈ — ਕਿਹੜਾ ਚਾਹੁੰਦੇ ਹੋ?

**USER:** The fish pakora please.
**SIERRA:** Spice level? Mild, medium, or spicy?

**USER:** Medium.
> `add_item({"item_query": "Fish Pakora", "quantity": 1, "spice_level": "medium"})` → ADDED: 1 x Fish Pakora (Amritsari Fish Pakora), note: medium. ⏎ ORDER NOW: 1 x Fish Pakora (Amritsari Fish Pakora) [medium]. total=$14.99 ⏎ GUIDE: confirm the add briefly in the customer's language using the exact dish name and quantity above (quantity spoken as "one", never a digit), then keep the order moving.
**SIERRA:** One Fish Pakora medium added, anything else?

**USER:** That's it for now.
**SIERRA:** Any allergies I should know about?

## Final cart

```json
{
  "v": 1,
  "status": "building",
  "items": [
    {
      "id": "8BGZA0MVS825P",
      "name": "Amritsari Fish Pakora",
      "voice_line": "Fish Pakora",
      "qty": 1,
      "unit_price": 14.99,
      "line_total": 14.99,
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
  "subtotal": 14.99,
  "delivery_charge": 0,
  "total": 14.99,
  "eta": null,
  "order_id": null
}
```

## Assertions

- ✅ placed — cart.placed=False
- ✅ items: exact set of dishes — cart=['Amritsari Fish Pakora']
- ✅ items: Amritsari Fish Pakora qty == 1 — got qty=1
- ✅ transcript never contains 'Punjabi Fish Curry ਅਤੇ'
- ✅ transcript never contains 'both fish'
