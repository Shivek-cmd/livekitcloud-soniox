# Scenario: hindi_order

- channel: phone
- model: gemini-3.5-flash
- result: PASS

## Transcript

**SIERRA (greeting):** Hi! I'm Sierra, your virtual assistant. I speak English, Hindi, and Punjabi. How can I help you?

**USER:** नमस्ते, एक पनीर टिक्का और एक गुलाब जामुन चाहिए।
> `add_item({"quantity": 1, "item_query": "paneer tikka"})` → ⛔ NOTHING WAS ADDED — CART UNCHANGED. NEEDS SPICE — Paneer Tikka comes Mild, Medium, Spicy or Extra Spicy. Ask the customer which they want ('no preference' = Medium), then re-call add_item with spice_level. If other dishes in this turn also need one, ask about them in the SAME question, then re-call add_item once per dish.
> `add_item({"item_query": "gulab jamun", "quantity": 1})` → ADDED: 1 x ਗੁਲਾਬ ਜਾਮੁਨ (Gulab Jamun (2 pcs)). ⏎ ORDER NOW: 1 x ਗੁਲਾਬ ਜਾਮੁਨ (Gulab Jamun (2 pcs)). total=$5.99 ⏎ GUIDE: confirm the add in the customer's language — warm and in your own words, never reading these lines aloud — using the exact dish name and quantity above (quantity spoken as "one", never a digit), then keep the order moving.
**SIERRA:** नमस्ते जी! एक Gulab Jamun तो मैंने लिख लिया है। आपके Paneer Tikka के लिए spice level कितना रखूँ — mild, medium, spicy या extra spicy?

**USER:** मीडियम ठीक है।
> `add_item({"item_query": "paneer tikka", "spice_level": "Medium", "quantity": 1})` → ADDED: 1 x Paneer Tikka, note: medium. ⏎ ORDER NOW: 1 x ਗੁਲਾਬ ਜਾਮੁਨ (Gulab Jamun (2 pcs)); 1 x Paneer Tikka [medium]. total=$22.98 ⏎ GUIDE: confirm the add in the customer's language — warm and in your own words, never reading these lines aloud — using the exact dish name and quantity above (quantity spoken as "one", never a digit), then keep the order moving.
**SIERRA:** बिल्कुल जी, एक Paneer Tikka मीडियम स्पाइस के साथ भी लिख लिया है। इसके अलावा कुछ और लेंगे आप?

**USER:** बस, और कुछ नहीं।
> `record_additional_requests({"response": "no"})` → ADDITIONAL REQUESTS RECORDED: none. ⏎ ORDER NOW: 1 x ਗੁਲਾਬ ਜਾਮੁਨ (Gulab Jamun (2 pcs)); 1 x Paneer Tikka [medium]. total=$22.98 ⏎ GUIDE: acknowledge warmly in the customer's language, in your own words — do NOT re-ask about allergies, and never re-ask spice (it was settled per dish at add time) — then keep the order moving (pickup or delivery next if not set yet).
**SIERRA:** ठीक है जी। तो यह ऑर्डर आप पिकअप करेंगे या हम डिलीवरी करवा दें?

**USER:** कोई एलर्जी नहीं।
**SIERRA:** जी, बहुत बढ़िया। तो यह ऑर्डर आप खुद पिकअप करेंगे या फिर डिलीवरी करवानी है?

**USER:** Pickup कर लूंगा।
> `set_order_type({"order_type": "pickup"})` → Set to pickup. Continue the flow.
**SIERRA:** ठीक है जी, पिकअप रहेगा। आपका शुभ नाम जान सकती हूँ?

**USER:** मेरा नाम Rohan है।
> `set_customer_contact({"name": "Rohan"})` → NAME SAVED: "Rohan". ⏎ GUIDE: confirm the name briefly in the customer's language. Then ask for their phone number.
**SIERRA:** बहुत-बहुत धन्यवाद, Rohan जी। आपका फ़ोन नंबर क्या है?

