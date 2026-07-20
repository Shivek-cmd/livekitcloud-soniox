# Scenario: no_spice_mentioned

- channel: phone
- model: gpt-4.1-mini
- result: PASS

## Transcript

**SIERRA (greeting):** Hi! I'm Sierra, your virtual assistant. I speak English, Hindi, and Punjabi. How can I help you?

**USER:** Hi, one butter chicken and one garlic naan please.
> `add_item({"item_query": "butter chicken", "quantity": 1})` → ADDED: 1 x Butter Chicken. ⏎ ORDER NOW: 1 x Butter Chicken. total=$19.99 ⏎ GUIDE: confirm the add in the customer's language — warm and in your own words, never reading these lines aloud — using the exact dish name and quantity above (quantity spoken as "one", never a digit), then keep the order moving.
> `add_item({"item_query": "garlic naan", "quantity": 1})` → ADDED: 1 x ਗਾਰਲਿਕ ਨਾਨ (Garlic Naan). ⏎ ORDER NOW: 1 x Butter Chicken; 1 x ਗਾਰਲਿਕ ਨਾਨ (Garlic Naan). total=$24.98 ⏎ GUIDE: confirm the add in the customer's language — warm and in your own words, never reading these lines aloud — using the exact dish name and quantity above (quantity spoken as "one", never a digit), then keep the order moving.
**SIERRA:** Sure thing — I've got one Butter Chicken and one ਗਾਰਲਿਕ ਨਾਨ (Garlic Naan) for you. Anything else you'd like with that?

**USER:** That's everything.
**SIERRA:** Alright, so no more items. Do you have any spice preferences, allergies, or special instructions for the kitchen?

**USER:** No, nothing — all good.
> `record_additional_requests({"response": "no"})` → ADDITIONAL REQUESTS RECORDED: none. ⏎ SPICE DEFAULTED: Butter Chicken set to medium (no preference stated — use set_item_spice if the customer actually named a level). ⏎ ORDER NOW: 1 x Butter Chicken [medium]; 1 x ਗਾਰਲਿਕ ਨਾਨ (Garlic Naan). total=$24.98 ⏎ GUIDE: acknowledge warmly in the customer's language, in your own words — do NOT re-ask about spice or allergies — then keep the order moving (pickup or delivery next if not set yet).
**SIERRA:** Great, I've noted no special requests. Would you like to pick up your order or have it delivered?

**USER:** Pickup.
> `set_order_type({"order_type": "pickup"})` → Set to pickup. Continue the flow.
**SIERRA:** Pickup it is. Can I have your name for the order, please?

**USER:** My name is Karan.
> `set_customer_contact({"name": "Karan"})` → NAME SAVED: "Karan". ⏎ GUIDE: confirm the name briefly in the customer's language. Then ask for their phone number.
**SIERRA:** Thanks, Karan. And could you please give me your phone number?

**USER:** Four one six five five five one two three four.
> `set_customer_contact({"phone": "4165551234"})` → PHONE SAVED: four, one, six, five, five, five, one, two, three, four. ⏎ GUIDE: the number is already saved — do NOT ask the customer to repeat or re-say it. Confirm it back once yourself, speaking it as English word digits exactly as in PHONE SAVED (never numerals, never Punjabi/Hindi number words), then continue the order.
**SIERRA:** Got it, your phone number is four one six five five five one two three four. Now let me read back your order to make sure everything is correct. You have one Butter Chicken and one ਗਾਰਲਿਕ ਨਾਨ (Garlic Naan) for pickup. Is that all correct?

**USER (reactive):** Yes.
> `confirm_readback({})` → No read-back has been given yet — call get_order_readback first and read it to the customer.
> `get_order_readback({})` → READBACK FACTS — read ALL of these to the customer in their language, then ask if everything is correct: ⏎ - 1 x Butter Chicken [medium] ⏎ - 1 x ਗਾਰਲਿਕ ਨਾਨ (Garlic Naan) ⏎ - order type: pickup (say "pickup" in English) ⏎ - name: Karan ⏎ GUIDE: phrase this warmly in your own words in the customer's language — but every item, its quantity (as a word, never a digit), and the order type must actually be spoken. Your spoken readback is checked — anything missing forces a re-read. End by asking if everything is correct.
**SIERRA:** Alright Karan, you have one Butter Chicken with medium spice and one ਗਾਰਲਿਕ ਨਾਨ (Garlic Naan) for pickup. Is everything correct with your order?

**USER:** Yes, that's right.
> `confirm_readback({})` → Read-back confirmed. Call place_order now.
> `place_order({})` → Order placed! INTERNAL total $24.979999999999997. Tell customer: "ਤੁਹਾਡਾ ਆਰਡਰ ਮਿਲ ਗਿਆ ਜੀ! 20-25 ਮਿੰਟ ਵਿੱਚ ਤਿਆਰ ਹੋ ਜਾਵੇਗਾ। ਬਹੁਤ ਬਹੁਤ ਧੰਨਵਾਦ ਜੀ!" Do NOT mention price or dollars.
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
    "name": "Karan",
    "phone": "4165551234"
  },
  "subtotal": 24.98,
  "delivery_charge": 0,
  "total": 24.98,
  "eta": "20-25 min",
  "order_id": "PZPYX8BWBGSF8"
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
