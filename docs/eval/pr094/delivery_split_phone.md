# Scenario: delivery_split_phone

- channel: phone
- model: gemini-3.5-flash
- result: FAIL

## Transcript

**SIERRA (greeting):** Hi! I'm Sierra, your virtual assistant. I speak English, Hindi, and Punjabi. How can I help you?

**USER:** Hello, one dal makhani and two butter naan please.
> `add_item({"item_query": "dal makhani", "quantity": 1})` → ⛔ NOTHING WAS ADDED — CART UNCHANGED. NEEDS SPICE — Dal Makhani comes Mild, Medium, Spicy or Extra Spicy. Ask the customer which they want ('no preference' = Medium), then re-call add_item with spice_level. If other dishes in this turn also need one, ask about them in the SAME question, then re-call add_item once per dish.
> `add_item({"item_query": "butter naan", "quantity": 2})` → ADDED: 2 x ਬਟਰ ਨਾਨ (Butter Naan). ⏎ ORDER NOW: 2 x ਬਟਰ ਨਾਨ (Butter Naan). total=$7.98 ⏎ GUIDE: confirm the add in the customer's language — warm and in your own words, never reading these lines aloud — using the exact dish name and quantity above (quantity spoken as "two", never a digit), then keep the order moving.
**SIERRA:** Sure thing! I've got two Butter Naan down for you. How would you like the spice level for your Dal Makhani — mild, medium, spicy, or extra spicy?

**USER:** Make the dal spicy.
> `add_item({"spice_level": "Spicy", "item_query": "dal makhani", "quantity": 1})` → ADDED: 1 x ਦਾਲ ਮੱਖਣੀ (Dal Makhani), note: spicy. ⏎ ORDER NOW: 2 x ਬਟਰ ਨਾਨ (Butter Naan); 1 x ਦਾਲ ਮੱਖਣੀ (Dal Makhani) [spicy]. total=$23.97 ⏎ GUIDE: confirm the add in the customer's language — warm and in your own words, never reading these lines aloud — using the exact dish name and quantity above (quantity spoken as "one", never a digit), then keep the order moving.
**SIERRA:** You got it — one Dal Makhani, spicy. What else can I get started for you today?

**USER:** That's all.
> `record_additional_requests({"response": "no"})` → ADDITIONAL REQUESTS RECORDED: none. ⏎ ORDER NOW: 2 x ਬਟਰ ਨਾਨ (Butter Naan); 1 x ਦਾਲ ਮੱਖਣੀ (Dal Makhani) [spicy]. total=$23.97 ⏎ GUIDE: acknowledge warmly in the customer's language, in your own words — do NOT re-ask about allergies, and never re-ask spice (it was settled per dish at add time) — then keep the order moving (pickup or delivery next if not set yet).
**SIERRA:** Perfect. Will this order be for pickup or delivery today?

**USER (reactive):** Delivery please.
> `set_order_type({"order_type": "delivery"})` → Set to delivery. INTERNAL: delivery charge applies — do NOT mention price unless the customer asked. Ask for the delivery address.
**SIERRA:** Awesome, delivery it is. Could you please give me your delivery address?

**USER (reactive):** It's 12 Main Street, Brampton.
> `set_delivery_address({"address": "12 Main Street, Brampton"})` → Delivery address saved: 12 Main Street, Brampton.
**SIERRA:** Got that down. And can I get your name for the order, please?

**USER:** Nope, no allergies, nothing else.
**SIERRA:** I've got your address saved as 12 Main Street, Brampton. Could I just get your name for the order, please?

**USER (reactive):** It's 12 Main Street, Brampton.
**SIERRA:** I have the address saved as 12 Main Street, Brampton. Could you please tell me your name so I can put it on the order?

**USER:** Navdeep.
**SIERRA:** 
**ERROR:** LLM call failed after retries: completion had no message (finish_reason=content_filter: PROHIBITED_CONTENT)

**USER:** Six four seven three zero four...
> `set_customer_contact({"name": "Navdeep", "phone": "647304"})` → NAME SAVED: "Navdeep". ⏎ PHONE PARTIAL: have 6 of 10 (647304). ⏎ GUIDE: confirm the name briefly in the customer's language. ask only for the REMAINING digits — do not restart, and do not re-send digits already captured.
**SIERRA:** Thanks, Navdeep! I've got the first six digits of your phone number as six, four, seven, three, zero, four. What are the last four digits?

