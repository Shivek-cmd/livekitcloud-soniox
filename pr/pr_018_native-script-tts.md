# PR 018 — Fix romanised Indic text in prompt (Bulbul TTS quality)

## Branch
`pr_018_native-script-tts`

## What This PR Does
Fixes romanised (transliterated) Punjabi/Hindi text in the system prompt.
Per official Bulbul v3 docs: "Romanised Indic input significantly reduces output quality.
Always use native script for Indic words."

## Root Cause
When the LLM generates text like "Haan ji" or "Ek second — main aapko abhi connect karta hoon."
and sends it to Bulbul TTS, the TTS receives Roman characters for Indic words. This forces
the TTS to guess pronunciation instead of using its optimised Indic phoneme models —
resulting in robotic, degraded speech quality.

## Changes

### agent.py — SYSTEM_PROMPT

**HOW YOU TALK section — fillers rewritten in native script:**
- Was: `"Okay ji"`, `"Haan ji"` (Roman transliteration)
- Now: separate filler sets in English / Punjabi (Gurmukhi) / Hindi (Devanagari)
- Added SCRIPT RULE: explicit instruction to never use Roman transliteration for Indic words

**TRANSFER TO HUMAN — Hindi line fixed:**
- Was: `"Ek second — main aapko abhi connect karta hoon."` (Roman)
- Now: `"एक सेकंड — मैं आपको अभी connect करता हूँ।"` (Devanagari)

**NEVER DO — added script rule:**
- "Never write Punjabi or Hindi in Roman/English letters — always use Gurmukhi or Devanagari."

## Files Modified
- `agent.py` — SYSTEM_PROMPT only

## How to Test
```bash
cd /opt/livekit-sarvam && git pull origin main && systemctl restart restaurant-agent

# Call in Hindi and listen for the transfer line — should sound natural now
uv run python scripts/test_call.py +91XXXXXXXXXX
# Say: "mujhe kisi se baat karni hai" (should transfer in clean Devanagari TTS)
```

## Post-Merge: VPS Pull Command
```bash
cd /opt/livekit-sarvam && git pull origin main
systemctl restart restaurant-agent
```
