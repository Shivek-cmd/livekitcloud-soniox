# Latency Analysis — Production Restaurant Voice Agent

## Why Latency Matters More for This Use Case

This is a **restaurant ordering agent on a phone call**. Callers are:
- Hungry and impatient
- Often calling from noisy environments (street, car)
- Expecting a natural conversation, not a chatbot

On a phone call, **> 1.5s of silence = the caller thinks the line dropped**. They repeat themselves or hang up. This breaks the order flow and damages the business.

---

## Full Latency Breakdown (Per Response Turn)

### Phone Channel (Twilio SIP) — Most Critical

```
Step                                      Best Case    Worst Case
─────────────────────────────────────────────────────────────────
PSTN + Twilio network hop                   80ms         150ms
SIP → LiveKit SIP Service                   20ms          50ms
VAD: detecting end of utterance            200ms         500ms  ← TUNING RISK
STT: Saaras v3 WebSocket streaming         150ms         350ms
LLM: Sarvam-30B first token               500ms        1400ms  ← BIGGEST RISK
TTS: Bulbul v3 first audio chunk           150ms         350ms
LiveKit → SIP → Twilio → PSTN back        100ms         200ms
─────────────────────────────────────────────────────────────────
TOTAL (Time to First Audio, TTFA)         1.2s          3.0s
```

### Web Channel (Browser WebRTC)

```
Step                                      Best Case    Worst Case
─────────────────────────────────────────────────────────────────
WebRTC audio capture                        10ms          30ms
VAD: detecting end of utterance            200ms         400ms
STT: Saaras v3 WebSocket streaming         100ms         250ms
LLM: Sarvam-30B first token               500ms        1400ms
TTS: Bulbul v3 first audio chunk           100ms         300ms
WebRTC back to browser                      10ms          30ms
─────────────────────────────────────────────────────────────────
TOTAL (TTFA)                               0.9s          2.4s
```

---

## The 5 Critical Latency Risks

### Risk 1: LLM Response Time (HIGHEST IMPACT)

Sarvam-30B is a 30 billion parameter model. Cold inference = 500–1400ms to first token.

**Impact**: Every time a customer says anything, there's at minimum 0.5–1.4s of silence before the agent starts responding. For a multi-turn order ("I want 2 burgers... what sauces do you have?... ok add chilli sauce... for pickup... name is Harpreet") this stacks badly.

**Mitigations**:
- Stream LLM tokens directly into TTS — agent starts speaking as soon as first few words are generated, not after full response
- Use `sarvam-30b` not `sarvam-105b` — speed over capability for this use case
- Inject **filler phrases** while LLM is warming up: "ਹਾਂ ਜੀ..." (yes...) or "ਠੀਕ ਹੈ..." (okay...)
- Pre-compute responses for predictable questions (hours, location, specials)

### Risk 2: VAD — End-of-Utterance Detection

VAD decides when the user has finished speaking. Wrong settings cause two opposite problems:

| Problem | Cause | Effect |
|---|---|---|
| Cuts user off mid-sentence | VAD too aggressive | "I want a paneer—" → agent interrupts |
| Long silence before agent responds | VAD too conservative | 600–800ms added to every turn |

**Restaurant-specific problem**: Punjabi speakers often pause mid-order while thinking:
> "ਮੈਨੂੰ... ਇੱਕ ਪਨੀਰ ਬਰਗਰ... ਅਤੇ... ਇੱਕ ਮੈਂਗੋ ਲੱਸੀ ਚਾਹੀਦੀ ਹੈ"

A 300ms pause within this sentence should NOT trigger end-of-utterance.

**Mitigation**: Tune VAD end-of-speech threshold to ~600ms for restaurant context. Test extensively with real Punjabi speech patterns.

### Risk 3: Tool Call Stacking

A restaurant order requires multiple sequential tool calls:

```
Turn: "I want 2 paneer burgers for delivery"
  → tool: validate_item("paneer burger")     +300ms
  → tool: add_to_cart(item, qty=2)           +200ms
  → tool: set_order_type("delivery")         +100ms
  → LLM generates confirmation response      +500ms
Total added: 1.1s on top of base latency
```

For a full order (3 items + delivery address + payment method):
- Could be 8–12 tool calls
- Adds 2–4 seconds of dead processing time
- User experiences silence, repeats themselves, order gets duplicated

