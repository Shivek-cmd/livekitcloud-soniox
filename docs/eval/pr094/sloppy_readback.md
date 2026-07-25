# Scenario: sloppy_readback

- channel: phone
- model: gemini-3.5-flash
- result: PASS

## Transcript

**SIERRA (greeting):** Hi! I'm Sierra, your virtual assistant. I speak English, Hindi, and Punjabi. How can I help you?

**USER:** Hi, can I get two butter chicken and one garlic naan please?
> `add_item({"item_query": "butter chicken", "quantity": 2})` → ⛔ NOTHING WAS ADDED — CART UNCHANGED. NEEDS SPICE — Butter Chicken comes Mild, Medium, Spicy or Extra Spicy. Ask the customer which they want ('no preference' = Medium), then re-call add_item with spice_level. If other dishes in this turn also need one, ask about them in the SAME question, then re-call add_item once per dish.
> `add_item({"quantity": 1, "item_query": "garlic naan"})` → ADDED: 1 x ਗਾਰਲਿਕ ਨਾਨ (Garlic Naan). ⏎ ORDER NOW: 1 x ਗਾਰਲਿਕ ਨਾਨ (Garlic Naan). total=$4.99 ⏎ GUIDE: confirm the add in the customer's language — warm and in your own words, never reading these lines aloud — using the exact dish name and quantity above (quantity spoken as "one", never a digit), then keep the order moving.
**SIERRA:** Sure thing! I've got one Garlic Naan down for you. How would you like the spice level for your two Butter Chicken — mild, medium, spicy, or extra spicy?

**USER:** Medium spice please.
> `add_item({"spice_level": "Medium", "quantity": 2, "item_query": "butter chicken"})` → ADDED: 2 x Butter Chicken, note: medium. ⏎ ORDER NOW: 1 x ਗਾਰਲਿਕ ਨਾਨ (Garlic Naan); 2 x Butter Chicken [medium]. total=$44.97 ⏎ GUIDE: confirm the add in the customer's language — warm and in your own words, never reading these lines aloud — using the exact dish name and quantity above (quantity spoken as "two", never a digit), then keep the order moving.
**SIERRA:** You got it — two Butter Chicken, medium. What else can I get started for you today?

**USER:** That's everything, thanks.
> `record_additional_requests({"response": "no"})` → ADDITIONAL REQUESTS RECORDED: none. ⏎ ORDER NOW: 1 x ਗਾਰਲਿਕ ਨਾਨ (Garlic Naan); 2 x Butter Chicken [medium]. total=$44.97 ⏎ GUIDE: acknowledge warmly in the customer's language, in your own words — do NOT re-ask about allergies, and never re-ask spice (it was settled per dish at add time) — then keep the order moving (pickup or delivery next if not set yet).
**SIERRA:** Perfect. Will this order be for pickup or delivery today?

**USER:** No allergies, nothing else.
**SIERRA:** Awesome, thank you. And will you be picking this up, or would you like it delivered?

**USER:** Pickup please.
> `set_order_type({"order_type": "pickup"})` → Set to pickup. Continue the flow.
**SIERRA:** Great, pickup it is. Can I get your name for the order, please?

**USER:** My name is Harpreet.
> `set_customer_contact({"name": "Harpreet"})` → NAME SAVED: "Harpreet". ⏎ GUIDE: confirm the name briefly in the customer's language. Then ask for their phone number.
**SIERRA:** Got it, Harpreet. And what is a good phone number to reach you at?

**USER:** Six four seven three zero four one two one two.
> `set_customer_contact({"phone": "6473041212"})` → PHONE SAVED: six, four, seven, three, zero, four, one, two, one, two. ⏎ GUIDE: the number is already saved — do NOT ask the customer to repeat or re-say it. Call get_contact_readback next and read the name and number back for confirmation.
> `get_contact_readback({})` → CONTACT FACTS — read BOTH of these back to the customer, then ask if they are correct: ⏎ - name: Harpreet (say it in English/Roman script, then spell it letter by letter: H-A-R-P-R-E-E-T) ⏎ - phone: six, four, seven, three, zero, four, one, two, one, two (say every digit as a separate English word, one at a time) ⏎ GUIDE: phrase the ask warmly in your own words in the customer's language, but the name letters and the phone digits themselves must be spoken exactly as above. If the customer corrects either one, call set_customer_contact with the fix and read it back again. Only when they say both are right, call confirm_contact.
**SIERRA:** Alright, let me just make sure I have your contact details correct. I have your name down as Harpreet, spelled H-A-R-P-R-E-E-T, and your phone number is six, four, seven, three, zero, four, one, two, one, two. Is that all correct?

