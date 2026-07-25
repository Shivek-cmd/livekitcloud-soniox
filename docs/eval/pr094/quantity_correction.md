# Scenario: quantity_correction

- channel: phone
- model: gemini-3.5-flash
- result: PASS

## Transcript

**SIERRA (greeting):** Hi! I'm Sierra, your virtual assistant. I speak English, Hindi, and Punjabi. How can I help you?

**USER:** Two butter chicken please, medium spice.
> `add_item({"quantity": 2, "item_query": "butter chicken", "spice_level": "Medium"})` → ADDED: 2 x Butter Chicken, note: medium. ⏎ ORDER NOW: 2 x Butter Chicken [medium]. total=$39.98 ⏎ GUIDE: confirm the add in the customer's language — warm and in your own words, never reading these lines aloud — using the exact dish name and quantity above (quantity spoken as "two", never a digit), then keep the order moving.
**SIERRA:** You got it — two Butter Chicken, medium. What else can I get started for you today?

**USER:** Wait — I said one, not two.
> `set_item_quantity({"quantity": 1, "item_query": "butter chicken"})` → CORRECTED (not added): Butter Chicken is now 1 total. ⏎ ORDER NOW: 1 x Butter Chicken [medium]. total=$19.99 ⏎ GUIDE: reassure the customer in their language, in your own words, that it is fixed — "one" total, not a second add.
**SIERRA:** Ah, my mistake! I've got that changed to just the one Butter Chicken for you. What else can I get for you?

**USER:** That's all.
> `record_additional_requests({"response": "no"})` → ADDITIONAL REQUESTS RECORDED: none. ⏎ ORDER NOW: 1 x Butter Chicken [medium]. total=$19.99 ⏎ GUIDE: acknowledge warmly in the customer's language, in your own words — do NOT re-ask about allergies, and never re-ask spice (it was settled per dish at add time) — then keep the order moving (pickup or delivery next if not set yet).
**SIERRA:** Perfect. And will this order be for pickup or delivery today?

**USER:** No allergies, nothing else.
**SIERRA:** No problem, I've got that noted down. Will this be for pickup or delivery today?

**USER:** Pickup.
> `set_order_type({"order_type": "pickup"})` → Set to pickup. Continue the flow.
**SIERRA:** Got it, pickup it is. Can I get your name for the order, please?

**USER:** It's Simran.
> `set_customer_contact({"name": "Simran"})` → NAME SAVED: "Simran". ⏎ GUIDE: confirm the name briefly in the customer's language. Then ask for their phone number.
**SIERRA:** Great, Simran. And what is a good phone number to reach you at?

**USER:** Nine zero three zero four five one one two two.
> `set_customer_contact({"phone": "9030451122"})` → PHONE SAVED: nine, zero, three, zero, four, five, one, one, two, two. ⏎ GUIDE: the number is already saved — do NOT ask the customer to repeat or re-say it. Call get_contact_readback next and read the name and number back for confirmation.
> `get_contact_readback({})` → CONTACT FACTS — read BOTH of these back to the customer, then ask if they are correct: ⏎ - name: Simran (say it in English/Roman script, then spell it letter by letter: S-I-M-R-A-N) ⏎ - phone: nine, zero, three, zero, four, five, one, one, two, two (say every digit as a separate English word, one at a time) ⏎ GUIDE: phrase the ask warmly in your own words in the customer's language, but the name letters and the phone digits themselves must be spoken exactly as above. If the customer corrects either one, call set_customer_contact with the fix and read it back again. Only when they say both are right, call confirm_contact.
**SIERRA:** Alright, let me just make sure I have your contact details correct. I have your name as Simran, spelled S-I-M-R-A-N, and your phone number as nine, zero, three, zero, four, five, one, one, two, two. Is that all correct?

**USER (reactive):** Yes.
> `confirm_contact({})` → Name and phone confirmed. Continue with the order read-back (get_order_readback).
> `get_order_readback({})` → READBACK FACTS — read ALL of these to the customer in their language, then ask if everything is correct: ⏎ - 1 x Butter Chicken [medium] ⏎ - order type: pickup (say "pickup" in English) ⏎ - name: Simran ⏎ GUIDE: phrase this warmly in your own words in the customer's language — but every item, its quantity (as a word, never a digit), and the order type must actually be spoken. Your spoken readback is checked — anything missing forces a re-read. End by asking if everything is correct.
**SIERRA:** Awesome. Let me read your order back to you to make sure everything is perfect. I have one Butter Chicken, medium, for pickup under the name Simran. Is everything correct?

**USER:** Yes, perfect.
> `confirm_readback({})` → Order placed! INTERNAL total $19.99. Tell customer: "ਤੁਹਾਡਾ ਆਰਡਰ ਮਿਲ ਗਿਆ ਜੀ! 20-25 ਮਿੰਟ ਵਿੱਚ ਤਿਆਰ ਹੋ ਜਾਵੇਗਾ। ਬਹੁਤ ਬਹੁਤ ਧੰਨਵਾਦ ਜੀ!" Do NOT mention price or dollars.
**SIERRA:** ਤੁਹਾਡਾ ਆਰਡਰ ਮਿਲ ਗਿਆ ਜੀ! 20-25 ਮਿੰਟ ਵਿੱਚ ਤਿਆਰ ਹੋ ਜਾਵੇਗਾ। ਬਹੁਤ ਬਹੁਤ ਧੰਨਵਾਦ ਜੀ!

**USER:** Yes.
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
    }
  ],
  "order_type": "pickup",
  "delivery_address": null,
  "customer": {
    "name": "Simran",
    "phone": "9030451122"
  },
  "subtotal": 19.99,
  "delivery_charge": 0,
  "total": 19.99,
  "eta": "20-25 min",
  "order_id": "9EJQJG1PXBXFG"
}
```

## Assertions

- ✅ gates: placed order had a confirmed, current readback — readback_confirmed=True readback_revision=3 cart.revision=3
- ✅ placed — cart.placed=True
- ✅ items: exact set of dishes — cart=['Butter Chicken']
- ✅ items: Butter Chicken qty == 1 — got qty=1
- ✅ items: Butter Chicken note contains 'medium' — got note='medium'
- ✅ order_type — got 'pickup'
- ✅ customer_name — got 'Simran'
- ✅ customer_phone — got '9030451122'
- ✅ additional_requests_recorded — got True
- ✅ readbacks: at least 1 successful — got 1
