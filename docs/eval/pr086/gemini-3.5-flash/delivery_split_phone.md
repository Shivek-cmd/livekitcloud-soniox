# Scenario: delivery_split_phone

- channel: phone
- model: gemini-3.5-flash
- result: FAIL

## Transcript

**SIERRA (greeting):** Hi! I'm Sierra, your virtual assistant. I speak English, Hindi, and Punjabi. How can I help you?

**USER:** Hello, one dal makhani and two butter naan please.
> `add_item({"quantity": 1, "item_query": "dal makhani"})` → ADDED: 1 x ਦਾਲ ਮੱਖਣੀ (Dal Makhani). ⏎ ORDER NOW: 1 x ਦਾਲ ਮੱਖਣੀ (Dal Makhani). total=$15.99 ⏎ GUIDE: confirm the add in the customer's language — warm and in your own words, never reading these lines aloud — using the exact dish name and quantity above (quantity spoken as "one", never a digit), then keep the order moving.
> `add_item({"quantity": 2, "item_query": "butter naan"})` → ADDED: 2 x ਬਟਰ ਨਾਨ (Butter Naan). ⏎ ORDER NOW: 1 x ਦਾਲ ਮੱਖਣੀ (Dal Makhani); 2 x ਬਟਰ ਨਾਨ (Butter Naan). total=$23.97 ⏎ GUIDE: confirm the add in the customer's language — warm and in your own words, never reading these lines aloud — using the exact dish name and quantity above (quantity spoken as "two", never a digit), then keep the order moving.
**SIERRA:** You got it — I've added one Dal Makhani and two Butter Naan to your order. Is there anything else I can get for you today?

**USER:** Make the dal spicy.
> `set_item_spice({"item_query": "dal makhani", "spice_level": "spicy"})` → SPICE SET: ਦਾਲ ਮੱਖਣੀ is now spicy. ⏎ ORDER NOW: 1 x ਦਾਲ ਮੱਖਣੀ (Dal Makhani) [spicy]; 2 x ਬਟਰ ਨਾਨ (Butter Naan). total=$23.97 ⏎ GUIDE: confirm the spice change in the customer's language, warm and in your own words, then keep the order moving.
**SIERRA:** You got it, I've made the Dal Makhani spicy for you. What else can I get started for you?

**USER:** That's all.
> `record_additional_requests({"response": "no other requests"})` → ADDITIONAL REQUESTS RECORDED for the kitchen: "no other requests". ⏎ ORDER NOW: 1 x ਦਾਲ ਮੱਖਣੀ (Dal Makhani) [spicy]; 2 x ਬਟਰ ਨਾਨ (Butter Naan). total=$23.97 ⏎ GUIDE: acknowledge warmly in the customer's language, in your own words — do NOT re-ask about spice or allergies — then keep the order moving (pickup or delivery next if not set yet).
**SIERRA:** Perfect. Will this order be for pickup or delivery today?

**USER (reactive):** Delivery please.
> `set_order_type({"order_type": "delivery"})` → Set to delivery. INTERNAL: delivery charge applies — do NOT mention price unless the customer asked. Ask for the delivery address.
**SIERRA:** Sure thing, delivery it is. Could you please provide your delivery address?

**USER (reactive):** It's 12 Main Street, Brampton.
> `set_delivery_address({"address": "12 Main Street, Brampton"})` → Delivery address saved: 12 Main Street, Brampton.
**SIERRA:** Got it, I've saved that address. Can I get your name for the order, please?

**USER (reactive):** It's 12 Main Street, Brampton.
**SIERRA:** Got it, I have the address as 12 Main Street, Brampton. Could I just get your name for the order, please?

**USER:** Nope, no allergies, nothing else.
**SIERRA:** No problem at all. Could I just get your name so we know who the order is for?

**USER:** Navdeep.
**SIERRA:** 
**ERROR:** LLM call failed after retries: completion had no message

**USER:** Six four seven five five five...
> `set_customer_contact({"name": "Navdeep"})` → NAME SAVED: "Navdeep". ⏎ GUIDE: confirm the name briefly in the customer's language. Then ask for their phone number.
**SIERRA:** Thanks, Navdeep. And what is the best phone number to reach you at?

**USER:** Sorry — six four seven five five five one two one two.
> `set_customer_contact({"phone": "6475551212"})` → PHONE SAVED: six, four, seven, five, five, five, one, two, one, two. ⏎ GUIDE: the number is already saved — do NOT ask the customer to repeat or re-say it. Confirm it back once yourself, speaking it as English word digits exactly as in PHONE SAVED (never numerals, never Punjabi/Hindi number words), then continue the order.
> `get_order_readback({})` → READBACK FACTS — read ALL of these to the customer in their language, then ask if everything is correct: ⏎ - 1 x ਦਾਲ ਮੱਖਣੀ (Dal Makhani) [spicy] ⏎ - 2 x ਬਟਰ ਨਾਨ (Butter Naan) ⏎ - order type: delivery (say "delivery" in English) ⏎ - name: Navdeep ⏎ GUIDE: phrase this warmly in your own words in the customer's language — but every item, its quantity (as a word, never a digit), and the order type must actually be spoken. Your spoken readback is checked — anything missing forces a re-read. End by asking if everything is correct.
**SIERRA:** Alright, Navdeep, I've got your phone number down as six, four, seven, five, five, five, one, two, one, two. 

Let me read your order back to make sure everything is correct:
- We have one Dal Makhani, made spicy,
- and two Butter Naan.
- This is for delivery to 12 Main Street, Brampton, under the name Navdeep.

Does that all sound correct to you?

**USER (reactive):** Delivery please.
> `get_order_readback({})` → READBACK FACTS — read ALL of these to the customer in their language, then ask if everything is correct: ⏎ - 1 x ਦਾਲ ਮੱਖਣੀ (Dal Makhani) [spicy] ⏎ - 2 x ਬਟਰ ਨਾਨ (Butter Naan) ⏎ - order type: delivery (say "delivery" in English) ⏎ - name: Navdeep ⏎ GUIDE: phrase this warmly in your own words in the customer's language — but every item, its quantity (as a word, never a digit), and the order type must actually be spoken. Your spoken readback is checked — anything missing forces a re-read. End by asking if everything is correct.
**SIERRA:** Yes, we have it set for delivery. 

Just to confirm everything one more time:
- One Dal Makhani, spicy,
- and two Butter Naan.
- This is for delivery under the name Navdeep.

Is all of that correct?

**USER:** Yes, that's right.
> `confirm_readback({})` → Read-back confirmed. Call place_order now.
> `place_order({})` → Order placed! INTERNAL total $28.97. Tell customer: "ਤੁਹਾਡਾ ਆਰਡਰ ਮਿਲ ਗਿਆ ਜੀ! 30-40 ਮਿੰਟ ਵਿੱਚ ਤਿਆਰ ਹੋ ਜਾਵੇਗਾ। ਬਹੁਤ ਬਹੁਤ ਧੰਨਵਾਦ ਜੀ!" Do NOT mention price or dollars.
**SIERRA:** ਤੁਹਾਡਾ ਆਰਡਰ ਮਿਲ ਗਿਆ ਜੀ! 30-40 ਮਿੰਟ ਵਿੱਚ ਤਿਆਰ ਹੋ ਜਾਵੇਗਾ। ਬਹੁਤ ਬਹੁਤ ਧੰਨਵਾਦ ਜੀ!

**USER:** Yes.
**SIERRA:** 

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
  "order_id": "EXYCDSFC35WJT"
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
- ✅ readbacks: at least 1 successful — got 2
