# PR 015 — Prompt: multilingual, transfer-to-human, tighter conversation rules

## Branch
`pr_015_prompt-flow-update`

## What This PR Does
Incorporates a reference prompt flow into Sierra's existing personality. Adds Hindi support,
auto language detection, transfer-to-human tool with two-strike rule, allergy question,
"Anything else?" step, and a NEVER DO guardrail list. Tightens conversation rules to
one-thing-at-a-time. Sierra's Punjabi voice and Bizbull Restaurant identity are unchanged.

## Files Modified

### `agent.py`
**SYSTEM_PROMPT:**
- Added LANGUAGE section: detect English/Hindi/Punjabi from caller, switch with them, no announcement
- Updated HOW YOU TALK: one sentence per turn, one question at a time, fillers list, "sorry could you say that again?" rule
- Updated greeting: shorter, mentions all three language options
- Added allergy question after special instructions per item
- Added "Anything else?" after each item before moving to pickup/delivery
- Added TRANSFER TO HUMAN section: when to transfer (caller requests human, two-strike on unclear, out-of-scope request)
- Final confirmation: only once at the very end — never repeat or summarize mid-order
- Added NEVER DO list

**`transfer_to_human` tool:**
- New `@function_tool` method on `RestaurantAgent`
- Logs the reason, returns instruction to agent on what to say
- Actual SIP call transfer is deferred (Phase 5)

## What's NOT in This PR
- Actual SIP call transfer (LiveKit SIP transfer API) — tool is a placeholder that logs and instructs the agent to say a hold message
- Hindi menu text (menu stays in English as it is now)

## How to Test
```bash
# After deploy, test these scenarios via phone or web:
# 1. Call in Hindi — agent should reply in Hindi
# 2. Call in English — agent should reply in English
# 3. Say something unclear twice — agent should transfer
# 4. Say "I want to talk to a person" — agent should transfer immediately
# 5. Order an item — agent should ask spice, then allergy, then "anything else?"
# 6. Order multiple items — agent should NOT summarize mid-order, only at end
```

## Post-Merge: VPS Pull Command
```bash
cd /opt/livekit-sarvam && git pull origin main
systemctl restart restaurant-agent
```
