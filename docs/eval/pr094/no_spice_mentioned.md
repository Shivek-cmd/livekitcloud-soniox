# Scenario: no_spice_mentioned

- channel: phone
- model: gemini-3.5-flash
- result: PASS

## Transcript

**SIERRA (greeting):** Hi! I'm Sierra, your virtual assistant. I speak English, Hindi, and Punjabi. How can I help you?

**USER:** Hi, one butter chicken and one garlic naan please.
> `add_item({"quantity": 1, "item_query": "butter chicken"})` → ⛔ NOTHING WAS ADDED — CART UNCHANGED. NEEDS SPICE — Butter Chicken comes Mild, Medium, Spicy or Extra Spicy. Ask the customer which they want ('no preference' = Medium), then re-call add_item with spice_level. If other dishes in this turn also need one, ask about them in the SAME question, then re-call add_item once per dish.
> `add_item({"quantity": 1, "item_query": "garlic naan"})` → ADDED: 1 x ਗਾਰਲਿਕ ਨਾਨ (Garlic Naan). ⏎ ORDER NOW: 1 x ਗਾਰਲਿਕ ਨਾਨ (Garlic Naan). total=$4.99 ⏎ GUIDE: confirm the add in the customer's language — warm and in your own words, never reading these lines aloud — using the exact dish name and quantity above (quantity spoken as "one", never a digit), then keep the order moving.
**SIERRA:** Sure thing! I've got one ਗਾਰਲਿਕ ਨਾਨ down for you. How would you like the spice level for your Butter Chicken — mild, medium, spicy, or extra spicy?

**USER:** Oh, no preference really — whatever's normal.
> `add_item({"quantity": 1, "spice_level": "Medium", "item_query": "butter chicken"})` → ADDED: 1 x Butter Chicken, note: medium. ⏎ ORDER NOW: 1 x ਗਾਰਲਿਕ ਨਾਨ (Garlic Naan); 1 x Butter Chicken [medium]. total=$24.98 ⏎ GUIDE: confirm the add in the customer's language — warm and in your own words, never reading these lines aloud — using the exact dish name and quantity above (quantity spoken as "one", never a digit), then keep the order moving.
**SIERRA:** Perfect, I've added one Butter Chicken at medium spice. Can I get you anything else with that?

**USER:** That's everything.
> `record_additional_requests({"response": "no"})` → ADDITIONAL REQUESTS RECORDED: none. ⏎ ORDER NOW: 1 x ਗਾਰਲਿਕ ਨਾਨ (Garlic Naan); 1 x Butter Chicken [medium]. total=$24.98 ⏎ GUIDE: acknowledge warmly in the customer's language, in your own words — do NOT re-ask about allergies, and never re-ask spice (it was settled per dish at add time) — then keep the order moving (pickup or delivery next if not set yet).
**SIERRA:** Got it, no special instructions. Will this order be for pickup or delivery today?

**USER:** No, nothing — all good.
**SIERRA:** You got it. Will this order be for pickup or delivery today?

**USER:** Pickup.
> `set_order_type({"order_type": "pickup"})` → Set to pickup. Continue the flow.
**SIERRA:** Awesome, pickup it is. Can I get your name for the order, please?

**USER:** My name is Karan.
> `set_customer_contact({"name": "Karan"})` → NAME SAVED: "Karan". ⏎ GUIDE: confirm the name briefly in the customer's language. Then ask for their phone number.
**SIERRA:** Nice to meet you, Karan. And what is a good phone number to reach you at?

**USER:** Four one six three zero four one two three four.
> `set_customer_contact({"phone": "4163041234"})` → PHONE SAVED: four, one, six, three, zero, four, one, two, three, four. ⏎ GUIDE: the number is already saved — do NOT ask the customer to repeat or re-say it. Call get_contact_readback next and read the name and number back for confirmation.
> `get_contact_readback({})` → CONTACT FACTS — read BOTH of these back to the customer, then ask if they are correct: ⏎ - name: Karan (say it in English/Roman script, then spell it letter by letter: K-A-R-A-N) ⏎ - phone: four, one, six, three, zero, four, one, two, three, four (say every digit as a separate English word, one at a time) ⏎ GUIDE: phrase the ask warmly in your own words in the customer's language, but the name letters and the phone digits themselves must be spoken exactly as above. If the customer corrects either one, call set_customer_contact with the fix and read it back again. Only when they say both are right, call confirm_contact.
**SIERRA:** Alright, let me just make sure I've got your contact details right. I have your name as Karan, spelled K-A-R-A-N, and your phone number as four, one, six, three, zero, four, one, two, three, four. Is that all correct?

**USER (reactive):** Yes.
> `confirm_contact({})` → Name and phone confirmed. Continue with the order read-back (get_order_readback).
> `get_order_readback({})` → READBACK FACTS — read ALL of these to the customer in their language, then ask if everything is correct: ⏎ - 1 x ਗਾਰਲਿਕ ਨਾਨ (Garlic Naan) ⏎ - 1 x Butter Chicken [medium] ⏎ - order type: pickup (say "pickup" in English) ⏎ - name: Karan ⏎ GUIDE: phrase this warmly in your own words in the customer's language — but every item, its quantity (as a word, never a digit), and the order type must actually be spoken. Your spoken readback is checked — anything missing forces a re-read. End by asking if everything is correct.
**SIERRA:** Perfect. Let me read your order back to you to make sure everything is correct. I have one ਗਾਰਲਿਕ ਨਾਨ and one Butter Chicken, medium spice, for pickup under the name Karan. Does that all look good to you?

**USER:** Yes, that's right.
> `confirm_readback({})` → Order placed! INTERNAL total $24.979999999999997. Tell customer: "ਤੁਹਾਡਾ ਆਰਡਰ ਮਿਲ ਗਿਆ ਜੀ! 20-25 ਮਿੰਟ ਵਿੱਚ ਤਿਆਰ ਹੋ ਜਾਵੇਗਾ। ਬਹੁਤ ਬਹੁਤ ਧੰਨਵਾਦ ਜੀ!" Do NOT mention price or dollars.
**SIERRA:** ਤੁਹਾਡਾ ਆਰਡਰ ਮਿਲ ਗਿਆ ਜੀ! 20-25 ਮਿੰਟ ਵਿੱਚ ਤਿਆਰ ਹੋ ਜਾਵੇਗਾ। ਬਹੁਤ ਬਹੁਤ ਧੰਨਵਾਦ ਜੀ!

## Final cart

```json
{
  "v": 1,
  "status": "placed",
  "items": [
    {
      "id": "T61J8SX6W8JF2",
      "name": "Garlic Naan",
      "voice_line": "ਗਾਰਲਿਕ ਨਾਨ",
      "qty": 1,
      "unit_price": 4.99,
      "line_total": 4.99,
      "note": "",
      "modifiers": []
    },
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
    "name": "Karan",
    "phone": "4163041234"
  },
  "subtotal": 24.98,
  "delivery_charge": 0,
  "total": 24.98,
  "eta": "20-25 min",
  "order_id": "Y8NZNSXFZXJA0"
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
- ✅ customer_name — got 'Karan'
- ✅ customer_phone — got '4163041234'
- ✅ additional_requests_recorded — got True
- ✅ readbacks: at least 1 successful — got 1