**Mitigation**:
- Batch tool calls where possible — single `process_order_update(items, type, address)` instead of one call per item
- Execute non-dependent tool calls in parallel
- Keep tool call responses tiny (don't return full menu JSON, just success/failure)

### Risk 4: Phone Audio Quality (8kHz Degradation)

Twilio SIP delivers audio in **G.711 PCMU at 8kHz**. Sarvam STT expects **16kHz**.

LiveKit upsamples 8kHz → 16kHz but this doesn't recover lost frequency information. Punjabi phonemes in the 4–8kHz range are degraded. Combined with:
- Restaurant background noise (kitchen sounds, other callers)
- Mobile phone compression artifacts
- Thick regional Punjabi accents

STT error rate on phone calls will be **notably higher than web calls**.

**Mitigations**:
- Enable **Krisp noise cancellation** on the LiveKit SIP service (built-in integration)
- Use `code-mixed` STT mode — more tolerant of imperfect audio
- Add confirmation step in agent: "ਕੀ ਮੈਂ ਸਹੀ ਸਮਝਿਆ — 2 ਪਨੀਰ ਬਰਗਰ?" before placing order
- If STT confidence is low, ask user to repeat: "ਮਾਫ਼ ਕਰਨਾ, ਕੀ ਤੁਸੀਂ ਦੁਬਾਰਾ ਕਹਿ ਸਕਦੇ ਹੋ?"

### Risk 5: Server Geography

Sarvam API is hosted in India. Every STT and TTS call travels:

```
LiveKit Agent → internet → Sarvam API → internet → back

If server is in India (Mumbai):   ~20ms round trip  ✓
If server is in Singapore:        ~60ms round trip  OK
If server is in US/Europe:        ~180ms round trip  ✗ (adds 360ms+ per turn)
```

**Decision**: Host the LiveKit VPS in **India (Mumbai region)** — AWS `ap-south-1`, GCP `asia-south1`, or Hetzner Falkenstein (Europe is still better than US for Sarvam).

---

## Streaming Pipeline — The Most Important Optimization

Without streaming, latency is **additive**:
```
Wait for STT to finish → Wait for LLM to finish → Wait for TTS to finish → Play audio
= 3 sequential waits
```

With streaming, components **overlap**:
```
STT partial results → LLM starts processing early tokens
LLM first tokens → TTS starts generating audio for first sentence
TTS first audio chunk → Playing on phone while LLM still generating
= parallel pipeline
```

This alone reduces **perceived** latency by 40–60%.

LiveKit Agents handles this automatically when all three components support streaming:
- ✓ Sarvam STT: WebSocket streaming (already in plan)
- ✓ Sarvam LLM: streaming tokens (OpenAI-compatible `stream=True`)
- ✓ Sarvam TTS: HTTP streaming (already in plan)

**All three must be streaming — verify each one is configured correctly in agent code.**

---

## Filler Phrase Strategy

When LLM processing takes > 600ms, the agent should say a short filler phrase to signal it's "thinking":

```python
FILLERS_PUNJABI = [
    "ਹਾਂ ਜੀ...",           # "Yes..."
    "ਠੀਕ ਹੈ...",            # "Okay..."
    "ਇੱਕ ਮਿੰਟ...",          # "One moment..."
    "ਦੇਖਦੇ ਹਾਂ...",         # "Let me check..."
]
```

Inject filler TTS immediately after STT completes, before LLM response is ready. This makes the agent feel responsive even when the LLM is slow.

---

## Latency Targets by Scenario

| Scenario | Target TTFA | Acceptable Max |
|---|---|---|
| Simple greeting | < 0.8s | 1.2s |
| Item lookup ("do you have X?") | < 1.2s | 1.8s |
| Adding item to order | < 1.4s | 2.0s |
| Order confirmation | < 1.2s | 1.8s |
| Reservation booking | < 1.5s | 2.2s |
| "What are today's specials?" (cached) | < 0.3s | 0.5s |

---

## Production Monitoring Checklist

Track these metrics from day one:

- [ ] TTFA per call (web vs phone)
- [ ] STT word error rate (WER) — web vs phone
- [ ] LLM time to first token (p50, p95, p99)
- [ ] Tool call latency per tool
- [ ] Call abandonment rate (proxy for "agent too slow")
- [ ] Order error rate (proxy for "STT or LLM got it wrong")
- [ ] Average turns per order completion (lower = more efficient)
