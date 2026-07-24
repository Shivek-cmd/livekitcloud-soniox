# PR 092 — Confirm name/phone at collection + Roman-script name capture

## Branch
`pr_092_contact-confirm-and-roman-names`

## What This PR Does
Rolls back the part of PR 087 (`675fd46`) that moved contact verification into
the final order read-back, and replaces it with a dedicated, code-gated
confirmation step right after the details are collected.

Under PR 087 the phone number and delivery address were read back inside
`get_order_readback`, and a strict spoken-digit check in `readback_verify.py`
refused the confirmation if the digits weren't matched exactly — which drove
false re-read loops at the most expensive point in the call, since a
correction there forced a re-read of the whole order. This PR restores the
pre-087 read-back (cart only) and removes that digit check, then adds
`get_contact_readback`/`confirm_contact`: the agent reads the name back in
English spelled letter by letter and the phone as separate English word
digits, the customer corrects or accepts, and only then does the flow move on.
A correction there costs one contact re-read, not a whole-order re-read.

The step is a hard gate, not a prompt instruction — `readback_blockers`
requires `state.contact_confirmed`, and any later name/phone change clears it.
`confirm_contact` is not a bare flag flip either: it verifies the agent
actually *spoke* the name and every phone digit, reusing the PR 078
capture/verify shape.

Two things carried over from PR 087 deliberately: auto-place on
`confirm_readback` is kept, and PR 091's contact collection order
(`type → address → name → phone`) and fabrication backstop are untouched.

The last commit also enforces the capture side of PR 088: names are now saved
in Roman letters, because the ticket, the spelled-out read-back and the
spoken-name check all silently degrade on a Gurmukhi/Devanagari name.

## Files Modified

### `restaurant/agent/facts.py`
- `format_readback_facts` — PR 087's phone and address lines removed; GUIDE
  text restored to its pre-087 wording.
- New `_spell_out(name)` — `"Ubair"` → `"U-B-A-I-R"`, the letter-by-letter
  form the agent speaks so a mis-heard name is caught before the kitchen
  ticket.
- New `format_contact_readback_facts(cart)` — CONTACT FACTS block: the name in
  Roman plus its spelled-out form, and the phone via the existing
  `format_phone_spoken`. GUIDE tells the LLM to phrase the ask in its own
  words in the customer's language, but to speak the letters and digits
  exactly as given, re-read after any correction, and call `confirm_contact`
  only on a yes.

### `restaurant/agent/readback_verify.py`
- PR 087's `_check_phone`, its call site in `verify_readback`, and its import
  removed — the file is byte-identical to its pre-087 state at that point.
- New `contact_verify_mode()` — `CONTACT_VERIFY` env var: `strict` (default) |
  `warn` | `off`. Deliberately separate from `READBACK_VERIFY` so the contact
  check can be relaxed live without weakening the order read-back check; the
  two have different failure modes.
- New `verify_contact_readback(spoken, cart)` → `ReadbackCheck`, built from:
  - `_check_spoken_phone` — reuses `_INDIC_NUMERAL_MAP` and
    `_spoken_words_to_digits` from `customer_info`, so English/Punjabi/Hindi
    digit words and ASCII/Gurmukhi/Devanagari numerals all count. The buffer
    is captured pre-TTS-transform, so any of those forms can appear.
  - `_check_spoken_name` — strips everything but ASCII letters from both sides
    before matching, so `"Aman"` and the spelled-out `"A-M-A-N"` both satisfy
    it. A name with no Roman letters at all is skipped (fail safe toward
    allowing) — which is exactly the hole the Roman-capture commit closes.

### `restaurant/agent/gates.py`
- `OrderSessionState` gains `contact_confirmed`, `contact_readback_pending`,
  `contact_spoken` — same capture shape as the order read-back.
- New `invalidate_contact_readback(state)` — clears the confirmation *and* any
  in-flight capture, so speech about the old details can't satisfy the check
  for the new ones.
- New `contact_readback_blockers(cart)` — a valid name and a valid 10-digit
  phone must actually be saved before there is anything to read back.
- `readback_blockers` gains the `contact_confirmed` requirement, appended
  under `if not blockers` so the LLM is never told to confirm details it
  hasn't collected yet.

### `restaurant/agent/core.py`
- `note_agent_speech` — every assistant line while `contact_readback_pending`
  is appended to `state.contact_spoken`.
- New `get_contact_readback` tool — checks `contact_readback_blockers`, returns
  the CONTACT FACTS block, arms `contact_readback_pending`, clears the buffer.
- New `confirm_contact` tool — checks the blockers, then `_verified_contact_confirm()`:
  in `strict` mode a failed check returns `CONTACT READBACK INCOMPLETE` with
  the specific problems and clears the buffer while staying pending, so the
  fresh re-read is what gets captured; `warn` logs + records a
  `contact_verify_warn` analytics event and allows; `off` is the rollback.
- `set_customer_contact` — both the name-save and phone-save paths call
  `invalidate_contact_readback`. The `PHONE SAVED` guide now points at
  `get_contact_readback` instead of ending the step.
- `set_customer_contact` — refuses a non-Roman name via `is_roman_name` and
  tells the LLM to transliterate the name it already heard. No customer-facing
  turn is spent: the refusal is a tool result and is never spoken.

  **The wording here is load-bearing and was tuned against the live model** —
  see *Live model verification* below. Do not paraphrase it without re-running
  `check_real_refusal.py`.

