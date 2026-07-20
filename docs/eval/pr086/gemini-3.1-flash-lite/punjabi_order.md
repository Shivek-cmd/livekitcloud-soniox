# Scenario: punjabi_order

- channel: phone
- model: gemini-3.1-flash-lite
- result: PASS

## Transcript

**SIERRA (greeting):** Hi! I'm Sierra, your virtual assistant. I speak English, Hindi, and Punjabi. How can I help you?

**USER:** ਸਤ ਸ੍ਰੀ ਅਕਾਲ ਜੀ, ਦੋ ਬਟਰ ਚਿਕਨ ਲਗਾ ਦਿਓ।
> `add_item({"quantity": 2, "item_query": "butter chicken"})` → ADDED: 2 x Butter Chicken. ⏎ ORDER NOW: 2 x Butter Chicken. total=$39.98 ⏎ GUIDE: confirm the add in the customer's language — warm and in your own words, never reading these lines aloud — using the exact dish name and quantity above (quantity spoken as "two", never a digit), then keep the order moving.
**SIERRA:** ਸਤ ਸ੍ਰੀ ਅਕਾਲ ਜੀ! ਮੈਂ ਦੋ Butter Chicken ਲਿਖ ਲਏ ਹਨ ਜੀ। ਹੋਰ ਕੁਝ ਚਾਹੀਦਾ ਜੀ?

**USER:** ਬੱਸ ਜੀ, ਹੋਰ ਕੁਝ ਨਹੀਂ।
> `record_additional_requests({"response": "none"})` → ADDITIONAL REQUESTS RECORDED: none. ⏎ SPICE DEFAULTED: Butter Chicken set to medium (no preference stated — use set_item_spice if the customer actually named a level). ⏎ ORDER NOW: 2 x Butter Chicken [medium]. total=$39.98 ⏎ GUIDE: acknowledge warmly in the customer's language, in your own words — do NOT re-ask about spice or allergies — then keep the order moving (pickup or delivery next if not set yet).
**SIERRA:** ਠੀਕ ਹੈ ਜੀ। ਇਹ ਆਰਡਰ ਤੁਸੀਂ Pickup ਲਈ ਲੈਣਾ ਹੈ ਜਾਂ ਅਸੀਂ Delivery ਕਰਵਾ ਦੇਈਏ?

**USER:** ਮੀਡੀਅਮ ਠੀਕ ਹੈ ਜੀ, ਕੋਈ ਐਲਰਜੀ ਨਹੀਂ।
**SIERRA:** ਠੀਕ ਹੈ ਜੀ, ਮੈਂ ਨੋਟ ਕਰ ਲਿਆ ਹੈ। ਇਹ ਆਰਡਰ ਤੁਸੀਂ Pickup ਲਈ ਲੈਣਾ ਹੈ ਜਾਂ ਅਸੀਂ Delivery ਕਰਵਾ ਦੇਈਏ?

**USER:** Pickup ਜੀ।
> `set_order_type({"order_type": "pickup"})` → Set to pickup. Continue the flow.
**SIERRA:** ਠੀਕ ਹੈ ਜੀ, Pickup ਲਈ। ਤੁਹਾਡਾ ਨਾਮ ਕੀ ਹੈ ਜੀ?

**USER:** ਮੇਰਾ ਨਾਮ Gurpreet ਹੈ।
> `set_customer_contact({"name": "Gurpreet"})` → NAME SAVED: "Gurpreet". ⏎ GUIDE: confirm the name briefly in the customer's language. Then ask for their phone number.
**SIERRA:** ਧੰਨਵਾਦ ਜੀ, Gurpreet ਜੀ। ਆਪਣਾ ਫੋਨ ਨੰਬਰ ਦੱਸੋਗੇ ਜੀ?

**USER:** Six four seven five five five three four five six.
> `set_customer_contact({"phone": "6475553456"})` → PHONE SAVED: six, four, seven, five, five, five, three, four, five, six. ⏎ GUIDE: the number is already saved — do NOT ask the customer to repeat or re-say it. Confirm it back once yourself, speaking it as English word digits exactly as in PHONE SAVED (never numerals, never Punjabi/Hindi number words), then continue the order.
> `get_order_readback({})` → READBACK FACTS — read ALL of these to the customer in their language, then ask if everything is correct: ⏎ - 2 x Butter Chicken [medium] ⏎ - order type: pickup (say "pickup" in English) ⏎ - name: Gurpreet ⏎ GUIDE: phrase this warmly in your own words in the customer's language — but every item, its quantity (as a word, never a digit), and the order type must actually be spoken. Your spoken readback is checked — anything missing forces a re-read. End by asking if everything is correct.
**SIERRA:** ਠੀਕ ਹੈ ਜੀ, Gurpreet ਜੀ। ਮੈਂ ਤੁਹਾਡਾ ਆਰਡਰ ਚੈੱਕ ਕਰ ਲਿਆ ਹੈ: ਦੋ Butter Chicken [medium] ਹਨ, ਇਹ Pickup ਲਈ ਹੈ, ਅਤੇ ਤੁਹਾਡਾ ਫੋਨ ਨੰਬਰ six four seven five five five three four five six ਹੈ। ਕੀ ਇਹ ਸਭ ਸਹੀ ਹੈ ਜੀ?

**USER (reactive):** Yes.
> `confirm_readback({})` → Read-back confirmed. Call place_order now.
> `place_order({})` → Order placed! INTERNAL total $39.98. Tell customer: "ਤੁਹਾਡਾ ਆਰਡਰ ਮਿਲ ਗਿਆ ਜੀ! 20-25 ਮਿੰਟ ਵਿੱਚ ਤਿਆਰ ਹੋ ਜਾਵੇਗਾ। ਬਹੁਤ ਬਹੁਤ ਧੰਨਵਾਦ ਜੀ!" Do NOT mention price or dollars.
**SIERRA:** ਤੁਹਾਡਾ ਆਰਡਰ ਮਿਲ ਗਿਆ ਜੀ! 20-25 ਮਿੰਟ ਵਿੱਚ ਤਿਆਰ ਹੋ ਜਾਵੇਗਾ। ਬਹੁਤ ਬਹੁਤ ਧੰਨਵਾਦ ਜੀ!

**USER:** ਹਾਂ ਜੀ, ਬਿਲਕੁਲ ਠੀਕ ਹੈ।
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
    "phone": "6475553456"
  },
  "subtotal": 39.98,
  "delivery_charge": 0,
  "total": 39.98,
  "eta": "20-25 min",
  "order_id": "XT3HMYYTBGZN8"
}
```

## Assertions

- ✅ gates: placed order had a confirmed, current readback — readback_confirmed=True readback_revision=3 cart.revision=3
- ✅ placed — cart.placed=True
- ✅ items: exact set of dishes — cart=['Butter Chicken']
- ✅ items: Butter Chicken qty == 2 — got qty=2
- ✅ items: Butter Chicken note contains 'medium' — got note='medium'
- ✅ order_type — got 'pickup'
- ✅ customer_name — got 'Gurpreet'
- ✅ customer_phone — got '6475553456'
- ✅ additional_requests_recorded — got True
- ✅ readbacks: at least 1 successful — got 1
