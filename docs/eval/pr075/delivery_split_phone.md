# Scenario: delivery_split_phone

- channel: phone
- model: gpt-4.1-mini
- result: PASS

## Transcript

**SIERRA (greeting):** Hi! I'm Sierra, your virtual assistant. I speak English, Hindi, and Punjabi. How can I help you?

**USER:** Hello, one dal makhani and two butter naan please.
> `add_item({"item_query": "dal makhani", "quantity": 1, "spice_level": "medium"})` → ADDED: 1 x ਦਾਲ ਮੱਖਣੀ (Dal Makhani), note: medium. ⏎ ORDER NOW: 1 x ਦਾਲ ਮੱਖਣੀ (Dal Makhani) [medium]. total=$15.99 ⏎ GUIDE: confirm the add briefly in the customer's language using the exact dish name and quantity above (quantity spoken as "one", never a digit), then keep the order moving.
> `add_item({"item_query": "butter naan", "quantity": 2})` → ADDED: 2 x ਬਟਰ ਨਾਨ (Butter Naan). ⏎ ORDER NOW: 1 x ਦਾਲ ਮੱਖਣੀ (Dal Makhani) [medium]; 2 x ਬਟਰ ਨਾਨ (Butter Naan). total=$23.97 ⏎ GUIDE: confirm the add briefly in the customer's language using the exact dish name and quantity above (quantity spoken as "two", never a digit), then keep the order moving.
**SIERRA:** One Dal Makhani medium and two Butter Naan, anything else?

**USER:** Make the dal spicy.
> `set_item_spice({"item_query": "dal makhani", "spice_level": "spicy"})` → SPICE SET: ਦਾਲ ਮੱਖਣੀ is now spicy. ⏎ ORDER NOW: 1 x ਦਾਲ ਮੱਖਣੀ (Dal Makhani) [spicy]; 2 x ਬਟਰ ਨਾਨ (Butter Naan). total=$23.97 ⏎ GUIDE: confirm the spice change briefly in the customer's language, then keep the order moving.
**SIERRA:** Dal Makhani is now spicy, anything else?

**USER:** That's all.
**SIERRA:** Any allergies I should know about?

**USER:** Nope, no allergies.
> `record_allergies({"response": "no"})` → Allergies recorded: none. Continue — pickup or delivery?
**SIERRA:** Pickup or delivery?

**USER (reactive):** Delivery please.
**SIERRA:** Please tell me your delivery address.

**USER (reactive):** It's 12 Main Street, Brampton.
> `set_delivery_address({"address": "12 Main Street, Brampton"})` → Delivery address saved: 12 Main Street, Brampton.
**SIERRA:** May I have your name for the order?

**USER:** Navdeep.
> `set_customer_contact({"name": "Navdeep"})` → Name saved: "Navdeep".
**SIERRA:** Please provide your phone number.

**USER:** Six four seven five five five...
**SIERRA:** Please say the full phone number.

**USER:** Sorry — six four seven five five five one two one two.
> `set_customer_contact({"phone": "6475551212"})` → Phone saved. Read it back as English word digits ONLY: "six, four, seven, five, five, five, one, two, one, two".
> `get_order_readback({})` → Cannot read back yet: ⏎ - Pickup or delivery has not been set — ask and call set_order_type.
**SIERRA:** Is this order for pickup or delivery?

**USER (reactive):** Delivery please.
> `set_order_type({"order_type": "delivery"})` → Set to delivery. INTERNAL: delivery charge applies — do NOT mention price unless the customer asked. Ask for the delivery address.
**SIERRA:** You already gave the delivery address as 12 Main Street, Brampton. Should I proceed with the order?

**USER (reactive):** It's 12 Main Street, Brampton.
> `get_order_readback({})` → READ THIS BACK VERBATIM, then wait for the customer's yes: ⏎ "Okay Navdeep ji — one ਦਾਲ ਮੱਖਣੀ (spicy) and two ਬਟਰ ਨਾਨ, delivery. All good?"
**SIERRA:** Okay Navdeep ji — one ਦਾਲ ਮੱਖਣੀ (spicy) and two ਬਟਰ ਨਾਨ, delivery. All good?

**USER:** Yes, that's right.
> `confirm_readback({})` → Read-back confirmed. Call place_order now.
> `place_order({})` → Order placed! INTERNAL total $28.97. Tell customer: "ਤੁਹਾਡਾ ਆਰਡਰ ਮਿਲ ਗਿਆ ਜੀ। 30-40 ਮਿੰਟ ਵਿੱਚ ਤਿਆਰ ਹੋ ਜਾਵੇਗਾ। ਧੰਨਵਾਦ ਜੀ!" Do NOT mention price or dollars.
**SIERRA:** ਤੁਹਾਡਾ ਆਰਡਰ ਮਿਲ ਗਿਆ ਜੀ। 30-40 ਮਿੰਟ ਵਿੱਚ ਤਿਆਰ ਹੋ ਜਾਵੇਗਾ। ਧੰਨਵਾਦ ਜੀ!

**USER:** Yes.
**SIERRA:** Sure, let me connect you — one moment.

## Final cart

```json
{
  "v": 1,
  "status": "placed",
  "items": [
    {
      "id": "NXGWYTWSNNHCG",
      "name": "Dal Makhani",
      "voice_line": "ਦਾਲ ਮੱਖਣੀ",
      "qty": 1,
      "unit_price": 15.99,
      "line_total": 15.99,
      "note": "spicy",
      "modifiers": [
        "spicy"
      ]
    },
    {
      "id": "8BQQ63MMZDSMG",
      "name": "Butter Naan",
      "voice_line": "ਬਟਰ ਨਾਨ",
      "qty": 2,
      "unit_price": 3.99,
      "line_total": 7.98,
      "note": "",
      "modifiers": []
    }
  ],
  "order_type": "delivery",
  "delivery_address": "12 Main Street, Brampton",
  "customer": {
    "name": "Navdeep",
    "phone": "6475551212"
  },
  "subtotal": 23.97,
  "delivery_charge": 5,
  "total": 28.97,
  "eta": "30-40 min",
  "order_id": "ZZQ8ZC6HVVYJW"
}
```

## Assertions

- ✅ gates: placed order had a confirmed, current readback — readback_confirmed=True readback_revision=4 cart.revision=4
- ✅ placed — cart.placed=True
- ✅ items: exact set of dishes — cart=['Butter Naan', 'Dal Makhani']
- ✅ items: Dal Makhani qty == 1 — got qty=1
- ✅ items: Dal Makhani note contains 'spicy' — got note='spicy'
- ✅ items: Butter Naan qty == 2 — got qty=2
- ✅ order_type — got 'delivery'
- ✅ customer_name — got 'Navdeep'
- ✅ customer_phone — got '6475551212'
- ✅ allergies_recorded — got True
- ✅ readbacks: at least 1 successful — got 1
