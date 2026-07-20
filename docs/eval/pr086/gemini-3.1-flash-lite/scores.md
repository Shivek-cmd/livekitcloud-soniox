# Judge scores — gemini-3.1-flash-lite

- judge: gpt-4.1
- harness pass rate: 9/10
- mean LLM latency: 1.211s

## Dimension means (1–5)

- acknowledgement_variety: 4.6
- sentence_length_variety: 4.9
- code_mix_appropriateness: 4.8
- zero_meta_speech: 4.8
- confusion_handling_grace: 4.9
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
- scores: {"acknowledgement_variety": 4, "sentence_length_variety": 5, "code_mix_appropriateness": 5, "zero_meta_speech": 4, "confusion_handling_grace": 5}
- checkout_efficiency: 5
- flags: {"meta_speech": 1}
  - let me just read everything back to you one more time to make sure it's all correct — narrates process, mild meta-speech

### delivery_split_phone — harness FAIL
- scores: {"acknowledgement_variety": 4, "sentence_length_variety": 5, "code_mix_appropriateness": 5, "zero_meta_speech": 5, "confusion_handling_grace": 5}
- checkout_efficiency: 5
- flags: none
  - Sure thing — I've got one Dal Makhani and two Butter Naan down for you. Anything else I can get you with that? — varied acknowledgement, not repeated
  - You got it, I've made that Dal Makhani spicy for you. Anything else I can add to your order? — sentence length and structure varies
  - Got it. Would you like to pick this up, or should we deliver it for you? — natural code-mix, English for delivery/pickup
  - Thanks, Navdeep. I have the first six digits of your phone number—could you please finish that for me? — confusion handled gracefully, no blame
  - ਤੁਹਾਡਾ ਆਰਡਰ ਮਿਲ ਗਿਆ ਜੀ! 30-40 ਮਿੰਟ ਵਿੱਚ ਤਿਆਰ ਹੋ ਜਾਵੇਗਾ। ਬਹੁਤ ਬਹੁਤ ਧੰਨਵਾਦ ਜੀ! — correct closing in Punjabi

### english_pickup — harness PASS
- scores: {"acknowledgement_variety": 5, "sentence_length_variety": 5, "code_mix_appropriateness": 5, "zero_meta_speech": 5, "confusion_handling_grace": 5}
- checkout_efficiency: 5
- flags: none

### hindi_order — harness PASS
- scores: {"acknowledgement_variety": 5, "sentence_length_variety": 5, "code_mix_appropriateness": 5, "zero_meta_speech": 5, "confusion_handling_grace": 5}
- checkout_efficiency: 5
- flags: none

### no_spice_mentioned — harness PASS
- scores: {"acknowledgement_variety": 5, "sentence_length_variety": 5, "code_mix_appropriateness": 5, "zero_meta_speech": 5, "confusion_handling_grace": 5}
- checkout_efficiency: 5
- flags: none

### price_ask_phone — harness PASS
- scores: {"acknowledgement_variety": 5, "sentence_length_variety": 5, "code_mix_appropriateness": 3, "zero_meta_speech": 5, "confusion_handling_grace": 5}
- checkout_efficiency: None
- flags: none
  - All agent turns in English despite user using English; code-mix appropriateness is only average.

### punjabi_order — harness PASS
- scores: {"acknowledgement_variety": 3, "sentence_length_variety": 4, "code_mix_appropriateness": 5, "zero_meta_speech": 5, "confusion_handling_grace": 4}
- checkout_efficiency: 5
- flags: none
  - ਤੁਹਾਡਾ ਆਰਡਰ ਮਿਲ ਗਿਆ ਜੀ! 20-25 ਮਿੰਟ ਵਿੱਚ ਤਿਆਰ ਹੋ ਜਾਵੇਗਾ। ਬਹੁਤ ਬਹੁਤ ਧੰਨਵਾਦ ਜੀ! — repeated verbatim at end
  - ਠੀਕ ਹੈ ਜੀ। ਇਹ ਆਰਡਰ ਤੁਸੀਂ Pickup ਲਈ ਲੈਣਾ ਹੈ ਜਾਂ ਅਸੀਂ Delivery ਕਰਵਾ ਦੇਈਏ? — repeated twice
  - mixes English dish and order type naturally: ਦੋ Butter Chicken, Pickup
  - handles allergy/spice gracefully: ਠੀਕ ਹੈ ਜੀ, ਮੈਂ ਨੋਟ ਕਰ ਲਿਆ ਹੈ।

### quantity_correction — harness PASS
- scores: {"acknowledgement_variety": 5, "sentence_length_variety": 5, "code_mix_appropriateness": 5, "zero_meta_speech": 5, "confusion_handling_grace": 5}
- checkout_efficiency: 5
- flags: none

### sloppy_readback — harness PASS
- scores: {"acknowledgement_variety": 5, "sentence_length_variety": 5, "code_mix_appropriateness": 5, "zero_meta_speech": 4, "confusion_handling_grace": 5}
- checkout_efficiency: 5
- flags: {"meta_speech": 1}
  - My apologies, Harpreet, let me just double-check that for you. — mild meta-speech (explaining process)
