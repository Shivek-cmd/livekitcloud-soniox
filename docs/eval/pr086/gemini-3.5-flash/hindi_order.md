# Scenario: hindi_order

- channel: phone
- model: gemini-3.5-flash
- result: PASS

## Transcript

**SIERRA (greeting):** Hi! I'm Sierra, your virtual assistant. I speak English, Hindi, and Punjabi. How can I help you?

**USER:** नमस्ते, एक पनीर टिक्का और एक गुलाब जामुन चाहिए।
> `add_item({"quantity": 1, "item_query": "paneer tikka"})` → ADDED: 1 x Paneer Tikka. ⏎ ORDER NOW: 1 x Paneer Tikka. total=$16.99 ⏎ GUIDE: confirm the add in the customer's language — warm and in your own words, never reading these lines aloud — using the exact dish name and quantity above (quantity spoken as "one", never a digit), then keep the order moving.
> `add_item({"quantity": 1, "item_query": "gulab jamun"})` → ADDED: 1 x ਗੁਲਾਬ ਜਾਮੁਨ (Gulab Jamun (2 pcs)). ⏎ ORDER NOW: 1 x Paneer Tikka; 1 x ਗੁਲਾਬ ਜਾਮੁਨ (Gulab Jamun (2 pcs)). total=$22.98 ⏎ GUIDE: confirm the add in the customer's language — warm and in your own words, never reading these lines aloud — using the exact dish name and quantity above (quantity spoken as "one", never a digit), then keep the order moving.
**SIERRA:** नमस्ते जी! बिल्कुल, मैंने आपके लिए एक Paneer Tikka और एक Gulab Jamun लिख लिया है। इसके अलावा कुछ और लेंगे आप?

**USER:** बस, और कुछ नहीं।
> `record_additional_requests({"response": "no"})` → ADDITIONAL REQUESTS RECORDED: none. ⏎ SPICE DEFAULTED: Paneer Tikka set to medium (no preference stated — use set_item_spice if the customer actually named a level). ⏎ ORDER NOW: 1 x Paneer Tikka [medium]; 1 x ਗੁਲਾਬ ਜਾਮੁਨ (Gulab Jamun (2 pcs)). total=$22.98 ⏎ GUIDE: acknowledge warmly in the customer's language, in your own words — do NOT re-ask about spice or allergies — then keep the order moving (pickup or delivery next if not set yet).
**SIERRA:** ठीक है जी। यह ऑर्डर आप यहाँ से पिकअप करेंगे या हम आपके घर डिलीवर करवा दें?

**USER:** मीडियम ठीक है, कोई एलर्जी नहीं।
**SIERRA:** जी, बिल्कुल ठीक है। तो यह ऑर्डर आप पिकअप करेंगे या फिर डिलीवरी करवानी है?

**USER:** Pickup कर लूंगा।
> `set_order_type({"order_type": "pickup"})` → Set to pickup. Continue the flow.
**SIERRA:** ज़रूर जी, पिकअप के लिए सेट कर दिया है। आपका शुभ नाम जान सकती हूँ?

**USER:** मेरा नाम Rohan है।
> `set_customer_contact({"name": "Rohan"})` → NAME SAVED: "Rohan". ⏎ GUIDE: confirm the name briefly in the customer's language. Then ask for their phone number.
**SIERRA:** बहुत-बहुत धन्यवाद, रोहन जी। आपका फ़ोन नंबर क्या है?

**USER:** Four one six five five five seven eight nine zero.
> `set_customer_contact({"phone": "4165557890"})` → PHONE SAVED: four, one, six, five, five, five, seven, eight, nine, zero. ⏎ GUIDE: the number is already saved — do NOT ask the customer to repeat or re-say it. Confirm it back once yourself, speaking it as English word digits exactly as in PHONE SAVED (never numerals, never Punjabi/Hindi number words), then continue the order.
> `get_order_readback({})` → READBACK FACTS — read ALL of these to the customer in their language, then ask if everything is correct: ⏎ - 1 x Paneer Tikka [medium] ⏎ - 1 x ਗੁਲਾਬ ਜਾਮੁਨ (Gulab Jamun (2 pcs)) ⏎ - order type: pickup (say "pickup" in English) ⏎ - name: Rohan ⏎ GUIDE: phrase this warmly in your own words in the customer's language — but every item, its quantity (as a word, never a digit), and the order type must actually be spoken. Your spoken readback is checked — anything missing forces a re-read. End by asking if everything is correct.
**SIERRA:** जी, मैंने आपका नंबर four, one, six, five, five, five, seven, eight, nine, zero लिख लिया है। 

तो रोहन जी, आपका ऑर्डर इस तरह है:
- एक Paneer Tikka
- एक Gulab Jamun
- और यह ऑर्डर pickup के लिए है।

क्या सब कुछ बिल्कुल सही है जी?

**USER (reactive):** Yes.
> `confirm_readback({})` → Read-back confirmed. Call place_order now.
> `place_order({})` → Order placed! INTERNAL total $22.979999999999997. Tell customer: "ਤੁਹਾਡਾ ਆਰਡਰ ਮਿਲ ਗਿਆ ਜੀ! 20-25 ਮਿੰਟ ਵਿੱਚ ਤਿਆਰ ਹੋ ਜਾਵੇਗਾ। ਬਹੁਤ ਬਹੁਤ ਧੰਨਵਾਦ ਜੀ!" Do NOT mention price or dollars.
**SIERRA:** ਤੁਹਾਡਾ ਆਰਡਰ ਮਿਲ ਗਿਆ ਜੀ! 20-25 ਮਿੰਟ ਵਿੱਚ ਤਿਆਰ ਹੋ ਜਾਵੇਗਾ। ਬਹੁਤ ਬਹੁਤ ਧੰਨਵਾਦ ਜੀ!

**USER:** हाँ, बिल्कुल सही है।
**SIERRA:** 

## Final cart

```json
{
  "v": 1,
  "status": "placed",
  "items": [
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
    },
    {
      "id": "XYCGVQJC48GTT",
      "name": "Gulab Jamun (2 pcs)",
      "voice_line": "ਗੁਲਾਬ ਜਾਮੁਨ",
      "qty": 1,
      "unit_price": 5.99,
      "line_total": 5.99,
      "note": "",
      "modifiers": []
    }
  ],
  "order_type": "pickup",
  "delivery_address": null,
  "customer": {
    "name": "Rohan",
    "phone": "4165557890"
  },
  "subtotal": 22.98,
  "delivery_charge": 0,
  "total": 22.98,
  "eta": "20-25 min",
  "order_id": "X8WNMQYSEHZBW"
}
```

## Assertions

- ✅ gates: placed order had a confirmed, current readback — readback_confirmed=True readback_revision=4 cart.revision=4
- ✅ placed — cart.placed=True
- ✅ items: exact set of dishes — cart=['Gulab Jamun (2 pcs)', 'Paneer Tikka']
- ✅ items: Paneer Tikka qty == 1 — got qty=1
- ✅ items: Paneer Tikka note contains 'medium' — got note='medium'
- ✅ items: Gulab Jamun (2 pcs) qty == 1 — got qty=1
- ✅ order_type — got 'pickup'
- ✅ customer_name — got 'Rohan'
- ✅ customer_phone — got '4165557890'
- ✅ additional_requests_recorded — got True
- ✅ readbacks: at least 1 successful — got 1