**USER (reactive):** Yes.
> `confirm_contact({})` → Name and phone confirmed. Continue with the order read-back (get_order_readback).
> `get_order_readback({})` → READBACK FACTS — read ALL of these to the customer in their language, then ask if everything is correct: ⏎ - 1 x ਗਾਰਲਿਕ ਨਾਨ (Garlic Naan) ⏎ - 2 x Butter Chicken [medium] ⏎ - order type: pickup (say "pickup" in English) ⏎ - name: Harpreet ⏎ GUIDE: phrase this warmly in your own words in the customer's language — but every item, its quantity (as a word, never a digit), and the order type must actually be spoken. Your spoken readback is checked — anything missing forces a re-read. End by asking if everything is correct.
**SIERRA:** Perfect. Let me read your order back to you: I have one Garlic Naan and two Butter Chicken, medium, for pickup under the name Harpreet. Is everything correct?

**USER:** Yes, that's correct.
> `confirm_readback({})` → READBACK INCOMPLETE — the customer has not heard the full order: ⏎ - you never said 'ਗਾਰਲਿਕ ਨਾਨ' ⏎ Read ALL the READBACK FACTS again in the customer's language, then ask again if everything is correct.
**SIERRA:** Ah, my apologies! Let me read that back to you properly: I have one ਗਾਰਲਿਕ ਨਾਨ and two Butter Chicken, medium, for pickup under the name Harpreet. Is everything correct?

**USER:** Yes, everything is correct.
> `confirm_readback({})` → READBACK INCOMPLETE — the customer has not heard the full order: ⏎ - you never said 'ਗਾਰਲਿਕ ਨਾਨ' ⏎ Read ALL the READBACK FACTS again in the customer's language, then ask again if everything is correct.
**SIERRA:** My mistake, let me get that exactly right for you. I have one ਗਾਰਲਿਕ ਨਾਨ and two Butter Chicken, medium, for pickup under the name Harpreet. Is that all correct?

**USER:** Yes, that's all right.
> `confirm_readback({})` → Order placed! INTERNAL total $44.97. Tell customer: "ਤੁਹਾਡਾ ਆਰਡਰ ਮਿਲ ਗਿਆ ਜੀ! 20-25 ਮਿੰਟ ਵਿੱਚ ਤਿਆਰ ਹੋ ਜਾਵੇਗਾ। ਬਹੁਤ ਬਹੁਤ ਧੰਨਵਾਦ ਜੀ!" Do NOT mention price or dollars.
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
      "qty": 2,
      "unit_price": 19.99,
      "line_total": 39.98,
      "note": "medium",
      "modifiers": [
        "medium"
      ]
    }
  ],
  "order_type": "pickup",
  "delivery_address": null,
  "customer": {
    "name": "Harpreet",
    "phone": "6473041212"
  },
  "subtotal": 44.97,
  "delivery_charge": 0,
  "total": 44.97,
  "eta": "20-25 min",
  "order_id": "W41TWG3WBRSW2"
}
```

## Assertions

- ✅ gates: placed order had a confirmed, current readback — readback_confirmed=True readback_revision=3 cart.revision=3
- ✅ placed — cart.placed=True
- ✅ items: exact set of dishes — cart=['Butter Chicken', 'Garlic Naan']
- ✅ items: Butter Chicken qty == 2 — got qty=2
- ✅ items: Butter Chicken note contains 'medium' — got note='medium'
- ✅ items: Garlic Naan qty == 1 — got qty=1
- ✅ order_type — got 'pickup'
- ✅ customer_name — got 'Harpreet'
- ✅ customer_phone — got '6473041212'
- ✅ additional_requests_recorded — got True
- ✅ readbacks: at least 1 successful — got 1
- ✅ tool confirm_readback result contains 'READBACK INCOMPLETE' at least 1x — got 2
