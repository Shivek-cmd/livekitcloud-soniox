# Scenario: change_after_readback

- channel: phone
- model: gemini-3.5-flash
- result: PASS

## Transcript

**SIERRA (greeting):** Hi! I'm Sierra, your virtual assistant. I speak English, Hindi, and Punjabi. How can I help you?

**USER:** Hi, one butter chicken please, medium.
> `add_item({"item_query": "butter chicken", "spice_level": "Medium"})` → ADDED: 1 x Butter Chicken, note: medium. ⏎ ORDER NOW: 1 x Butter Chicken [medium]. total=$19.99 ⏎ GUIDE: confirm the add in the customer's language — warm and in your own words, never reading these lines aloud — using the exact dish name and quantity above (quantity spoken as "one", never a digit), then keep the order moving.
**SIERRA:** You got it — one Butter Chicken, medium. What else can I get started for you today?

**USER:** That's everything.
> `record_additional_requests({"response": "no"})` → ADDITIONAL REQUESTS RECORDED: none. ⏎ ORDER NOW: 1 x Butter Chicken [medium]. total=$19.99 ⏎ GUIDE: acknowledge warmly in the customer's language, in your own words — do NOT re-ask about allergies, and never re-ask spice (it was settled per dish at add time) — then keep the order moving (pickup or delivery next if not set yet).
**SIERRA:** Perfect. Will this order be for pickup or delivery today?

**USER:** No allergies, nothing else.
**SIERRA:** Alright, got it. And is this going to be for pickup or delivery?

**USER:** Pickup.
> `set_order_type({"order_type": "pickup"})` → Set to pickup. Continue the flow.
**SIERRA:** Sure thing, pickup it is. Can I get your name for the order, please?

**USER:** Jasleen.
> `set_customer_contact({"name": "Jasleen"})` → NAME SAVED: "Jasleen". ⏎ GUIDE: confirm the name briefly in the customer's language. Then ask for their phone number.
**SIERRA:** Thanks, Jasleen. And what's a good phone number to reach you at?

**USER:** Four one six three zero four two two three three.
> `set_customer_contact({"phone": "4163042233"})` → PHONE SAVED: four, one, six, three, zero, four, two, two, three, three. ⏎ GUIDE: the number is already saved — do NOT ask the customer to repeat or re-say it. Call get_contact_readback next and read the name and number back for confirmation.
> `get_contact_readback({})` → CONTACT FACTS — read BOTH of these back to the customer, then ask if they are correct: ⏎ - name: Jasleen (say it in English/Roman script, then spell it letter by letter: J-A-S-L-E-E-N) ⏎ - phone: four, one, six, three, zero, four, two, two, three, three (say every digit as a separate English word, one at a time) ⏎ GUIDE: phrase the ask warmly in your own words in the customer's language, but the name letters and the phone digits themselves must be spoken exactly as above. If the customer corrects either one, call set_customer_contact with the fix and read it back again. Only when they say both are right, call confirm_contact.
**SIERRA:** Awesome. Let me just make sure I've got your contact details right: the name is Jasleen, spelled J-A-S-L-E-E-N, and the phone number is four, one, six, three, zero, four, two, two, three, three. Is that all correct?

**USER (reactive):** Yes.
> `confirm_contact({})` → Name and phone confirmed. Continue with the order read-back (get_order_readback).
> `get_order_readback({})` → READBACK FACTS — read ALL of these to the customer in their language, then ask if everything is correct: ⏎ - 1 x Butter Chicken [medium] ⏎ - order type: pickup (say "pickup" in English) ⏎ - name: Jasleen ⏎ GUIDE: phrase this warmly in your own words in the customer's language — but every item, its quantity (as a word, never a digit), and the order type must actually be spoken. Your spoken readback is checked — anything missing forces a re-read. End by asking if everything is correct.
**SIERRA:** Perfect. So we have one Butter Chicken, medium, for pickup under the name Jasleen. Is everything correct on your end?

**USER:** Actually, add a garlic naan too.
> `add_item({"item_query": "garlic naan"})` → ADDED: 1 x ਗਾਰਲਿਕ ਨਾਨ (Garlic Naan). ⏎ ORDER NOW: 1 x Butter Chicken [medium]; 1 x ਗਾਰਲਿਕ ਨਾਨ (Garlic Naan). total=$24.98 ⏎ GUIDE: confirm the add in the customer's language — warm and in your own words, never reading these lines aloud — using the exact dish name and quantity above (quantity spoken as "one", never a digit), then keep the order moving.
**SIERRA:** You got it — one ਗਾਰਲਿਕ ਨਾਨ added to your order. Since we updated the order, let me read it back to you one more time.

**USER:** Yes, that's all correct now.
> `get_order_readback({})` → READBACK FACTS — read ALL of these to the customer in their language, then ask if everything is correct: ⏎ - 1 x Butter Chicken [medium] ⏎ - 1 x ਗਾਰਲਿਕ ਨਾਨ (Garlic Naan) ⏎ - order type: pickup (say "pickup" in English) ⏎ - name: Jasleen ⏎ GUIDE: phrase this warmly in your own words in the customer's language — but every item, its quantity (as a word, never a digit), and the order type must actually be spoken. Your spoken readback is checked — anything missing forces a re-read. End by asking if everything is correct.
**SIERRA:** Alright, so we have one Butter Chicken, medium, and one ਗਾਰਲਿਕ ਨਾਨ, for pickup under the name Jasleen. Is everything correct?

**USER:** Yes, perfect.
> `confirm_readback({})` → Order placed! INTERNAL total $24.979999999999997. Tell customer: "ਤੁਹਾਡਾ ਆਰਡਰ ਮਿਲ ਗਿਆ ਜੀ! 20-25 ਮਿੰਟ ਵਿੱਚ ਤਿਆਰ ਹੋ ਜਾਵੇਗਾ। ਬਹੁਤ ਬਹੁਤ ਧੰਨਵਾਦ ਜੀ!" Do NOT mention price or dollars.
**SIERRA:** ਤੁਹਾਡਾ ਆਰਡਰ ਮਿਲ ਗਿਆ ਜੀ! 20-25 ਮਿੰਟ ਵਿੱਚ ਤਿਆਰ ਹੋ ਜਾਵੇਗਾ। ਬਹੁਤ ਬਹੁਤ ਧੰਨਵਾਦ ਜੀ!

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
    "phone": "4163042233"
  },
  "subtotal": 24.98,
  "delivery_charge": 0,
  "total": 24.98,
  "eta": "20-25 min",
  "order_id": "SA5WHB2QW3WR0"
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
- ✅ customer_phone — got '4163042233'
- ✅ additional_requests_recorded — got True
- ✅ readbacks: at least 2 successful — got 2
