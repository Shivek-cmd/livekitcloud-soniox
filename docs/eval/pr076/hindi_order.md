# Scenario: hindi_order

- channel: phone
- model: gpt-4.1-mini
- result: PASS

## Transcript

**SIERRA (greeting):** Hi! I'm Sierra, your virtual assistant. I speak English, Hindi, and Punjabi. How can I help you?

**USER:** नमस्ते, एक पनीर टिक्का और एक गुलाब जामुन चाहिए।
> `add_item({"item_query": "Paneer Tikka", "quantity": 1})` → ADDED: 1 x Paneer Tikka. ⏎ ORDER NOW: 1 x Paneer Tikka. total=$16.99 ⏎ GUIDE: confirm the add briefly in the customer's language using the exact dish name and quantity above (quantity spoken as "one", never a digit), then keep the order moving.
> `add_item({"item_query": "Gulab Jamun", "quantity": 1})` → ADDED: 1 x ਗੁਲਾਬ ਜਾਮੁਨ (Gulab Jamun (2 pcs)). ⏎ ORDER NOW: 1 x Paneer Tikka; 1 x ਗੁਲਾਬ ਜਾਮੁਨ (Gulab Jamun (2 pcs)). total=$22.98 ⏎ GUIDE: confirm the add briefly in the customer's language using the exact dish name and quantity above (quantity spoken as "one", never a digit), then keep the order moving.
**SIERRA:** एक पनीर टिक्का और एक ਗੁਲਾਬ ਜਾਮੁਨ (Gulab Jamun) ਇੱਕ-ਇੱਕ ਕਰਕੇ ਜੋੜ ਦਿੱਤੇ। ਹੋਰ ਕੁਝ ਚਾਹੀਦਾ?

**USER:** बस, और कुछ नहीं।
**SIERRA:** ਕਿਰਪਾ ਕਰਕੇ ਦੱਸੋ, ਮਸਾਲਾ ਕਿਵੇਂ ਚਾਹੀਦਾ ਹੈ? ਕੋਈ ਐਲਰਜੀ ਜਾਂ ਹੋਰ ਖਾਸ ਹਦਾਇਤਾਂ ਹਨ?

**USER:** मीडियम ठीक है, कोई एलर्जी नहीं।
> `record_additional_requests({"response": "Medium spice, no allergies, no special instructions"})` → ADDITIONAL REQUESTS RECORDED for the kitchen: "Medium spice, no allergies, no special instructions". ⏎ SPICE DEFAULTED: Paneer Tikka set to medium (no preference stated — use set_item_spice if the customer actually named a level). ⏎ ORDER NOW: 1 x Paneer Tikka [medium]; 1 x ਗੁਲਾਬ ਜਾਮੁਨ (Gulab Jamun (2 pcs)). total=$22.98 ⏎ GUIDE: acknowledge briefly in the customer's language — do NOT re-ask about spice or allergies — then keep the order moving (pickup or delivery next if not set yet).
**SIERRA:** ਮਧ्यम ਮਸਾਲਾ ਤੇ ਕੋਈ ਐਲਰਜੀ ਨਹੀਂ ਨੋਟ ਕਰ ਲਈ। ਪਿਕਅਪ ਕਰਨਾ ਹੈ ਜਾਂ ਡਿਲਿਵਰੀ?

**USER:** Pickup कर लूंगा।
> `set_order_type({"order_type": "pickup"})` → Set to pickup. Continue the flow.
**SIERRA:** ਕਿਰਪਾ ਕਰਕੇ ਆਪਣਾ ਨਾਮ ਦੱਸੋ ਜੀ।

**USER:** मेरा नाम Rohan है।
> `set_customer_contact({"name": "Rohan"})` → NAME SAVED: "Rohan". ⏎ GUIDE: confirm the name briefly in the customer's language. Then ask for their phone number.
**SIERRA:** ठीक है, Rohan ਜੀ। ਹੁਣ ਕਿਰਪਾ ਕਰਕੇ ਆਪਣਾ ਫੋਨ ਨੰਬਰ ਦੱਸੋ।

**USER:** Four one six five five five seven eight nine zero.
> `set_customer_contact({"phone": "4165557890"})` → PHONE SAVED: four, one, six, five, five, five, seven, eight, nine, zero. ⏎ GUIDE: the number is already saved — do NOT ask the customer to repeat or re-say it. Confirm it back once yourself, speaking it as English word digits exactly as in PHONE SAVED (never numerals, never Punjabi/Hindi number words), then continue the order.
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
  "order_id": "RTSCD739MGNC2"
}
```

## Assertions

- ✅ gates: placed order had a confirmed, current readback — readback_confirmed=True readback_revision=4 cart.revision=4
- ✅ placed — cart.placed=True
- ✅ items: exact set of dishes — cart=['Gulab Jamun (2 pcs)', 'Paneer Tikka']
- ✅ items: Paneer Tikka qty == 1 — got qty=1
- ✅ items: Paneer Tikka note contains 'medium' — got note='medium'
- ✅ items: Gulab Jamun (2 pcs) qty == 1 — got qty=1
- ✅ order_type — got 'pickup'
- ✅ customer_name — got 'Rohan'
- ✅ customer_phone — got '4165557890'
- ✅ additional_requests_recorded — got True
- ✅ readbacks: at least 1 successful — got 1