### `restaurant/customer_info.py`
- New `is_roman_name(name)` — NFD-normalizes, strips combining marks, then
  requires every remaining letter to be ASCII. So `"José"` passes and
  `"ਅਮਨ ਸਿੰਘ"` does not.
- Rejected alternative: `transliterate()` from `restaurant/clover/match.py`.
  It folds inherent vowels (`ਅਮਨ ਸਿੰਘ` → `"amn singh"`, `ਹਰਪ੍ਰੀਤ` →
  `"hrprit"`) — fine for menu matching, worse than Gurmukhi on a kitchen
  ticket. Making the LLM transliterate is the better source.

### `restaurant/agent/prompt.py`
- `_your_job()` gains the contact-confirmation step, flagged as checked.
- Both copies of the tool contract gain `get_contact_readback` /
  `confirm_contact`, and lose phone/address from the `get_order_readback`
  description.
- PR 088's "Customer names" hard speech rule (both copies) extended to cover
  capture: the LLM transliterates before calling `set_customer_contact`, and a
  non-Roman name is refused and never saved.

## Live Model Verification
Unit tests can assert a refusal string but not that the model can *act* on it.
Checked against `gpt-4.1-mini` (the configured default) at `temperature=0`,
end to end through the real tool with the real system prompt:

| Check | Result |
|---|---|
| Roman name sent on first pass, 6 Punjabi/Hindi utterances | **6/6** (`'ਮੇਰਾ ਨਾਮ ਹੈ ਜਸ਼ਨ।'` → `'Jashan'`, `'मेरा नाम राहुल शर्मा है।'` → `'Rahul Sharma'`) |
| Recovery from the **original** refusal text | **0/6** |
| Recovery from the shipped refusal text | **6/6**, model silent on the retry turn as instructed |

The 0/6 result was a real defect, not a hypothetical: the model didn't retry at
all, it spoke as though the save succeeded — *"I got your name as Jashan,
spelled J-A-S-H-A-N. Could you please provide your phone number now?"* — while
the cart had no name on it. Same false-claim shape PR 081 fixed for
`add_item`, and it would only have surfaced later as a `readback_blockers`
complaint. Fixed by scoring three candidate texts (0/6, 5/6, 6/6) and shipping
the 6/6 one: lead with a ⛔ nothing-saved marker stating the order has no name,
name the required next tool call explicitly, forbid speech for that turn.

Because first-pass transliteration is already 6/6, the refusal is a rare safety
net rather than a routine round trip.

## Tests
- `tests/test_agent_gates.py` (+3) — order read-back blocked until contact is
  confirmed; the blocker stays hidden while name/phone are still missing;
  `contact_readback_blockers` on an empty cart.
- `tests/test_agent_tools.py` (+7) — contact read-back facts spell the name and
  space the digits; `confirm_contact` refused when nothing was spoken; refused
  when only the phone was spoken; accepted on a full spoken read-back;
  a name change re-arms the gate; non-Roman name refused and not saved (asserts
  the tuned wording); order read-back no longer contains the phone.
- `tests/test_customer_info.py` (+3) — `is_roman_name` accepts Roman and
  accented names, rejects Gurmukhi/Devanagari.
- `tests/test_agent_facts.py`, `tests/test_readback_verify.py` — PR 087's phone
  blocks removed, contact equivalents added.
- Shared fixtures: `_complete_order` / `_make_ready` now run
  `get_contact_readback` → `note_agent_speech(_SPOKEN_CONTACT)` →
  `confirm_contact`; `_GOOD_READBACK` drops the phone.
- Full suite: **513 passed**. The 2 failures in `tests/test_hosted_checkout.py`
  (Clover sandbox pay-now path) **pre-exist on `main`** and are unrelated —
  verified by stashing this branch.

## What's NOT in This PR
- **Collection order unchanged** — stays `type → address → name → phone`.
  PR 091's `contact_blockers` encodes it and reordering would mean rewriting
  that gate for no correctness gain; the confirmation step works the same
  wherever it lands in the sequence.
- **Address is not confirmed** — only name and phone are read back. The
  address is already spoken once when set, and spelling out a street address
  is a poor fit for the letter-by-letter form.
- **Auto-place on `confirm_readback` kept** — PR 087 behaviour, untouched.
- **No transliteration in code** — the LLM does it; code only refuses the
  wrong script.

## How to Test
```
PYTHONPATH=. uv run --quiet pytest tests/ -q
```

Manual call-flow check:
1. Order an item, answer the additional-requests question, pick pickup.
2. Give a name and phone number. Confirm Sierra reads the name back **spelled
   letter by letter** and every phone digit as a separate English word, then
   asks whether they're right — before any order read-back.
3. Say the name is wrong, give a different one. Confirm Sierra saves it and
   re-reads both details rather than moving on.
4. Accept. Confirm the order read-back that follows covers the **cart only** —
   no phone number, no address.
5. Speak a Punjabi/Hindi name (e.g. "ਮੇਰਾ ਨਾਮ ਹੈ ਜਸ਼ਨ"). Confirm it is stored
   and read back as `Jashan`, not in Gurmukhi, and that the customer is never
   asked to repeat or spell it.

Kill switches, if either check misbehaves live:
```
CONTACT_VERIFY=warn   # log + analytics, don't refuse
CONTACT_VERIFY=off    # rollback to a bare flag flip
```

## Post-Merge: VPS Pull Command
`cd /opt/livekit-sarvam && git pull origin main && uv sync`
