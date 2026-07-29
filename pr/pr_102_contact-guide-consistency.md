# PR 102 — set_customer_contact stops telling the LLM to read the number back

## Branch
`pr_102_contact-guide-consistency`

## What This PR Does
PR 101 moved the contact read-back into code: `get_contact_readback` now speaks
the name-spelling and the phone digits itself, and its facts block tells the LLM
`Do NOT repeat the name or the number`. One instruction was left behind. After a
phone saves, `set_customer_contact` still returns:

> "the number is already saved — do NOT ask the customer to repeat or re-say it.
> Call get_contact_readback next and **read the name and number back** for
> confirmation."

So the model is told to read the number back, and then — one tool call later —
told not to. Conflicting instructions, with the stale one arriving **first**. If
it follows that one it repeats the digits in its own line right after the code
line spoke them, in whatever script the conversation is in, which is exactly the
Gurmukhi-digit failure PR 101 set out to make impossible.

Nothing has been observed failing because of it: the TTS phone enforcement still
rewrites recognised digit words, and the facts block does say not to repeat. This
removes the contradiction rather than fixing a live symptom.

## Files Modified

### `restaurant/agent/core.py`
- **Phone-saved guide** now points at the tool without asking for speech: the
  number is saved, call `get_contact_readback`, it speaks both details to the
  customer, do not say the name or the number yourself.
- **Name-saved guide** was "confirm the name briefly in the customer's
  language", which nudges the same way. Reworded to acknowledge the name without
  implying a read-back — the read-back is the tool's job now. (Lower risk than
  the phone guide either way: names are stored Roman, so there was never a script
  problem here.)

### `tests/test_agent_tools.py`
`test_contact_guides_do_not_ask_the_llm_to_read_details_back` — after a name save
and after a phone save, the returned guide must not instruct the model to read
the details back, and the phone guide must name `get_contact_readback`. Pins the
contract so the two texts can't drift apart again.

## Files Deleted
None.

## What's NOT in This PR
- **Partial phone corrections.** A fragment ("the last two digits are 11") is
  read by `accumulate_phone` as the start of a *new* number, so the saved number
  is left unchanged and the guide asks for "the REMAINING digits". Verified
  identical on `c66751f` (pre-PR-101) — long-standing, not a regression, and the
  live call worked only because the LLM sent all ten digits itself. Fixing it
  means deciding what a fragment should mean when a complete number is already
  stored (patch / restart / refuse and ask for the whole number), which is its
  own decision and its own PR.
- No change to `get_contact_readback`, `confirm_contact`, the verifier, or any
  gate. Guide text only.
- The `stt_noise` false positives and `parse_customer_name` truncating three-word
  names — both still open from PR 101.

## How to Test
```
PYTHONPATH=. uv run --with pytest pytest tests
```
647 pass. `tests/test_hosted_checkout.py::test_place_pay_now_disabled_no_url` and
`::test_place_pay_now_hco_failure_still_places` fail on `main` today too —
pre-existing, unrelated.

Manual call-flow check:
1. Reach the contact step and give a name and phone.
2. `get_contact_readback` speaks the spelled name and English digits.
3. Sierra's own next line must **only ask whether they are right** — she must not
   say the name or the number a second time.
4. Correct a digit (giving the whole number) and confirm the same holds on the
   re-read.

## Post-Merge: VPS Pull Command
`cd /opt/livekit-sarvam && git pull origin main && uv sync`
