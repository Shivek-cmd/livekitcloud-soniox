# PR 007 — TTS speech engine fix (Soniox script + quantities)

## Root cause (bugs found)

Soniox TTS works in playground because text is **Gurmukhi**. Our system sends **Roman Latin**
to the same `tts-rt-v1` / `Maya` / `language=pa` pipeline → mispronunciation.

| Bug | Where | Effect |
|-----|--------|--------|
| **B1** | `speech_policy.py` — `breads_rice` → English `voice_line` | Aloo Paratha spoken as Roman, not ਆਲੂ ਪਰਾਠਾ |
| **B2** | `agent.py` A4 — `"Got it — 1x [voice_line]"` | LLM says "2x Aloo Paratha" |
| **B3** | `orders.py` — `"2x {voice_line}"` in cart/summary | Tool output teaches LLM the x format |
| **B4** | Prompt — `speak_as` "STT only" | LLM ignores Gurmukhi, uses Roman voice_line |
| **B5** | LLM output — `"Aloo Paratha"` in quotes inside Punjabi | TTS code-switches badly mid-sentence |

**Not a Soniox model bug** — same API, wrong text input.

## Fix

1. **speech_policy** — Default `voice_line = speak_as` (Gurmukhi). English only for explicit overrides (Fish Pakora, Chole Bhature Combo, tandoor items staff say in English).
2. **Prompt** — New `TTS / SONIOX` section; ban `1x/2x/3x`; word quantities (do, ik, two).
3. **Tool output** — Cart/summary: `qty 2, say: ਆਲੂ ਪਰਾਠਾ` not `2x`.
4. **Rebuild** `clover_voice_labels.json`.

## Test plan

- [ ] Aloo Paratha — TTS says ਆਲੂ ਪਰਾਠਾ naturally (compare to playground)
- [ ] Fish Pakora — still English "Fish Pakora"
- [ ] Confirm order — "do" / "ਦੋ", never "2x"
- [ ] Full call flow still works
