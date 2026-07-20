# Scenario: quantity_correction

- channel: phone
- model: gemini-3.1-flash-lite
- result: PASS

## Transcript

**SIERRA (greeting):** Hi! I'm Sierra, your virtual assistant. I speak English, Hindi, and Punjabi. How can I help you?

**USER:** Two butter chicken please, medium spice.
> `add_item({"spice_level": "medium", "item_query": "butter chicken", "quantity": 2})` → ADDED: 2 x Butter Chicken, note: medium. ⏎ ORDER NOW: 2 x Butter Chicken [medium]. total=$39.98 ⏎ GUIDE: confirm the add in the customer's language — warm and in your own words, never reading these lines aloud — using the exact dish name and quantity above (quantity spoken as "two", never a digit), then keep the order moving.
**SIERRA:** Sure thing — I've got two Butter Chicken, medium spice, down for you. Anything else I can get you with that?

**USER:** Wait — I said one, not two.
> `set_item_quantity({"item_query": "butter chicken", "quantity": 1})` → CORRECTED (not added): Butter Chicken is now 1 total. ⏎ ORDER NOW: 1 x Butter Chicken [medium]. total=$19.99 ⏎ GUIDE: reassure the customer in their language, in your own words, that it is fixed — "one" total, not a second add.
**SIERRA:** No problem at all, I've fixed that to just one Butter Chicken for you. What else can I get you?

**USER:** That's all.
> `record_additional_requests({"response": "none"})` → ADDITIONAL REQUESTS RECORDED: none. ⏎ ORDER NOW: 1 x Butter Chicken [medium]. total=$19.99 ⏎ GUIDE: acknowledge warmly in the customer's language, in your own words — do NOT re-ask about spice or allergies — then keep the order moving (pickup or delivery next if not set yet).
**SIERRA:** Got it. Would you like to pick that up, or would you like us to deliver it for you?

**USER:** No allergies, nothing else.
**SIERRA:** Understood. And would you like to pick that up, or should we deliver it to you?

**USER:** Pickup.
> `set_order_type({"order_type": "pickup"})` → Set to pickup. Continue the flow.
**SIERRA:** Sure thing, pickup it is. Could I please get your name for the order?

**USER:** It's Simran.
> `set_customer_contact({"name": "Simran"})` → NAME SAVED: "Simran". ⏎ GUIDE: confirm the name briefly in the customer's language. Then ask for their phone number.
**SIERRA:** Thanks, Simran. And could I have a phone number for the order, please?

**USER:** Nine zero five five five five one one two two.
> `set_customer_contact({"phone": "9055551122"})` → PHONE SAVED: nine, zero, five, five, five, five, one, one, two, two. ⏎ GUIDE: the number is already saved — do NOT ask the customer to repeat or re-say it. Confirm it back once yourself, speaking it as English word digits exactly as in PHONE SAVED (never numerals, never Punjabi/Hindi number words), then continue the order.
> `get_order_readback({})` → READBACK FACTS — read ALL of these to the customer in their language, then ask if everything is correct: ⏎ - 1 x Butter Chicken [medium] ⏎ - order type: pickup (say "pickup" in English) ⏎ - name: Simran ⏎ GUIDE: phrase this warmly in your own words in the customer's language — but every item, its quantity (as a word, never a digit), and the order type must actually be spoken. Your spoken readback is checked — anything missing forces a re-read. End by asking if everything is correct.
**SIERRA:** Thanks, Simran. I have your phone number as nine zero five five five five one one two two.

So, I have one Butter Chicken, medium spice, for pickup under the name Simran. Does that all look correct to you?

**USER (reactive):** Yes.
> `confirm_readback({})` → Read-back confirmed. Call place_order now.
> `place_order({})` → Order placed! INTERNAL total $19.99. Tell customer: "ਤੁਹਾਡਾ ਆਰਡਰ ਮਿਲ ਗਿਆ ਜੀ! 20-25 ਮਿੰਟ ਵਿੱਚ ਤਿਆਰ ਹੋ ਜਾਵੇਗਾ। ਬਹੁਤ ਬਹੁਤ ਧੰਨਵਾਦ ਜੀ!" Do NOT mention price or dollars.
**SIERRA:** ਤੁਹਾਡਾ ਆਰਡਰ ਮਿਲ ਗਿਆ ਜੀ! 20-25 ਮਿੰਟ ਵਿੱਚ ਤਿਆਰ ਹੋ ਜਾਵੇਗਾ। ਬਹੁਤ ਬਹੁਤ ਧੰਨਵਾਦ ਜੀ!

**USER:** Yes, perfect.
**SIERRA:** ORDER COMPLETE — goodbye already spoken

**USER:** Yes.
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
    }
  ],
  "order_type": "pickup",
  "delivery_address": null,
  "customer": {
    "name": "Simran",
    "phone": "9055551122"
  },
  "subtotal": 19.99,
  "delivery_charge": 0,
  "total": 19.99,
  "eta": "20-25 min",
  "order_id": "1T4QBD4FJ74MW"
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
- ✅ customer_phone — got '9055551122'
- ✅ additional_requests_recorded — got True
- ✅ readbacks: at least 1 successful — got 1
