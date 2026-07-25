# Scenario: ambiguous_fish

- channel: phone
- model: gemini-3.5-flash
- result: PASS

## Transcript

**SIERRA (greeting):** Hi! I'm Sierra, your virtual assistant. I speak English, Hindi, and Punjabi. How can I help you?

**USER:** Can I get the fish?
> `search_menu({"query": "fish"})` → Browse result for 'fish' (mention at most TWO in ONE casual sentence — never a numbered list): Amritsari Fish Pakora → say "Fish Pakora" | Punjabi Fish Curry → say "Punjabi Fish Curry". Good: "ਹਾਂ ਜੀ, ਸਾਡੇ ਕੋਲ X ਤੇ Y ਹੈ — ਕਿਹੜਾ?" Bad: "1 X, 2 Y" or "first X, second Y". Ask which they would like.
**SIERRA:** We have the Fish Pakora and the Punjabi Fish Curry. Which one of those sounds good to you?

**USER:** The fish pakora please.
> `add_item({"quantity": 1, "item_query": "Fish Pakora"})` → ⛔ NOTHING WAS ADDED — CART UNCHANGED. NEEDS SPICE — Amritsari Fish Pakora comes Mild, Medium, Spicy or Extra Spicy. Ask the customer which they want ('no preference' = Medium), then re-call add_item with spice_level. If other dishes in this turn also need one, ask about them in the SAME question, then re-call add_item once per dish.
**SIERRA:** Sure thing! How would you like the spice level for your Fish Pakora — mild, medium, spicy, or extra spicy?

**USER:** Medium is fine.
> `add_item({"spice_level": "Medium", "item_query": "Fish Pakora", "quantity": 1})` → ADDED: 1 x Fish Pakora (Amritsari Fish Pakora), note: medium. ⏎ ORDER NOW: 1 x Fish Pakora (Amritsari Fish Pakora) [medium]. total=$14.99 ⏎ GUIDE: confirm the add in the customer's language — warm and in your own words, never reading these lines aloud — using the exact dish name and quantity above (quantity spoken as "one", never a digit), then keep the order moving.
**SIERRA:** Got it, one Fish Pakora, medium. What else can I get started for you today?

**USER:** That's it for now.
> `record_additional_requests({"response": "no"})` → ADDITIONAL REQUESTS RECORDED: none. ⏎ ORDER NOW: 1 x Fish Pakora (Amritsari Fish Pakora) [medium]. total=$14.99 ⏎ GUIDE: acknowledge warmly in the customer's language, in your own words — do NOT re-ask about allergies, and never re-ask spice (it was settled per dish at add time) — then keep the order moving (pickup or delivery next if not set yet).
**SIERRA:** Perfect. Will this order be for pickup or delivery today?

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
