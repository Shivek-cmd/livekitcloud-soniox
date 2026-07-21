# PR 088 — Customer names always spoken in English/Roman script

## Branch
`pr_088_customer-name-english`

## What This PR Does
Adds a HARD SPEECH RULE alongside the existing dish-name and phone-digit
rules: customer names must always be spoken in English/Roman letters, never
transliterated into Gurmukhi/Devanagari, regardless of the conversation's
language. Prompt-only by design — unlike phone digits and dish names,
there's no closed lookup table a generic name could be rewritten against at
the TTS layer, so this is enforced the same way the existing "never
transliterate dish names" rule is.

## Files Added
None.

## Files Modified
### `restaurant/agent/prompt.py`
Adds one line to both hard-speech-rule blocks (`_hard_speech_rules()` and
the `HOW YOU TALK` section): "Customer names: ALWAYS spoken in English/Roman
letters — NEVER transliterated into Gurmukhi/Devanagari, no matter what
language you're speaking in." Sits directly under the existing phone-digit
rule in each block.

## Files Deleted
None.

## What's NOT in This PR
- No code-level enforcement (no TTS-layer name transliteration filter) —
  there's no closed lookup table for arbitrary customer names the way there
  is for menu dish names, so this stays prompt-only, same as the dish-name
  rule it sits beside.
- No verifier/gate check for this rule — unlike `readback_verify.py`'s
  phone-digit and dish-name checks, name-script violations aren't checked
  post-speech in this PR.

## How to Test
```
PYTHONPATH=. uv run --with pytest pytest tests -q
```
Manual/live check: run a call in Punjabi/Hindi mode, have the agent read
back a customer name during readback/confirm, and confirm the name is
spoken in English/Roman letters rather than transliterated.

## Post-Merge: VPS Pull Command
`cd /opt/livekit-sarvam && git pull origin main && uv sync`
