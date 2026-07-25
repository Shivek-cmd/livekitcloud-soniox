# Dialogue harness summary

- model: gemini-3.5-flash
- scenarios: 10, passed: 9

- ✅ ambiguous_fish
- ✅ change_after_readback
- ❌ delivery_split_phone — failed: []['LLM call failed after retries: completion had no message (finish_reason=content_filter: PROHIBITED_CONTENT)']
- ✅ english_pickup
- ✅ hindi_order
- ✅ no_spice_mentioned
- ✅ price_ask_phone
- ✅ punjabi_order
- ✅ quantity_correction
- ✅ sloppy_readback

- llm latency (per call): mean 6.586s, p95 11.019s, max 38.929s over 178 calls
