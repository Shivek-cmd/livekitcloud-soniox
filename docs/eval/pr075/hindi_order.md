# Scenario: hindi_order

- channel: phone
- model: gpt-4.1-mini
- result: PASS

## Transcript

**SIERRA (greeting):** Hi! I'm Sierra, your virtual assistant. I speak English, Hindi, and Punjabi. How can I help you?

**USER:** नमस्ते, एक पनीर टिक्का और एक गुलाब जामुन चाहिए।
> `add_item({"item_query": "paneer tikka", "quantity": 1, "spice_level": "medium"})` → ADDED: 1 x Paneer Tikka, note: medium. ⏎ ORDER NOW: 1 x Paneer Tikka [medium]. total=$16.99 ⏎ GUIDE: confirm the add briefly in the customer's language using the exact dish name and quantity above (quantity spoken as "one", never a digit), then keep the order moving.
> `add_item({"item_query": "gulab jamun", "quantity": 1})` → ADDED: 1 x ਗੁਲਾਬ ਜਾਮੁਨ (Gulab Jamun (2 pcs)). ⏎ ORDER NOW: 1 x Paneer Tikka [medium]; 1 x ਗੁਲਾਬ ਜਾਮੁਨ (Gulab Jamun (2 pcs)). total=$22.98 ⏎ GUIDE: confirm the add briefly in the customer's language using the exact dish name and quantity above (quantity spoken as "one", never a digit), then keep the order moving.
**SIERRA:** जी, एक पनीर टिक्का और एक गुलाब जामुन जोड़ दिए। कुछ और चाहिए?

**USER:** मीडियम ठीक है।
**SIERRA:** ਹਾਂ ਜੀ, ਮੀਡਿਅਮ ਮਸਾਲਾ ਨਾਲ ਪਨੀਰ ਟਿੱਕਾ ਹੈ। ਹੋਰ ਕੁਝ ਚਾਹੀਦਾ?

**USER:** बस, और कुछ नहीं।
**SIERRA:** ਕੋਈ ਐਲਰਜੀ ਤਾਂ ਨਹੀਂ?

**USER:** नहीं, कोई एलर्जी नहीं है।
> `record_allergies({"response": "no"})` → Allergies recorded: none. Continue — pickup or delivery?
**SIERRA:** Pickup ਕਰਨਾ ਹੈ ਜਾਂ delivery?

**USER:** Pickup कर लूंगा।
> `set_order_type({"order_type": "pickup"})` → Set to pickup. Continue the flow.
**SIERRA:** ਤੁਹਾਡਾ ਨਾਮ ਕੀ ਹੈ ਜੀ?

**USER:** मेरा नाम Rohan है।
> `set_customer_contact({"name": "Rohan"})` → Name saved: "Rohan".
**SIERRA:** ਫੋਨ ਨੰਬਰ ਦੱਸੋ ਜੀ।

**USER:** Four one six five five five seven eight nine zero.
> `set_customer_contact({"phone": "4165557890"})` → Phone saved. Read it back as English word digits ONLY: "four, one, six, five, five, five, seven, eight, nine, zero".
**SIERRA:** Your phone number is four, one, six, five, five, five, seven, eight, nine, zero. Shall I read back your order now?

**USER (reactive):** Yes.
> `get_order_readback({})` → READ THIS BACK VERBATIM, then wait for the customer's yes: ⏎ "Okay Rohan ji — one Paneer Tikka (medium) and one ਗੁਲਾਬ ਜਾਮੁਨ, pickup. All good?"
**SIERRA:** Okay Rohan ji — one Paneer Tikka (medium) and one ਗੁਲਾਬ ਜਾਮੁਨ, pickup. All good?

**USER:** हाँ, बिल्कुल सही है।
> `confirm_readback({})` → Read-back confirmed. Call place_order now.
> `place_order({})` → Order placed! INTERNAL total $22.979999999999997. Tell customer: "ਤੁਹਾਡਾ ਆਰਡਰ ਮਿਲ ਗਿਆ ਜੀ। 20-25 ਮਿੰਟ ਵਿੱਚ ਤਿਆਰ ਹੋ ਜਾਵੇਗਾ। ਧੰਨਵਾਦ ਜੀ!" Do NOT mention price or dollars.
**SIERRA:** ਤੁਹਾਡਾ ਆਰਡਰ ਮਿਲ ਗਿਆ ਜੀ। 20-25 ਮਿੰਟ ਵਿੱਚ ਤਿਆਰ ਹੋ ਜਾਵੇਗਾ। ਧੰਨਵਾਦ ਜੀ!

## Final cart

```json
{
  "v": 1,
  "status": "placed",
  "items": [
    {
      "id": "M76YYRKJ33MGJ",
      "name": "Paneer Tikka",
      "voice_line": "Paneer Tikka",
      "qty": 1,
      "unit_price": 16.99,
      "line_total": 16.99,
      "note": "medium",
      "modifiers": [
        "medium"
      ]
    },
    {
      "id": "XYCGVQJC48GTT",
      "name": "Gulab Jamun (2 pcs)",
      "voice_line": "ਗੁਲਾਬ ਜਾਮੁਨ",
      "qty": 1,
      "unit_price": 5.99,
      "line_total": 5.99,
      "note": "",
      "modifiers": []
    }
  ],
  "order_type": "pickup",
  "delivery_address": null,
  "customer": {
    "name": "Rohan",
    "phone": "4165557890"
  },
  "subtotal": 22.98,
  "delivery_charge": 0,
  "total": 22.98,
  "eta": "20-25 min",
  "order_id": "86C1S5YHMQNC8"
}
```

## Assertions

- ✅ gates: placed order had a confirmed, current readback — readback_confirmed=True readback_revision=3 cart.revision=3
- ✅ placed — cart.placed=True
- ✅ items: exact set of dishes — cart=['Gulab Jamun (2 pcs)', 'Paneer Tikka']
- ✅ items: Paneer Tikka qty == 1 — got qty=1
- ✅ items: Paneer Tikka note contains 'medium' — got note='medium'
- ✅ items: Gulab Jamun (2 pcs) qty == 1 — got qty=1
- ✅ order_type — got 'pickup'
- ✅ customer_name — got 'Rohan'
- ✅ customer_phone — got '4165557890'
- ✅ allergies_recorded — got True
- ✅ readbacks: at least 1 successful — got 1
