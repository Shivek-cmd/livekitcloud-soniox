# PR 009 — Prompt rewrite: Sierra, humanized, mixed language

## Summary
Full rewrite of the system prompt and opening greeting.
Agent name changed to Sierra. Language changed from strict Punjabi to natural
Punjabi-English code-switching as spoken in Canadian Punjabi restaurants.
Prompt is descriptive rather than restrictive to avoid hallucination.

## Key changes
- Agent is now "Sierra" at "Bizbull Restaurant"
- Language: natural Punjabi+English mix, not 100% Gurmukhi
- Spice level asked for starters and mains only (explicit list of exceptions)
- Special instructions asked per item, after spice level
- Phone numbers read digit by digit in English
- Order flow written as human conversation guidance, not rigid numbered rules
- Greeting updated: "Welcome to Bizbull Restaurant! I'm Sierra — how can I help you today?"

## Files Changed
- `agent.py` — SYSTEM_PROMPT and session.say() greeting
