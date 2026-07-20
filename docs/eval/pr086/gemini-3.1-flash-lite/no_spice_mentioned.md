# Scenario: no_spice_mentioned

- channel: phone
- model: gemini-3.1-flash-lite
- result: PASS

## Transcript

**SIERRA (greeting):** Hi! I'm Sierra, your virtual assistant. I speak English, Hindi, and Punjabi. How can I help you?

**USER:** Hi, one butter chicken and one garlic naan please.
> `add_item({"quantity": 1, "item_query": "butter chicken"})` → ADDED: 1 x Butter Chicken. ⏎ ORDER NOW: 1 x Butter Chicken. total=$19.99 ⏎ GUIDE: confirm the add in the customer's language — warm and in your own words, never reading these lines aloud — using the exact dish name and quantity above (quantity spoken as "one", never a digit), then keep the order moving.
> `add_item({"item_query": "garlic naan", "quantity": 1})` → ADDED: 1 x ਗਾਰਲਿਕ ਨਾਨ (Garlic Naan). ⏎ ORDER NOW: 1 x Butter Chicken; 1 x ਗਾਰਲਿਕ ਨਾਨ (Garlic Naan). total=$24.98 ⏎ GUIDE: confirm the add in the customer's language — warm and in your own words, never reading these lines aloud — using the exact dish name and quantity above (quantity spoken as "one", never a digit), then keep the order moving.
**SIERRA:** Sure thing — I've got one Butter Chicken and one Garlic Naan down for you. Anything else I can get you with that?

**USER:** That's everything.
> `record_additional_requests({"response": "none"})` → ADDITIONAL REQUESTS RECORDED: none. ⏎ SPICE DEFAULTED: Butter Chicken set to medium (no preference stated — use set_item_spice if the customer actually named a level). ⏎ ORDER NOW: 1 x Butter Chicken [medium]; 1 x ਗਾਰਲਿਕ ਨਾਨ (Garlic Naan). total=$24.98 ⏎ GUIDE: acknowledge warmly in the customer's language, in your own words — do NOT re-ask about spice or allergies — then keep the order moving (pickup or delivery next if not set yet).
**SIERRA:** Great, thanks for letting me know. Would you like to pick this up, or should we deliver it to you?

**USER:** No, nothing — all good.
> `set_order_type({"order_type": "pickup"})` → Set to pickup. Continue the flow.
**SIERRA:** Got it, that'll be for pickup. Could I please get your name for the order?

**USER:** Pickup.
**SIERRA:** Sure thing, I have that set for pickup. May I have your name for the order, please?

**USER:** My name is Karan.
> `set_customer_contact({"name": "Karan"})` → NAME SAVED: "Karan". ⏎ GUIDE: confirm the name briefly in the customer's language. Then ask for their phone number.
**SIERRA:** Thanks, Karan. And could I please get a phone number for the order?

**USER:** Four one six five five five one two three four.
> `set_customer_contact({"phone": "4165551234"})` → PHONE SAVED: four, one, six, five, five, five, one, two, three, four. ⏎ GUIDE: the number is already saved — do NOT ask the customer to repeat or re-say it. Confirm it back once yourself, speaking it as English word digits exactly as in PHONE SAVED (never numerals, never Punjabi/Hindi number words), then continue the order.
> `get_order_readback({})` → READBACK FACTS — read ALL of these to the customer in their language, then ask if everything is correct: ⏎ - 1 x Butter Chicken [medium] ⏎ - 1 x ਗਾਰਲਿਕ ਨਾਨ (Garlic Naan) ⏎ - order type: pickup (say "pickup" in English) ⏎ - name: Karan ⏎ GUIDE: phrase this warmly in your own words in the customer's language — but every item, its quantity (as a word, never a digit), and the order type must actually be spoken. Your spoken readback is checked — anything missing forces a re-read. End by asking if everything is correct.
**SIERRA:** Thanks, Karan. I have your phone number as four one six, five five five, one two three four.

So, just to confirm, I have one Butter Chicken, medium, and one Garlic Naan for pickup under the name Karan. Is everything correct?

**USER (reactive):** Yes.
> `confirm_readback({})` → Read-back confirmed. Call place_order now.
> `place_order({})` → Order placed! INTERNAL total $24.979999999999997. Tell customer: "ਤੁਹਾਡਾ ਆਰਡਰ ਮਿਲ ਗਿਆ ਜੀ! 20-25 ਮਿੰਟ ਵਿੱਚ ਤਿਆਰ ਹੋ ਜਾਵੇਗਾ। ਬਹੁਤ ਬਹੁਤ ਧੰਨਵਾਦ ਜੀ!" Do NOT mention price or dollars.
**SIERRA:** ਤੁਹਾਡਾ ਆਰਡਰ ਮਿਲ ਗਿਆ ਜੀ! 20-25 ਮਿੰਟ ਵਿੱਚ ਤਿਆਰ ਹੋ ਜਾਵੇਗਾ। ਬਹੁਤ ਬਹੁਤ ਧੰਨਵਾਦ ਜੀ!

**USER:** Yes, that's right.
**SIERRA:** ORDER COMPLETE — goodbye already spoken

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
    "name": "Karan",
    "phone": "4165551234"
  },
  "subtotal": 24.98,
  "delivery_charge": 0,
  "total": 24.98,
  "eta": "20-25 min",
  "order_id": "JV933MA995M9J"
}
```

## Assertions

- ✅ gates: placed order had a confirmed, current readback — readback_confirmed=True readback_revision=4 cart.revision=4
- ✅ placed — cart.placed=True
- ✅ items: exact set of dishes — cart=['Butter Chicken', 'Garlic Naan']
- ✅ items: Butter Chicken qty == 1 — got qty=1
- ✅ items: Butter Chicken note contains 'medium' — got note='medium'
- ✅ items: Garlic Naan qty == 1 — got qty=1
- ✅ order_type — got 'pickup'
- ✅ customer_name — got 'Karan'
- ✅ customer_phone — got '4165551234'
- ✅ additional_requests_recorded — got True
- ✅ readbacks: at least 1 successful — got 1
