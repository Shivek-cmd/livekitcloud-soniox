# Scenario: delivery_split_phone

- channel: phone
- model: gpt-4.1-mini
- result: PASS

## Transcript

**SIERRA (greeting):** Hi! I'm Sierra, your virtual assistant. I speak English, Hindi, and Punjabi. How can I help you?

**USER:** Hello, one dal makhani and two butter naan please.
> `add_item({"item_query": "dal makhani", "quantity": 1})` → ADDED: 1 x ਦਾਲ ਮੱਖਣੀ (Dal Makhani). ⏎ ORDER NOW: 1 x ਦਾਲ ਮੱਖਣੀ (Dal Makhani). total=$15.99 ⏎ GUIDE: confirm the add in the customer's language — warm and in your own words, never reading these lines aloud — using the exact dish name and quantity above (quantity spoken as "one", never a digit), then keep the order moving.
> `add_item({"item_query": "butter naan", "quantity": 2})` → ADDED: 2 x ਬਟਰ ਨਾਨ (Butter Naan). ⏎ ORDER NOW: 1 x ਦਾਲ ਮੱਖਣੀ (Dal Makhani); 2 x ਬਟਰ ਨਾਨ (Butter Naan). total=$23.97 ⏎ GUIDE: confirm the add in the customer's language — warm and in your own words, never reading these lines aloud — using the exact dish name and quantity above (quantity spoken as "two", never a digit), then keep the order moving.
**SIERRA:** Sure thing — I've got one ਦਾਲ ਮੱਖਣੀ and two ਬਟਰ ਨਾਨ for you. Anything else you'd like with that?

**USER:** Make the dal spicy.
> `set_item_spice({"item_query": "dal makhani", "spice_level": "spicy"})` → SPICE SET: ਦਾਲ ਮੱਖਣੀ is now spicy. ⏎ ORDER NOW: 1 x ਦਾਲ ਮੱਖਣੀ (Dal Makhani) [spicy]; 2 x ਬਟਰ ਨਾਨ (Butter Naan). total=$23.97 ⏎ GUIDE: confirm the spice change in the customer's language, warm and in your own words, then keep the order moving.
**SIERRA:** Got it, I've made the ਦਾਲ ਮੱਖਣੀ spicy for you. Anything else you'd like to add?

**USER:** That's all.
**SIERRA:** Alright, before we finish, do you have any other preferences like spice level for the rest, allergies, or special instructions for the kitchen?

**USER:** Nope, no allergies, nothing else.
> `record_additional_requests({"response": "no"})` → ADDITIONAL REQUESTS RECORDED: none. ⏎ ORDER NOW: 1 x ਦਾਲ ਮੱਖਣੀ (Dal Makhani) [spicy]; 2 x ਬਟਰ ਨਾਨ (Butter Naan). total=$23.97 ⏎ GUIDE: acknowledge warmly in the customer's language, in your own words — do NOT re-ask about spice or allergies — then keep the order moving (pickup or delivery next if not set yet).
**SIERRA:** Great, no special requests noted. Will this order be for pickup or delivery?

**USER (reactive):** Delivery please.
**SIERRA:** Sure thing, could you please provide the delivery address?

**USER (reactive):** It's 12 Main Street, Brampton.
> `set_delivery_address({"address": "12 Main Street, Brampton"})` → Delivery address saved: 12 Main Street, Brampton.
**SIERRA:** Thanks for that. May I have your name for the order?

**USER:** Navdeep.
> `set_customer_contact({"name": "Navdeep"})` → NAME SAVED: "Navdeep". ⏎ GUIDE: confirm the name briefly in the customer's language. Then ask for their phone number.
**SIERRA:** Thanks, Navdeep. Could you please share your phone number as well?

**USER:** Six four seven five five five...
**SIERRA:** Sorry, one more time for the phone number, please?

**USER:** Sorry — six four seven five five five one two one two.
> `set_customer_contact({"phone": "6475551212"})` → PHONE SAVED: six, four, seven, five, five, five, one, two, one, two. ⏎ GUIDE: the number is already saved — do NOT ask the customer to repeat or re-say it. Confirm it back once yourself, speaking it as English word digits exactly as in PHONE SAVED (never numerals, never Punjabi/Hindi number words), then continue the order.
> `get_order_readback({})` → Cannot read back yet: ⏎ - Pickup or delivery has not been set — ask and call set_order_type.
**SIERRA:** Sorry, I need to confirm if this is for pickup or delivery before reading back. You mentioned delivery earlier, right? Should I set it as delivery?

**USER (reactive):** Delivery please.
> `set_order_type({"order_type": "delivery"})` → Set to delivery. INTERNAL: delivery charge applies — do NOT mention price unless the customer asked. Ask for the delivery address.
**SIERRA:** Thanks for confirming delivery. Just to double-check, is the delivery address still 12 Main Street, Brampton?

**USER (reactive):** It's 12 Main Street, Brampton.
> `get_order_readback({})` → READ THIS BACK VERBATIM, then wait for the customer's yes: ⏎ "Okay Navdeep ji — one ਦਾਲ ਮੱਖਣੀ (spicy) and two ਬਟਰ ਨਾਨ, delivery. All good?"
**SIERRA:** Okay Navdeep ji — one ਦਾਲ ਮੱਖਣੀ (spicy) and two ਬਟਰ ਨਾਨ, delivery. All good?

**USER:** Yes, that's right.
> `confirm_readback({})` → Read-back confirmed. Call place_order now.
> `place_order({})` → Order placed! INTERNAL total $28.97. Tell customer: "ਤੁਹਾਡਾ ਆਰਡਰ ਮਿਲ ਗਿਆ ਜੀ! 30-40 ਮਿੰਟ ਵਿੱਚ ਤਿਆਰ ਹੋ ਜਾਵੇਗਾ। ਬਹੁਤ ਬਹੁਤ ਧੰਨਵਾਦ ਜੀ!" Do NOT mention price or dollars.
**SIERRA:** ਤੁਹਾਡਾ ਆਰਡਰ ਮਿਲ ਗਿਆ ਜੀ! 30-40 ਮਿੰਟ ਵਿੱਚ ਤਿਆਰ ਹੋ ਜਾਵੇਗਾ। ਬਹੁਤ ਬਹੁਤ ਧੰਨਵਾਦ ਜੀ!

**USER:** Yes.
**SIERRA:** If you need anything else later, just give us a call. Have a great day!

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
  "order_id": "FWKFY1PS2DAFE"
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
- ✅ additional_requests_recorded — got True
- ✅ readbacks: at least 1 successful — got 1