**USER (reactive):** Yes.
**SIERRA:** Could you please give me the last four digits of your phone number to complete it?

**USER:** Sorry — six four seven three zero four one two one two.
> `set_customer_contact({"phone": "6473041212", "name": "Navdeep"})` → NAME SAVED: "Navdeep". ⏎ PHONE SAVED: six, four, seven, three, zero, four, one, two, one, two. ⏎ GUIDE: confirm the name briefly in the customer's language. the number is already saved — do NOT ask the customer to repeat or re-say it. Call get_contact_readback next and read the name and number back for confirmation.
> `get_contact_readback({})` → CONTACT FACTS — read BOTH of these back to the customer, then ask if they are correct: ⏎ - name: Navdeep (say it in English/Roman script, then spell it letter by letter: N-A-V-D-E-E-P) ⏎ - phone: six, four, seven, three, zero, four, one, two, one, two (say every digit as a separate English word, one at a time) ⏎ GUIDE: phrase the ask warmly in your own words in the customer's language, but the name letters and the phone digits themselves must be spoken exactly as above. If the customer corrects either one, call set_customer_contact with the fix and read it back again. Only when they say both are right, call confirm_contact.
**SIERRA:** Perfect, Navdeep. Let me read that back to make sure I have it exactly right. 

The name is Navdeep, spelled N-A-V-D-E-E-P, and the phone number is six, four, seven, three, zero, four, one, two, one, two. Is that all correct?

**USER (reactive):** Yes.
> `confirm_contact({})` → Name and phone confirmed. Continue with the order read-back (get_order_readback).
> `get_order_readback({})` → READBACK FACTS — read ALL of these to the customer in their language, then ask if everything is correct: ⏎ - 2 x ਬਟਰ ਨਾਨ (Butter Naan) ⏎ - 1 x ਦਾਲ ਮੱਖਣੀ (Dal Makhani) [spicy] ⏎ - order type: delivery (say "delivery" in English) ⏎ - name: Navdeep ⏎ GUIDE: phrase this warmly in your own words in the customer's language — but every item, its quantity (as a word, never a digit), and the order type must actually be spoken. Your spoken readback is checked — anything missing forces a re-read. End by asking if everything is correct.
**SIERRA:** Alright, I have your order ready to go. 

That is two Butter Naan and one Dal Makhani, spicy, for delivery to Navdeep. Is everything correct?

**USER (reactive):** Delivery please.
**SIERRA:** Yes, I have it set for delivery. Is the rest of the order with the two Butter Naan and one Dal Makhani, spicy, all correct?

**USER:** Yes, that's right.
> `confirm_readback({})` → Order placed! INTERNAL total $28.97. Tell customer: "ਤੁਹਾਡਾ ਆਰਡਰ ਮਿਲ ਗਿਆ ਜੀ! 30-40 ਮਿੰਟ ਵਿੱਚ ਤਿਆਰ ਹੋ ਜਾਵੇਗਾ। ਬਹੁਤ ਬਹੁਤ ਧੰਨਵਾਦ ਜੀ!" Do NOT mention price or dollars.
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
      "id": "8BQQ63MMZDSMG",
      "name": "Butter Naan",
      "voice_line": "ਬਟਰ ਨਾਨ",
      "qty": 2,
      "unit_price": 3.99,
      "line_total": 7.98,
      "note": "",
      "modifiers": []
    },
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
    }
  ],
  "order_type": "delivery",
  "delivery_address": "12 Main Street, Brampton",
  "customer": {
    "name": "Navdeep",
    "phone": "6473041212"
  },
  "subtotal": 23.97,
  "delivery_charge": 5,
  "total": 28.97,
  "eta": "30-40 min",
  "order_id": "S175ZP65NQA8G"
}
```

## Assertions

- ✅ gates: placed order had a confirmed, current readback — readback_confirmed=True readback_revision=3 cart.revision=3
- ✅ placed — cart.placed=True
- ✅ items: exact set of dishes — cart=['Butter Naan', 'Dal Makhani']
- ✅ items: Dal Makhani qty == 1 — got qty=1
- ✅ items: Dal Makhani note contains 'spicy' — got note='spicy'
- ✅ items: Butter Naan qty == 2 — got qty=2
- ✅ order_type — got 'delivery'
- ✅ customer_name — got 'Navdeep'
- ✅ customer_phone — got '6473041212'
- ✅ additional_requests_recorded — got True
- ✅ readbacks: at least 1 successful — got 1
