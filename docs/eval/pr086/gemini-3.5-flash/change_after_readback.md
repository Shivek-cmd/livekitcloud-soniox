# Scenario: change_after_readback

- channel: phone
- model: gemini-3.5-flash
- result: PASS

## Transcript

**SIERRA (greeting):** Hi! I'm Sierra, your virtual assistant. I speak English, Hindi, and Punjabi. How can I help you?

**USER:** Hi, one butter chicken please, medium.
> `add_item({"spice_level": "medium", "item_query": "butter chicken"})` → ADDED: 1 x Butter Chicken, note: medium. ⏎ ORDER NOW: 1 x Butter Chicken [medium]. total=$19.99 ⏎ GUIDE: confirm the add in the customer's language — warm and in your own words, never reading these lines aloud — using the exact dish name and quantity above (quantity spoken as "one", never a digit), then keep the order moving.
**SIERRA:** You got it — I've added one Butter Chicken with medium spice for you. What else can I get started for you today?

**USER:** That's everything.
> `record_additional_requests({"response": "no other requests"})` → ADDITIONAL REQUESTS RECORDED for the kitchen: "no other requests". ⏎ ORDER NOW: 1 x Butter Chicken [medium]. total=$19.99 ⏎ GUIDE: acknowledge warmly in the customer's language, in your own words — do NOT re-ask about spice or allergies — then keep the order moving (pickup or delivery next if not set yet).
**SIERRA:** Alright, perfect. And will this order be for pickup, or would you like us to deliver it to you?

**USER:** No allergies, nothing else.
**SIERRA:** Perfect, thank you for letting me know. And is this going to be for pickup or delivery?

**USER:** Pickup.
> `set_order_type({"order_type": "pickup"})` → Set to pickup. Continue the flow.
**SIERRA:** Awesome, pickup it is. Can I get your name for the order, please?

**USER:** Jasleen.
> `set_customer_contact({"name": "Jasleen"})` → NAME SAVED: "Jasleen". ⏎ GUIDE: confirm the name briefly in the customer's language. Then ask for their phone number.
**SIERRA:** Great, Jasleen. And what is a good phone number to reach you at?

**USER:** Four one six five five five two two three three.
> `set_customer_contact({"phone": "4165552233"})` → PHONE SAVED: four, one, six, five, five, five, two, two, three, three. ⏎ GUIDE: the number is already saved — do NOT ask the customer to repeat or re-say it. Confirm it back once yourself, speaking it as English word digits exactly as in PHONE SAVED (never numerals, never Punjabi/Hindi number words), then continue the order.
> `get_order_readback({})` → READBACK FACTS — read ALL of these to the customer in their language, then ask if everything is correct: ⏎ - 1 x Butter Chicken [medium] ⏎ - order type: pickup (say "pickup" in English) ⏎ - name: Jasleen ⏎ GUIDE: phrase this warmly in your own words in the customer's language — but every item, its quantity (as a word, never a digit), and the order type must actually be spoken. Your spoken readback is checked — anything missing forces a re-read. End by asking if everything is correct.
**SIERRA:** Thank you, Jasleen. I have your phone number down as four, one, six, five, five, five, two, two, three, three. 

Let me read your order back to make sure we have everything right: I have one Butter Chicken with medium spice, and this is for pickup under the name Jasleen. Is all of that correct?

**USER (reactive):** Yes.
> `confirm_readback({})` → Read-back confirmed. Call place_order now.
> `place_order({})` → Order placed! INTERNAL total $19.99. Tell customer: "ਤੁਹਾਡਾ ਆਰਡਰ ਮਿਲ ਗਿਆ ਜੀ! 20-25 ਮਿੰਟ ਵਿੱਚ ਤਿਆਰ ਹੋ ਜਾਵੇਗਾ। ਬਹੁਤ ਬਹੁਤ ਧੰਨਵਾਦ ਜੀ!" Do NOT mention price or dollars.
**SIERRA:** ਤੁਹਾਡਾ ਆਰਡਰ ਮਿਲ ਗਿਆ ਜੀ! 20-25 ਮਿੰਟ ਵਿੱਚ ਤਿਆਰ ਹੋ ਜਾਵੇਗਾ। ਬਹੁਤ ਬਹੁਤ ਧੰਨਵਾਦ ਜੀ!

