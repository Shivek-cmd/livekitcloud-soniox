# Scenario: sloppy_readback

- channel: phone
- model: gemini-3.5-flash
- result: PASS

## Transcript

**SIERRA (greeting):** Hi! I'm Sierra, your virtual assistant. I speak English, Hindi, and Punjabi. How can I help you?

**USER:** Hi, can I get two butter chicken and one garlic naan please?
> `add_item({"quantity": 2, "item_query": "butter chicken"})` → ADDED: 2 x Butter Chicken. ⏎ ORDER NOW: 2 x Butter Chicken. total=$39.98 ⏎ GUIDE: confirm the add in the customer's language — warm and in your own words, never reading these lines aloud — using the exact dish name and quantity above (quantity spoken as "two", never a digit), then keep the order moving.
> `add_item({"quantity": 1, "item_query": "garlic naan"})` → ADDED: 1 x ਗਾਰਲਿਕ ਨਾਨ (Garlic Naan). ⏎ ORDER NOW: 2 x Butter Chicken; 1 x ਗਾਰਲਿਕ ਨਾਨ (Garlic Naan). total=$44.97 ⏎ GUIDE: confirm the add in the customer's language — warm and in your own words, never reading these lines aloud — using the exact dish name and quantity above (quantity spoken as "one", never a digit), then keep the order moving.
**SIERRA:** You got it! I've added two Butter Chicken and one ਗਾਰਲਿਕ ਨਾਨ to your order. What else can I get started for you today?

**USER:** That's everything, thanks.
> `record_additional_requests({"response": "no"})` → ADDITIONAL REQUESTS RECORDED: none. ⏎ SPICE DEFAULTED: Butter Chicken set to medium (no preference stated — use set_item_spice if the customer actually named a level). ⏎ ORDER NOW: 2 x Butter Chicken [medium]; 1 x ਗਾਰਲਿਕ ਨਾਨ (Garlic Naan). total=$44.97 ⏎ GUIDE: acknowledge warmly in the customer's language, in your own words — do NOT re-ask about spice or allergies — then keep the order moving (pickup or delivery next if not set yet).
**SIERRA:** Perfect. And will this order be for pickup, or would you like us to deliver it to you?

**USER:** Medium spice is fine, and no allergies.
**SIERRA:** Thanks for letting me know! And is this order going to be for pickup, or would you like delivery?

**USER:** Pickup please.
> `set_order_type({"order_type": "pickup"})` → Set to pickup. Continue the flow.
**SIERRA:** Sure thing, pickup it is. Can I get your name for the order, please?

**USER:** My name is Harpreet.
> `set_customer_contact({"name": "Harpreet"})` → NAME SAVED: "Harpreet". ⏎ GUIDE: confirm the name briefly in the customer's language. Then ask for their phone number.
**SIERRA:** Great, Harpreet. And what is a good phone number to reach you at?

**USER:** Six four seven five five five one two one two.
> `set_customer_contact({"phone": "6475551212"})` → PHONE SAVED: six, four, seven, five, five, five, one, two, one, two. ⏎ GUIDE: the number is already saved — do NOT ask the customer to repeat or re-say it. Confirm it back once yourself, speaking it as English word digits exactly as in PHONE SAVED (never numerals, never Punjabi/Hindi number words), then continue the order.
> `get_order_readback({})` → READBACK FACTS — read ALL of these to the customer in their language, then ask if everything is correct: ⏎ - 2 x Butter Chicken [medium] ⏎ - 1 x ਗਾਰਲਿਕ ਨਾਨ (Garlic Naan) ⏎ - order type: pickup (say "pickup" in English) ⏎ - name: Harpreet ⏎ GUIDE: phrase this warmly in your own words in the customer's language — but every item, its quantity (as a word, never a digit), and the order type must actually be spoken. Your spoken readback is checked — anything missing forces a re-read. End by asking if everything is correct.
**SIERRA:** Awesome, I've got your phone number down as six, four, seven, five, five, five, one, two, one, two. 

Let me read your order back to make sure everything is correct: I have two Butter Chicken with medium spice and one ਗਾਰਲਿਕ ਨਾਨ for pickup under the name Harpreet. Does that all sound right to you?

**USER (reactive):** Yes.
> `confirm_readback({})` → READBACK INCOMPLETE — the customer has not heard the full order: ⏎ - you never said 'ਗਾਰਲਿਕ ਨਾਨ' ⏎ Read ALL the READBACK FACTS again in the customer's language, then ask again if everything is correct.
> `get_order_readback({})` → READBACK FACTS — read ALL of these to the customer in their language, then ask if everything is correct: ⏎ - 2 x Butter Chicken [medium] ⏎ - 1 x ਗਾਰਲਿਕ ਨਾਨ (Garlic Naan) ⏎ - order type: pickup (say "pickup" in English) ⏎ - name: Harpreet ⏎ GUIDE: phrase this warmly in your own words in the customer's language — but every item, its quantity (as a word, never a digit), and the order type must actually be spoken. Your spoken readback is checked — anything missing forces a re-read. End by asking if everything is correct.
**SIERRA:** My apologies, let me read that back one more time to be absolutely sure. I have two Butter Chicken with medium spice and one ਗਾਰਲਿਕ ਨਾਨ for pickup under the name Harpreet. Is everything correct?

**USER:** Yes, that's correct.
> `confirm_readback({})` → Read-back confirmed. Call place_order now.
> `place_order({})` → Order placed! INTERNAL total $44.97. Tell customer: "ਤੁਹਾਡਾ ਆਰਡਰ ਮਿਲ ਗਿਆ ਜੀ! 20-25 ਮਿੰਟ ਵਿੱਚ ਤਿਆਰ ਹੋ ਜਾਵੇਗਾ। ਬਹੁਤ ਬਹੁਤ ਧੰਨਵਾਦ ਜੀ!" Do NOT mention price or dollars.
**SIERRA:** ਤੁਹਾਡਾ ਆਰਡਰ ਮਿਲ ਗਿਆ ਜੀ! 20-25 ਮਿੰਟ ਵਿੱਚ ਤਿਆਰ ਹੋ ਜਾਵੇਗਾ। ਬਹੁਤ ਬਹੁਤ ਧੰਨਵਾਦ ਜੀ!

**USER:** Yes, everything is correct.
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
      "qty": 2,
      "unit_price": 19.99,
      "line_total": 39.98,
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
    "name": "Harpreet",
    "phone": "6475551212"
  },
  "subtotal": 44.97,
  "delivery_charge": 0,
  "total": 44.97,
  "eta": "20-25 min",
  "order_id": "N54ZEW4N6ZWRG"
}
```

## Assertions

- ✅ gates: placed order had a confirmed, current readback — readback_confirmed=True readback_revision=4 cart.revision=4
- ✅ placed — cart.placed=True
- ✅ items: exact set of dishes — cart=['Butter Chicken', 'Garlic Naan']
- ✅ items: Butter Chicken qty == 2 — got qty=2
- ✅ items: Butter Chicken note contains 'medium' — got note='medium'
- ✅ items: Garlic Naan qty == 1 — got qty=1
- ✅ order_type — got 'pickup'
- ✅ customer_name — got 'Harpreet'
- ✅ customer_phone — got '6475551212'
- ✅ additional_requests_recorded — got True
- ✅ readbacks: at least 1 successful — got 2
- ✅ tool confirm_readback result contains 'READBACK INCOMPLETE' at least 1x — got 1
