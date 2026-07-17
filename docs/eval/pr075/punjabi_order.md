# Scenario: punjabi_order

- channel: phone
- model: gpt-4.1-mini
- result: PASS

## Transcript

**SIERRA (greeting):** Hi! I'm Sierra, your virtual assistant. I speak English, Hindi, and Punjabi. How can I help you?

**USER:** ਸਤ ਸ੍ਰੀ ਅਕਾਲ ਜੀ, ਦੋ ਬਟਰ ਚਿਕਨ ਲਗਾ ਦਿਓ।
> `add_item({"item_query": "Butter Chicken", "quantity": 2, "spice_level": "medium"})` → ADDED: 2 x Butter Chicken, note: medium. ⏎ ORDER NOW: 2 x Butter Chicken [medium]. total=$39.98 ⏎ GUIDE: confirm the add briefly in the customer's language using the exact dish name and quantity above (quantity spoken as "two", never a digit), then keep the order moving.
**SIERRA:** ਦੋ ਬਟਰ ਚਿਕਨ medium spice ਨਾਲ ਜੋੜ ਦਿੱਤੇ। ਹੋਰ ਕੁਝ?

**USER:** ਮੀਡੀਅਮ ਠੀਕ ਹੈ ਜੀ।
**SIERRA:** ਹੋਰ ਕੁਝ ਚਾਹੀਦਾ ਹੈ?

**USER:** ਬੱਸ ਜੀ, ਹੋਰ ਕੁਝ ਨਹੀਂ।
**SIERRA:** ਕੋਈ allergy ਤਾਂ ਨਹੀਂ?

**USER:** ਨਹੀਂ ਜੀ, ਕੋਈ ਐਲਰਜੀ ਨਹੀਂ।
> `record_allergies({"response": "no"})` → Allergies recorded: none. Continue — pickup or delivery?
**SIERRA:** pickup ਕਰਨਾ ਹੈ ਜਾਂ delivery?

**USER:** Pickup ਜੀ।
> `set_order_type({"order_type": "pickup"})` → Set to pickup. Continue the flow.
**SIERRA:** ਆਪਣਾ ਨਾਮ ਦੱਸੋ ਜੀ।

**USER:** ਮੇਰਾ ਨਾਮ Gurpreet ਹੈ।
> `set_customer_contact({"name": "Gurpreet"})` → Name saved: "Gurpreet".
**SIERRA:** ਫੋਨ ਨੰਬਰ ਦੱਸੋ ਜੀ।

**USER:** Six four seven five five five three four five six.
> `set_customer_contact({"phone": "6475553456"})` → Phone saved. Read it back as English word digits ONLY: "six, four, seven, five, five, five, three, four, five, six".
**SIERRA:** Your phone number is six, four, seven, five, five, five, three, four, five, six. Is that correct?

**USER (reactive):** Yes.
> `get_order_readback({})` → READ THIS BACK VERBATIM, then wait for the customer's yes: ⏎ "Okay Gurpreet ji — two Butter Chicken (medium), pickup. All good?"
**SIERRA:** Okay Gurpreet ji — two Butter Chicken (medium), pickup. All good?

**USER:** ਹਾਂ ਜੀ, ਬਿਲਕੁਲ ਠੀਕ ਹੈ।
> `confirm_readback({})` → Read-back confirmed. Call place_order now.
> `place_order({})` → Order placed! INTERNAL total $39.98. Tell customer: "ਤੁਹਾਡਾ ਆਰਡਰ ਮਿਲ ਗਿਆ ਜੀ। 20-25 ਮਿੰਟ ਵਿੱਚ ਤਿਆਰ ਹੋ ਜਾਵੇਗਾ। ਧੰਨਵਾਦ ਜੀ!" Do NOT mention price or dollars.
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
    }
  ],
  "order_type": "pickup",
  "delivery_address": null,
  "customer": {
    "name": "Gurpreet",
    "phone": "6475553456"
  },
  "subtotal": 39.98,
  "delivery_charge": 0,
  "total": 39.98,
  "eta": "20-25 min",
  "order_id": "S29AHQGTXG1SG"
}
```

## Assertions

- ✅ gates: placed order had a confirmed, current readback — readback_confirmed=True readback_revision=2 cart.revision=2
- ✅ placed — cart.placed=True
- ✅ items: exact set of dishes — cart=['Butter Chicken']
- ✅ items: Butter Chicken qty == 2 — got qty=2
- ✅ items: Butter Chicken note contains 'medium' — got note='medium'
- ✅ order_type — got 'pickup'
- ✅ customer_name — got 'Gurpreet'
- ✅ customer_phone — got '6475553456'
- ✅ allergies_recorded — got True
- ✅ readbacks: at least 1 successful — got 1
