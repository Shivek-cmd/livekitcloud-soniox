# Scenario: punjabi_order

- channel: phone
- model: gemini-3.5-flash
- result: PASS

## Transcript

**SIERRA (greeting):** Hi! I'm Sierra, your virtual assistant. I speak English, Hindi, and Punjabi. How can I help you?

**USER:** ਸਤ ਸ੍ਰੀ ਅਕਾਲ ਜੀ, ਦੋ ਬਟਰ ਚਿਕਨ ਲਗਾ ਦਿਓ।
> `add_item({"item_query": "butter chicken", "quantity": 2})` → ⛔ NOTHING WAS ADDED — CART UNCHANGED. NEEDS SPICE — Butter Chicken comes Mild, Medium, Spicy or Extra Spicy. Ask the customer which they want ('no preference' = Medium), then re-call add_item with spice_level. If other dishes in this turn also need one, ask about them in the SAME question, then re-call add_item once per dish.
**SIERRA:** ਸਤਿ ਸ੍ਰੀ ਅਕਾਲ ਜੀ! ਦੋ Butter Chicken ਬਿਲਕੁਲ ਲਿਖ ਲੈਂਦੀ ਹਾਂ। ਤੁਸੀਂ spice ਕਿੰਨਾ ਪਸੰਦ ਕਰੋਗੇ ਜੀ — mild, medium, spicy, ਜਾਂ extra spicy?

**USER:** ਮੀਡੀਅਮ ਠੀਕ ਹੈ ਜੀ।
> `add_item({"quantity": 2, "spice_level": "Medium", "item_query": "butter chicken"})` → ADDED: 2 x Butter Chicken, note: medium. ⏎ ORDER NOW: 2 x Butter Chicken [medium]. total=$39.98 ⏎ GUIDE: confirm the add in the customer's language — warm and in your own words, never reading these lines aloud — using the exact dish name and quantity above (quantity spoken as "two", never a digit), then keep the order moving.
**SIERRA:** ਠੀਕ ਹੈ ਜੀ, ਦੋ Butter Chicken, medium ਲਿਖ ਲਏ ਹਨ। ਹੋਰ ਕੁਝ ਚਾਹੀਦਾ ਹੈ ਜੀ?

**USER:** ਬੱਸ ਜੀ, ਹੋਰ ਕੁਝ ਨਹੀਂ।
> `record_additional_requests({"response": "no"})` → ADDITIONAL REQUESTS RECORDED: none. ⏎ ORDER NOW: 2 x Butter Chicken [medium]. total=$39.98 ⏎ GUIDE: acknowledge warmly in the customer's language, in your own words — do NOT re-ask about allergies, and never re-ask spice (it was settled per dish at add time) — then keep the order moving (pickup or delivery next if not set yet).
**SIERRA:** ਠੀਕ ਹੈ ਜੀ। ਇਹ ਆਰਡਰ ਤੁਸੀਂ pickup ਕਰਨਾ ਹੈ ਜਾਂ delivery ਕਰਵਾਉਣੀ ਹੈ ਜੀ?

**USER:** ਕੋਈ ਐਲਰਜੀ ਨਹੀਂ ਜੀ।
**SIERRA:** ਠੀਕ ਹੈ ਜੀ, ਬਹੁਤ ਵਧੀਆ। ਇਹ ਆਰਡਰ ਤੁਸੀਂ pickup ਕਰਨਾ ਹੈ ਜਾਂ delivery ਕਰਵਾਉਣੀ ਹੈ ਜੀ?

**USER:** Pickup ਜੀ।
> `set_order_type({"order_type": "pickup"})` → Set to pickup. Continue the flow.
**SIERRA:** ਠੀਕ ਹੈ ਜੀ, pickup ਕਰ ਦਿੱਤਾ ਹੈ। ਮੈਂ ਤੁਹਾਡਾ ਨਾਮ ਜਾਣ ਸਕਦੀ ਹਾਂ ਜੀ?

**USER:** ਮੇਰਾ ਨਾਮ Gurpreet ਹੈ।
> `set_customer_contact({"name": "Gurpreet"})` → NAME SAVED: "Gurpreet". ⏎ GUIDE: confirm the name briefly in the customer's language. Then ask for their phone number.
**SIERRA:** ਠੀਕ ਹੈ ਜੀ Gurpreet, ਤੇ ਤੁਹਾਡਾ ਫ਼ੋਨ ਨੰਬਰ ਕੀ ਹੈ ਜੀ?

