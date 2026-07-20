# Judge scores — gpt-4.1-mini

- judge: gpt-4.1
- harness pass rate: 10/10
- mean LLM latency: 1.264s

## Dimension means (1–5)

- acknowledgement_variety: 4.1
- sentence_length_variety: 4.8
- code_mix_appropriateness: 5.0
- zero_meta_speech: 4.6
- confusion_handling_grace: 4.9
- checkout_efficiency: 5.0

## Flag totals

- stray_language: 0
- roman_indic: 0
- ungrounded_dish: 0
- fact_contradiction: 0
- meta_speech: 4
- spoken_parenthetical: 12

## Per scenario

### ambiguous_fish — harness PASS
- scores: {"acknowledgement_variety": 5, "sentence_length_variety": 5, "code_mix_appropriateness": 5, "zero_meta_speech": 5, "confusion_handling_grace": 5}
- checkout_efficiency: None
- flags: none

### change_after_readback — harness PASS
- scores: {"acknowledgement_variety": 2, "sentence_length_variety": 5, "code_mix_appropriateness": 5, "zero_meta_speech": 5, "confusion_handling_grace": 5}
- checkout_efficiency: 5
- flags: none
  - Sure thing, I've got one Butter Chicken with medium spice for you. Anything else you'd like to add? — varied acknowledgement, not repeated
  - Alright, before we finish, do you have any spice preferences, allergies, or special instructions for the kitchen? — longer sentence
  - Great, I've noted no allergies or special requests. Would you like to pick up your order or have it delivered? — medium-length, natural
  - Pickup it is. Can I have your name for the order, please? — short and direct
  - Got it, your phone number is four one six five five five two two three three. Let me read back your order: one Butter Chicken with medium spice, for pickup under the name Jasleen. Is everything correct? — mixes short confirm with full readback
  - No problem, I've added one Garlic Naan to your order. Anything else you'd like? — natural, warm, and varied
  - Alright Jasleen, your order now has one Butter Chicken with medium spice and one Garlic Naan, for pickup. Is everything correct? — full, clear, and warm readback
  - ਤੁਹਾਡਾ ਆਰਡਰ ਮਿਲ ਗਿਆ ਜੀ! 20-25 ਮਿੰਟ ਵਿੱਚ ਤਿਆਰ ਹੋ ਜਾਵੇਗਾ। ਬਹੁਤ ਬਹੁਤ ਧੰਨਵਾਦ ਜੀ! — appropriate code-switch to Punjabi at close

### delivery_split_phone — harness PASS
- scores: {"acknowledgement_variety": 3, "sentence_length_variety": 4, "code_mix_appropriateness": 5, "zero_meta_speech": 4, "confusion_handling_grace": 5}
- checkout_efficiency: 5
- flags: {"meta_speech": 1}
  - "Anything else you'd like to add?" — repeated twice, mechanical
  - "Got it, your Dal Makhani will be spicy. Anything else you'd like to add?" — similar structure, little variety
  - "Alright, no allergies or special instructions noted." — slightly meta, but not tool narration
  - "Thanks for that. Now, is this order for pickup or delivery?" — smooth confusion handling
  - "Thanks, Navdeep, and your phone number six four seven five five five one two one two is all set." — confirms phone as required
  - "Let me read back your order: one spicy Dal Makhani and two Butter Naan for delivery. Is everything correct?" — meta-speech: 'Let me read back your order'

### english_pickup — harness PASS
- scores: {"acknowledgement_variety": 4, "sentence_length_variety": 5, "code_mix_appropriateness": 5, "zero_meta_speech": 5, "confusion_handling_grace": 5}
- checkout_efficiency: 5
- flags: {"spoken_parenthetical": 2}
  - one ਗਾਰਲਿਕ ਨਾਨ (Garlic Naan) for you — spoken parenthetical

### hindi_order — harness PASS
- scores: {"acknowledgement_variety": 5, "sentence_length_variety": 5, "code_mix_appropriateness": 5, "zero_meta_speech": 5, "confusion_handling_grace": 5}
- checkout_efficiency: 5
- flags: {"spoken_parenthetical": 2}

### no_spice_mentioned — harness PASS
- scores: {"acknowledgement_variety": 4, "sentence_length_variety": 5, "code_mix_appropriateness": 5, "zero_meta_speech": 4, "confusion_handling_grace": 5}
- checkout_efficiency: 5
- flags: {"meta_speech": 1, "spoken_parenthetical": 3}
  - Now let me read back your order to make sure everything is correct. — meta-speech (narrates readback step)
  - one ਗਾਰਲਿਕ ਨਾਨ (Garlic Naan) — spoken parenthetical inside English sentence

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
- scores: {"acknowledgement_variety": 3, "sentence_length_variety": 4, "code_mix_appropriateness": 5, "zero_meta_speech": 3, "confusion_handling_grace": 4}
- checkout_efficiency: 5
- flags: {"meta_speech": 2, "spoken_parenthetical": 5}
  - "Anything else you'd like with that?" — repeated structure, limited variety
  - "Let me read back your order to make sure everything is correct." — meta-speech, narrates process
  - "Let me read back your order again to confirm." — meta-speech, narrates process
  - "one ਗਾਰਲਿਕ ਨਾਨ (Garlic Naan)" — spoken parenthetical inside English sentence
  - "one ਗਾਰਲਿਕ ਨਾਨ (Garlic Naan)" — spoken parenthetical inside English sentence
