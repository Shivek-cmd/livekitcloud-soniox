# Dialogue harness summary

- model: gemini-3.5-flash
- scenarios: 10, passed: 9

- ✅ ambiguous_fish
- ✅ change_after_readback
- ❌ delivery_split_phone — failed: []['LLM call failed after retries: completion had no message']
- ✅ english_pickup
- ✅ hindi_order
- ✅ no_spice_mentioned
- ✅ price_ask_phone
- ✅ punjabi_order
- ✅ quantity_correction
- ✅ sloppy_readback

- llm latency (per call): mean 1.283s, p95 1.703s, max 7.815s over 159 calls