**USER:** Actually, add a garlic naan too.
> `add_item({"item_query": "garlic naan"})` → ADDED: 1 x ਗਾਰਲਿਕ ਨਾਨ (Garlic Naan). ⏎ ORDER NOW: 1 x Butter Chicken [medium]; 1 x ਗਾਰਲਿਕ ਨਾਨ (Garlic Naan). total=$24.98 ⏎ GUIDE: confirm the add in the customer's language — warm and in your own words, never reading these lines aloud — using the exact dish name and quantity above (quantity spoken as "one", never a digit), then keep the order moving.
**SIERRA:** No problem, I've added one ਗਾਰਲਿਕ ਨਾਨ to your order. Since we made a change, let me just double-check: is there anything else you'd like to add, or are we good to go with this?

**USER:** Yes, that's all correct now.
> `record_additional_requests({"response": "no other requests"})` → ADDITIONAL REQUESTS RECORDED for the kitchen: "no other requests". ⏎ ORDER NOW: 1 x Butter Chicken [medium]; 1 x ਗਾਰਲਿਕ ਨਾਨ (Garlic Naan). total=$24.98 ⏎ GUIDE: acknowledge warmly in the customer's language, in your own words — do NOT re-ask about spice or allergies — then keep the order moving (pickup or delivery next if not set yet).
> `get_order_readback({})` → READBACK FACTS — read ALL of these to the customer in their language, then ask if everything is correct: ⏎ - 1 x Butter Chicken [medium] ⏎ - 1 x ਗਾਰਲਿਕ ਨਾਨ (Garlic Naan) ⏎ - order type: pickup (say "pickup" in English) ⏎ - name: Jasleen ⏎ GUIDE: phrase this warmly in your own words in the customer's language — but every item, its quantity (as a word, never a digit), and the order type must actually be spoken. Your spoken readback is checked — anything missing forces a re-read. End by asking if everything is correct.
**SIERRA:** Alright, let me read the updated order back to you: I have one Butter Chicken with medium spice and one ਗਾਰਲਿਕ ਨਾਨ, for pickup under the name Jasleen. Is everything correct now?

**USER:** Yes, perfect.
> `confirm_readback({})` → Read-back confirmed. Call place_order now.
> `place_order({})` → ORDER COMPLETE — goodbye already spoken. Do NOT generate any assistant speech.
**SIERRA:** 

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
      "qty": 1,
      "unit_price": 19.99,
      "line_total": 19.99,
      "note": "medium",
      "modifiers": [
        "medium"
      ]
    },
    {
      "id": "T61J8SX6W8JF2",
      "name": "Garlic Naan",
      "voice_line": "ਗਾਰਲਿਕ ਨਾਨ",
      "qty": 1,
      "unit_price": 4.99,
      "line_total": 4.99,
      "note": "",
      "modifiers": []
    }
  ],
  "order_type": "pickup",
  "delivery_address": null,
  "customer": {
    "name": "Jasleen",
    "phone": "4165552233"
  },
  "subtotal": 24.98,
  "delivery_charge": 0,
  "total": 24.98,
  "eta": "20-25 min",
  "order_id": "KBP6JM5P0W9AT"
}
```

## Assertions

- ✅ gates: placed order had a confirmed, current readback — readback_confirmed=True readback_revision=3 cart.revision=3
- ✅ placed — cart.placed=True
- ✅ items: exact set of dishes — cart=['Butter Chicken', 'Garlic Naan']
- ✅ items: Butter Chicken qty == 1 — got qty=1
- ✅ items: Butter Chicken note contains 'medium' — got note='medium'
- ✅ items: Garlic Naan qty == 1 — got qty=1
- ✅ order_type — got 'pickup'
- ✅ customer_name — got 'Jasleen'
- ✅ customer_phone — got '4165552233'
- ✅ additional_requests_recorded — got True
- ✅ readbacks: at least 2 successful — got 2
