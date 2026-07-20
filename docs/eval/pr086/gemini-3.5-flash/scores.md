# Judge scores — gemini-3.5-flash

- judge: gpt-4.1
- harness pass rate: 9/10
- mean LLM latency: 1.3s

## Dimension means (1–5)

- acknowledgement_variety: 4.9
- sentence_length_variety: 5.0
- code_mix_appropriateness: 5.0
- zero_meta_speech: 4.8
- confusion_handling_grace: 5.0
- checkout_efficiency: 5.0

## Flag totals

- stray_language: 0
- roman_indic: 0
- ungrounded_dish: 0
- fact_contradiction: 0
- meta_speech: 2
- spoken_parenthetical: 0

## Per scenario

### ambiguous_fish — harness PASS
- scores: {"acknowledgement_variety": 5, "sentence_length_variety": 5, "code_mix_appropriateness": 5, "zero_meta_speech": 5, "confusion_handling_grace": 5}
- checkout_efficiency: None
- flags: none

### change_after_readback — harness PASS
- scores: {"acknowledgement_variety": 5, "sentence_length_variety": 5, "code_mix_appropriateness": 5, "zero_meta_speech": 4, "confusion_handling_grace": 5}
- checkout_efficiency: 5
- flags: {"meta_speech": 1}
  - Since we made a change, let me just double-check: is there anything else you'd like to add, or are we good to go with this? — mild meta-speech about process

### delivery_split_phone — harness FAIL
- scores: {"acknowledgement_variety": 4, "sentence_length_variety": 5, "code_mix_appropriateness": 5, "zero_meta_speech": 5, "confusion_handling_grace": 5}
- checkout_efficiency: 5
- flags: none
  - You got it — I've added one Dal Makhani and two Butter Naan...
  - You got it, I've made the Dal Makhani spicy for you.
  - Perfect. Will this order be for pickup or delivery today?
  - Sure thing, delivery it is. Could you please provide your delivery address?
  - Got it, I've saved that address. Can I get your name for the order, please?
  - Thanks, Navdeep. And what is the best phone number to reach you at?
  - Alright, Navdeep, I've got your phone number down as six, four, seven, five, five, five, one, two, one, two.
  - Let me read your order back to make sure everything is correct: ...
  - Yes, we have it set for delivery. Just to confirm everything one more time: ...
  - ਤੁਹਾਡਾ ਆਰਡਰ ਮਿਲ ਗਿਆ ਜੀ! 30-40 ਮਿੰਟ ਵਿੱਚ ਤਿਆਰ ਹੋ ਜਾਵੇਗਾ। ਬਹੁਤ ਬਹੁਤ ਧੰਨਵਾਦ ਜੀ!

### english_pickup — harness PASS
- scores: {"acknowledgement_variety": 5, "sentence_length_variety": 5, "code_mix_appropriateness": 5, "zero_meta_speech": 5, "confusion_handling_grace": 5}
- checkout_efficiency: 5
- flags: none
  - You got it! I've added two Butter Chicken and one ਗਾਰਲਿਕ ਨਾਨ
  - Perfect. And will this order be for pickup, or would you like us to deliver it to you?
  - Thanks for letting me know! And is this order going to be for pickup, or would you like delivery?
  - Alright, pickup it is. Can I get your name for the order, please?
  - Great, Harpreet. And what is a good phone number to reach you at?
  - Thank you, Harpreet. I've got your phone number down as six, four, seven, five, five, five, one, two, one, two.
  - Let me read your order back to make sure we have everything right: we have two Butter Chicken and one ਗਾਰਲਿਕ ਨਾਨ, and this is for pickup under the name Harpreet. Does that all sound correct to you?
  - ਤੁਹਾਡਾ ਆਰਡਰ ਮਿਲ ਗਿਆ ਜੀ! 20-25 ਮਿੰਟ ਵਿੱਚ ਤਿਆਰ ਹੋ ਜਾਵੇਗਾ। ਬਹੁਤ ਬਹੁਤ ਧੰਨਵਾਦ ਜੀ!

### hindi_order — harness PASS
- scores: {"acknowledgement_variety": 5, "sentence_length_variety": 5, "code_mix_appropriateness": 5, "zero_meta_speech": 5, "confusion_handling_grace": 5}
- checkout_efficiency: 5
- flags: none

### no_spice_mentioned — harness PASS
- scores: {"acknowledgement_variety": 5, "sentence_length_variety": 5, "code_mix_appropriateness": 5, "zero_meta_speech": 5, "confusion_handling_grace": 5}
- checkout_efficiency: 5
- flags: none
  - You got it — I've added one Butter Chicken and one ਗਾਰਲਿਕ ਨਾਨ
  - Perfect. And will this order be for pickup, or would you like us to deliver it to you?
  - No problem. Will you be coming by to pick this up, or would you like us to deliver it to your place?
  - Awesome, pickup it is. May I please have your name for the order?
  - Thanks, Karan. And what is a good phone number to reach you at?
  - Got that down as four, one, six, five, five, five, one, two, three, four.
  - Alright, let's make sure I've got everything right: I have one Butter Chicken and one ਗਾਰਲਿਕ ਨਾਨ for pickup under the name Karan. Is all of that correct?
  - ਤੁਹਾਡਾ ਆਰਡਰ ਮਿਲ ਗਿਆ ਜੀ! 20-25 ਮਿੰਟ ਵਿੱਚ ਤਿਆਰ ਹੋ ਜਾਵੇਗਾ। ਬਹੁਤ ਬਹੁਤ ਧੰਨਵਾਦ ਜੀ!

### price_ask_phone — harness PASS
- scores: {"acknowledgement_variety": 5, "sentence_length_variety": 5, "code_mix_appropriateness": 5, "zero_meta_speech": 5, "confusion_handling_grace": 5}
- checkout_efficiency: None
- flags: none

### punjabi_order — harness PASS
- scores: {"acknowledgement_variety": 5, "sentence_length_variety": 5, "code_mix_appropriateness": 5, "zero_meta_speech": 5, "confusion_handling_grace": 5}
- checkout_efficiency: 5
- flags: none

### quantity_correction — harness PASS
- scores: {"acknowledgement_variety": 5, "sentence_length_variety": 5, "code_mix_appropriateness": 5, "zero_meta_speech": 5, "confusion_handling_grace": 5}
- checkout_efficiency: 5
- flags: none

### sloppy_readback — harness PASS
- scores: {"acknowledgement_variety": 5, "sentence_length_variety": 5, "code_mix_appropriateness": 5, "zero_meta_speech": 4, "confusion_handling_grace": 5}
- checkout_efficiency: 5
- flags: {"meta_speech": 1}
  - My apologies, let me read that back one more time to be absolutely sure. — narrates the re-read process, mild meta-speech