**USER:** Six four seven three zero four three four five six.
> `set_customer_contact({"phone": "6473043456"})` → PHONE SAVED: six, four, seven, three, zero, four, three, four, five, six. ⏎ GUIDE: the number is already saved — do NOT ask the customer to repeat or re-say it. Call get_contact_readback next and read the name and number back for confirmation.
> `get_contact_readback({})` → CONTACT FACTS — read BOTH of these back to the customer, then ask if they are correct: ⏎ - name: Gurpreet (say it in English/Roman script, then spell it letter by letter: G-U-R-P-R-E-E-T) ⏎ - phone: six, four, seven, three, zero, four, three, four, five, six (say every digit as a separate English word, one at a time) ⏎ GUIDE: phrase the ask warmly in your own words in the customer's language, but the name letters and the phone digits themselves must be spoken exactly as above. If the customer corrects either one, call set_customer_contact with the fix and read it back again. Only when they say both are right, call confirm_contact.
**SIERRA:** ਠੀਕ ਹੈ ਜੀ, ਮੈਂ ਤੁਹਾਡੀ contact details confirm ਕਰ ਲਵਾਂ। ਨਾਮ ਹੈ Gurpreet, spelled G-U-R-P-R-E-E-T, ਅਤੇ ਫ਼ੋਨ ਨੰਬਰ ਹੈ six, four, seven, three, zero, four, three, four, five, six. ਕੀ ਇਹ ਬਿਲਕੁਲ ਠੀਕ ਹੈ ਜੀ?

**USER (reactive):** Yes.
> `confirm_contact({})` → Name and phone confirmed. Continue with the order read-back (get_order_readback).
> `get_order_readback({})` → READBACK FACTS — read ALL of these to the customer in their language, then ask if everything is correct: ⏎ - 2 x Butter Chicken [medium] ⏎ - order type: pickup (say "pickup" in English) ⏎ - name: Gurpreet ⏎ GUIDE: phrase this warmly in your own words in the customer's language — but every item, its quantity (as a word, never a digit), and the order type must actually be spoken. Your spoken readback is checked — anything missing forces a re-read. End by asking if everything is correct.
**SIERRA:** ਬਹੁਤ ਵਧੀਆ ਜੀ। ਮੈਂ ਤੁਹਾਡਾ ਆਰਡਰ confirm ਕਰ ਲਵਾਂ: ਤੁਹਾਡੇ ਕੋਲ two Butter Chicken, medium ਹਨ, ਅਤੇ ਇਹ pickup ਲਈ ਹੈ Gurpreet ਦੇ ਨਾਮ 'ਤੇ। ਕੀ ਸਭ ਕੁਝ ਬਿਲਕੁਲ ਠੀਕ ਹੈ ਜੀ?

**USER:** ਹਾਂ ਜੀ, ਬਿਲਕੁਲ ਠੀਕ ਹੈ।
> `confirm_readback({})` → Order placed! INTERNAL total $39.98. Tell customer: "ਤੁਹਾਡਾ ਆਰਡਰ ਮਿਲ ਗਿਆ ਜੀ! 20-25 ਮਿੰਟ ਵਿੱਚ ਤਿਆਰ ਹੋ ਜਾਵੇਗਾ। ਬਹੁਤ ਬਹੁਤ ਧੰਨਵਾਦ ਜੀ!" Do NOT mention price or dollars.
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
    "name": "Gurpreet",
    "phone": "6473043456"
  },
  "subtotal": 39.98,
  "delivery_charge": 0,
  "total": 39.98,
  "eta": "20-25 min",
  "order_id": "KCSK8P0R1D2KY"
}
```

## Assertions

- ✅ gates: placed order had a confirmed, current readback — readback_confirmed=True readback_revision=2 cart.revision=2
- ✅ placed — cart.placed=True
- ✅ items: exact set of dishes — cart=['Butter Chicken']
- ✅ items: Butter Chicken qty == 2 — got qty=2
- ✅ items: Butter Chicken note contains 'medium' — got note='medium'
- ✅ order_type — got 'pickup'
- ✅ customer_name — got 'Gurpreet'
- ✅ customer_phone — got '6473043456'
- ✅ additional_requests_recorded — got True
- ✅ readbacks: at least 1 successful — got 1