**USER:** Four one six three zero four seven eight nine zero.
> `set_customer_contact({"phone": "4163047890"})` → PHONE SAVED: four, one, six, three, zero, four, seven, eight, nine, zero. ⏎ GUIDE: the number is already saved — do NOT ask the customer to repeat or re-say it. Call get_contact_readback next and read the name and number back for confirmation.
> `get_contact_readback({})` → CONTACT FACTS — read BOTH of these back to the customer, then ask if they are correct: ⏎ - name: Rohan (say it in English/Roman script, then spell it letter by letter: R-O-H-A-N) ⏎ - phone: four, one, six, three, zero, four, seven, eight, nine, zero (say every digit as a separate English word, one at a time) ⏎ GUIDE: phrase the ask warmly in your own words in the customer's language, but the name letters and the phone digits themselves must be spoken exactly as above. If the customer corrects either one, call set_customer_contact with the fix and read it back again. Only when they say both are right, call confirm_contact.
**SIERRA:** ठीक है जी, मैं एक बार आपकी डिटेल्स कन्फर्म कर लेती हूँ। आपका नाम है Rohan, R-O-H-A-N, और फ़ोन नंबर है four, one, six, three, zero, four, seven, eight, nine, zero. क्या यह सही है जी?

**USER (reactive):** Yes.
> `confirm_contact({})` → Name and phone confirmed. Continue with the order read-back (get_order_readback).
> `get_order_readback({})` → READBACK FACTS — read ALL of these to the customer in their language, then ask if everything is correct: ⏎ - 1 x ਗੁਲਾਬ ਜਾਮੁਨ (Gulab Jamun (2 pcs)) ⏎ - 1 x Paneer Tikka [medium] ⏎ - order type: pickup (say "pickup" in English) ⏎ - name: Rohan ⏎ GUIDE: phrase this warmly in your own words in the customer's language — but every item, its quantity (as a word, never a digit), and the order type must actually be spoken. Your spoken readback is checked — anything missing forces a re-read. End by asking if everything is correct.
**SIERRA:** बहुत बढ़िया जी। अब मैं आपका पूरा ऑर्डर पढ़ देती हूँ:

आपके ऑर्डर में है:
- one Gulab Jamun
- one Paneer Tikka, मीडियम स्पाइस के साथ
- और यह pickup ऑर्डर है Rohan जी के लिए।

क्या सब कुछ बिल्कुल सही है जी?

**USER:** हाँ, बिल्कुल सही है।
> `confirm_readback({})` → Order placed! INTERNAL total $22.979999999999997. Tell customer: "ਤੁਹਾਡਾ ਆਰਡਰ ਮਿਲ ਗਿਆ ਜੀ! 20-25 ਮਿੰਟ ਵਿੱਚ ਤਿਆਰ ਹੋ ਜਾਵੇਗਾ। ਬਹੁਤ ਬਹੁਤ ਧੰਨਵਾਦ ਜੀ!" Do NOT mention price or dollars.
**SIERRA:** ਤੁਹਾਡਾ ਆਰਡਰ ਮਿਲ ਗਿਆ ਜੀ! 20-25 ਮਿੰਟ ਵਿੱਚ ਤਿਆਰ ਹੋ ਜਾਵੇਗਾ। ਬਹੁਤ ਬਹੁਤ ਧੰਨਵਾਦ ਜੀ!

## Final cart

```json
{
  "v": 1,
  "status": "placed",
  "items": [
    {
      "id": "XYCGVQJC48GTT",
      "name": "Gulab Jamun (2 pcs)",
      "voice_line": "ਗੁਲਾਬ ਜਾਮੁਨ",
      "qty": 1,
      "unit_price": 5.99,
      "line_total": 5.99,
      "note": "",
      "modifiers": []
    },
    {
      "id": "M76YYRKJ33MGJ",
      "name": "Paneer Tikka",
      "voice_line": "Paneer Tikka",
      "qty": 1,
      "unit_price": 16.99,
      "line_total": 16.99,
      "note": "medium",
      "modifiers": [
        "medium"
      ]
    }
  ],
  "order_type": "pickup",
  "delivery_address": null,
  "customer": {
    "name": "Rohan",
    "phone": "4163047890"
  },
  "subtotal": 22.98,
  "delivery_charge": 0,
  "total": 22.98,
  "eta": "20-25 min",
  "order_id": "1EJAR2BDJDGC2"
}
```

## Assertions

- ✅ gates: placed order had a confirmed, current readback — readback_confirmed=True readback_revision=3 cart.revision=3
- ✅ placed — cart.placed=True
- ✅ items: exact set of dishes — cart=['Gulab Jamun (2 pcs)', 'Paneer Tikka']
- ✅ items: Paneer Tikka qty == 1 — got qty=1
- ✅ items: Paneer Tikka note contains 'medium' — got note='medium'
- ✅ items: Gulab Jamun (2 pcs) qty == 1 — got qty=1
- ✅ order_type — got 'pickup'
- ✅ customer_name — got 'Rohan'
- ✅ customer_phone — got '4163047890'
- ✅ additional_requests_recorded — got True
- ✅ readbacks: at least 1 successful — got 1
