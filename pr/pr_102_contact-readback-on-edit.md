# PR 102 — An edit to the name or phone re-speaks the read-back from code

## Branch
`pr_102_contact-readback-on-edit`

## What This PR Does
PR 101 moved the contact read-back into code, but only on the path where the LLM
calls `get_contact_readback`. After a **correction** it was still the LLM's job
to call that tool again — and the whole point of PR 101 was that the money path
should not depend on the LLM remembering to do something.

It doesn't merely degrade; it confirms wrong. With the number corrected and the
LLM asking "is that right now?" without re-reading:

```
attempt 1: CONTACT READBACK INCOMPLETE — the customer has not heard their details
attempt 2: CONTACT READBACK INCOMPLETE — the customer has not heard their details
attempt 3: Name and phone confirmed.        ← give-up valve
RESULT confirmed=True | code utterances=1   ← the new number was never spoken
```

PR 101's give-up valve exists so a verifier gap can't trap a call, and here it
did exactly what it was built to do — but the result is `contact_confirmed=True`
for a phone number the customer never heard. On this path the valve was load
bearing rather than a backstop.

So a saved change to the name or phone, once the read-back step has been reached,
now re-speaks from code immediately. The LLM cannot skip it, because it is no
longer the LLM's call. After the change the first `confirm_contact` passes on
merit, with the corrected digits actually spoken and no `contact_verify_forced`
event.

This also fixes the stale guide text left behind by PR 101: `set_customer_contact`
told the model to "read the name and number back" one tool call before
`get_contact_readback` told it not to.

## Files Modified

### `restaurant/agent/gates.py`
New `OrderSessionState.contact_readback_ever_spoken`. A session milestone, and
deliberately **not** cleared by `invalidate_contact_readback` — it answers "have
we reached the read-back step yet?", which is what makes a later change an *edit*
rather than ordinary collection.

### `restaurant/agent/core.py`
- New `_contact_edit_needs_respeak()` — true when a just-saved change lands on
  details the customer has already had read back, and the contact is not
  confirmed. False during first-time collection, so the auto-speak never doubles
  up with the `get_contact_readback` call the flow makes next.
- `set_customer_contact` tracks whether it actually saved anything
  (`saved_change`) and, when the above holds, clears the capture window and
  re-speaks via the existing `_speak_contact_readback()`. Its GUIDE is then
  replaced with one telling the LLM the customer has already heard the corrected
  details and to only ask whether they're right.
- `_speak_contact_readback()` sets the milestone flag.
- **Guide text fixes:** the phone-saved guide no longer says "read the name and
  number back"; the name-saved guide no longer says "confirm the name briefly",
  which nudged the same way. Both now point at the tool that does the reading.

### `restaurant/agent/prompt.py`, `restaurant/agent/facts.py`
The correction instruction in the tool contract and in the
`CONTACT READBACK ALREADY SPOKEN` block now says: call `set_customer_contact`
with the fix **and nothing else** — it re-speaks the corrected details itself, so
do not call `get_contact_readback` again and do not say the name or number in
your own line.

### `tests/test_agent_tools.py`
- `test_contact_correction_respeaks_without_a_second_getter_call` — replaces
  PR 101's `..._respeaks_the_new_details`, which asserted the old contract (two
  utterances *including* an explicit getter call).
- `test_contact_edit_confirms_without_the_give_up_valve` — the hole above: edit,
  LLM never re-reads, first `confirm_contact` succeeds with the refusal counter
  at zero and **no** `contact_verify_forced` event.
- `test_contact_collection_does_not_respeak_before_the_first_readback` — pins the
  no-double-speak boundary.
- `test_contact_guides_do_not_ask_the_llm_to_read_details_back` — pins the guide
  texts against the `get_contact_readback` contract so they can't drift apart
  again.
- Removed a duplicate module-level `_EventRecorder` **introduced by PR 101**: the
  file already had one further down, which shadowed it, so PR 101's new tests
  were silently running against the older stub. Kept the original and gave it the
  `append_sierra` method the code-spoken path needs.

## Files Deleted
None.

## What's NOT in This PR
- **`get_contact_readback` still speaks every time it is called.** It is now
  redundant right after an edit, and the prompt says not to call it there, but it
  is deliberately not made idempotent: a caller asking "sorry, say that again?"
  must get a repeat. Hearing the details twice is never wrong; not hearing them
  when asked is.
- **Partial phone corrections.** A fragment ("the last two digits are 11") is
  read by `accumulate_phone` as the start of a *new* number, so the saved number
  is unchanged and the guide asks for "the REMAINING digits". Verified identical
  on `c66751f` (pre-PR-101) — long-standing, not a regression; the live call
  worked only because the LLM sent all ten digits itself. Deciding what a
  fragment should mean when a complete number is already stored (patch / restart
  / refuse and ask for the whole number) is its own PR.
- No change to the verifier, the give-up valve, or any gate. The valve stays as
  the backstop it was meant to be — this removes the path that was leaning on it.
- The `stt_noise` false positives and `parse_customer_name` truncating three-word
  names — both still open from PR 101.

## How to Test
```
PYTHONPATH=. uv run --with pytest pytest tests
```
649 pass. `tests/test_hosted_checkout.py::test_place_pay_now_disabled_no_url` and
`::test_place_pay_now_hco_failure_still_places` fail on `main` today too —
pre-existing, unrelated.

Manual call-flow check:
1. Reach the contact step, give a name and phone, let the read-back play.
2. Correct the last two digits (say the **whole** number).
3. The corrected details must be re-spoken **immediately**, in English digits,
   without Sierra calling `get_contact_readback` — and she must not repeat the
   name or number in her own line, only ask if it's right now.
4. One "ਹਾਂ ਜੀ" must confirm. Check the log: **no** `contact_verify_forced`
   event. If one appears, the re-speak didn't happen and the valve carried it.
5. Correct the **name** instead — same behaviour.
6. Correct something *after* already confirming — the gate re-arms, re-speaks,
   and re-confirms.

## Post-Merge: VPS Pull Command
`cd /opt/livekit-sarvam && git pull origin main && uv sync`
