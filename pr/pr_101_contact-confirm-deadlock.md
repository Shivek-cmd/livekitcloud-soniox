# PR 101 — The contact confirmation can no longer deadlock a call

## Branch
`pr_101_contact-confirm-deadlock`

## What This PR Does
A live test call looped for its last five turns and **never placed the order**.
The caller said "yes" four times — twice in Punjabi, twice in English — and
Sierra re-read the name and phone every single turn, calling `confirm_contact`
each time and being refused each time. The PR 092 contact gate had become
**permanently unsatisfiable** for that call: no behaviour from the LLM or the
caller could get past it.

Two things were wrong, and this PR fixes both.

**The capture was armed in the wrong place.** Contact read-back speech was only
recorded while `contact_readback_pending`, a flag set by exactly one caller
(`get_contact_readback`) and cleared by any name/phone change. The correction
path the LLM is *told* to follow — `set_customer_contact` with the fix, then
read it back — skips the getter, so every re-read after a correction was
dropped on the floor. The strict refusal then cleared the buffer without
re-arming anything, despite a code comment claiming it kept the flag armed.
Empty buffer → refuse → clear → repeat, forever.

**The digits were being policed instead of produced.** What started the refusal
cycle was Sierra speaking `ਜ਼ੀਰੋ` (Gurmukhi "zero"), which was absent from
`_SPOKEN_DIGIT_WORDS`. That one dict backs *both* the TTS phone rewrite and the
confirm-time verifier, so a correct read-back of `7780039811` verified as
`77839811` **and** the caller heard a Gurmukhi digit inside their own phone
number — a break of the English-digits rule in `CLAUDE.md`, independent of the
loop. Widening the word list closes the forms we have seen; it cannot close the
category, because the set of renditions an LLM may produce is open-ended. So
`get_contact_readback` now **speaks the name-spelling and the digits itself**,
from code, and the script is right by construction rather than by lexicon
coverage.

## Files Modified

### `restaurant/agent/replies.py`
New `contact_readback_line(name=, phone=, language=)` — the code-owned
utterance, same shape and language keying as `order_placed_goodbye` (Punjabi
default for `pa`/`mixed`/unknown, accepts the `CustomerLanguage` enum or a bare
string). Only the short lead-in is translated; the details themselves come from
`facts._spell_out()` and `customer_info.format_phone_spoken()`:

```
ਇੱਕ ਵਾਰ ਦੁਹਰਾ ਦਿੰਦੀ ਹਾਂ ਜੀ — Paneer Tikka Singh, P-A-N-E-E-R T-I-K-K-A
S-I-N-G-H, seven, seven, eight, zero, zero, three, nine, eight, one, one.
```

Module-level imports of `_spell_out` / `format_phone_spoken` alongside the
existing `_qty_word` import; no new dependency direction.

### `restaurant/agent/core.py`
- **New `_speak_contact_readback()`** — speaks the line through
  `session.say(..., allow_interruptions=False)`, then feeds it to
  `note_agent_speech` and the recorder exactly as the goodbye does.
  Uninterruptible is deliberate: the confirm gate treats this line as proof the
  customer heard their details, so a half-spoken number must not satisfy it.
  Returns `False` — falling back to the LLM reading the facts, verifier still
  armed — when there is no session (web RPC, tests) or `say()` raises.
- **`get_contact_readback`** clears the capture window, speaks, and passes
  `spoken_by_code=` to the facts formatter. Docstring says it speaks.
- **`note_agent_speech`** captures contact speech whenever the cart has a name
  and phone and contact is unconfirmed — *not* only after a getter call. This is
  the same arm-on-content pattern as PR 095's `additional_requests_asked` two
  lines below it. Buffer capped at `_CONTACT_SPOKEN_LINES = 12` now that it
  spans turns. Because the code-spoken line goes through this same hook, it
  satisfies the PR 092 verifier with **no special-casing and no bypass flag**.
- **`_verified_contact_confirm`** gives up after
  `_MAX_CONTACT_CONFIRM_ATTEMPTS = 3` (two refusals, then the third attempt
  passes), logging a warning and recording a `contact_verify_forced` analytics
  event. A verifier gap should cost one possibly-unheard read-back, never a call
  that can never place its order. The refusal text no longer demands
  `get_contact_readback` before retrying, since the re-read is captured either
  way.

### `restaurant/agent/gates.py`
- `contact_readback_pending` **retired** from `OrderSessionState` — capture no
  longer depends on it.
- New `contact_verify_refusals: int` counter, reset on a successful confirm and
  in `invalidate_contact_readback`.
- `invalidate_contact_readback` still clears the buffer on any name/phone
  change, which is what keeps staleness covered: speech about the old number
  cannot satisfy the check for the new one.
- No blocker text and no phase-chain change; `readback_blockers` /
  `place_order_blockers` are exactly as before.

### `restaurant/agent/facts.py`
`format_contact_readback_facts(cart, *, spoken_by_code=False)`. When the details
were spoken by code it returns a `CONTACT READBACK ALREADY SPOKEN` block —
quoting what the customer just heard, instructing the LLM **not** to repeat the
name or number, and naming the correction path. The pre-existing `CONTACT FACTS`
block is unchanged and still used on the fallback paths.

### `restaurant/agent/prompt.py`
`_your_job()` and the `get_contact_readback` / `confirm_contact` tool-contract
lines now say the tool speaks the details and the LLM must not repeat them.
(Single copy — the `PROMPT_STYLE=legacy` builder was retired in PR 099.)

### `restaurant/customer_info.py`
`_SPOKEN_DIGIT_WORDS` gains the Gurmukhi and Devanagari renderings of the
English digit words (`ਜ਼ੀਰੋ`, `ਵਨ`, `ਟੂ` … `ज़ीरो`, `वन`, `टू` …) plus the missing
zero forms (`ਸਿਫਰ`, `ਸੁੰਨ`, `सिफ़र`, `सिफर`, `sifar`) and `पाँच`. A header comment
records that this dict is shared three ways — the verifier, `extract_phone_digits`
on caller speech, and `tts_transform._DIGIT_WORD_KEYS` — so a missing form
breaks all three at once, and entries must be unambiguous digit words.

Still worth having after the code-spoken change: it governs **caller-side**
phone parsing and the LLM-read fallback paths.

### `tests/test_agent_replies.py`
`contact_readback_line` is always English digits (asserts no ASCII digit and no
Indic digit word survives), the language variants, and — the load-bearing one —
that the generated line **passes `verify_contact_readback`**, which is what makes
the refusal path unreachable on the phone path.

### `tests/test_agent_tools.py`
New `_SayingSession` stub and module-level `_EventRecorder`. New tests:
- `test_contact_readback_is_spoken_by_code_in_english` — one code utterance with
  the spelled name and English digits, the facts block tells the LLM not to
  repeat, and `confirm_contact` succeeds with **zero** LLM speech.
- `test_contact_correction_respeaks_the_new_details` — the corrected number is
  re-spoken and the stale one is gone.
- `test_contact_readback_is_uninterruptible`.
- `test_contact_readback_falls_back_to_llm_when_say_fails` /
  `..._without_a_session` — facts block returned, verifier still refuses an
  unspoken confirm.
- `test_contact_confirm_survives_a_correction_without_a_fresh_getter` — the live
  repro: correction, re-read, no second getter call, confirm succeeds.
- `test_contact_confirm_still_refuses_a_stale_readback` — the flip side.
- `test_contact_verify_gives_up_after_repeated_refusals` — two refusals then
  through, with the `contact_verify_forced` event and the counter reset.
- `test_contact_speech_buffered_only_while_pending` renamed to
  `..._while_unconfirmed` and rewritten for the new arming condition.

### `tests/test_readback_verify.py`, `tests/test_customer_info.py`
Gurmukhi and Devanagari digit-word read-backs verify; a wrong number and a
missing name still fail; `contact_verify_mode()` env resolution;
`extract_phone_digits` on the in-script forms; and
`enforce_english_phone_in_speech` rewrites `ਜ਼ੀਰੋ` to `zero` so the caller never
hears a Gurmukhi digit on the fallback path.

## Files Deleted
None.

## What's NOT in This PR
- **No change to the order read-back.** `confirm_readback` / `verify_readback`
  keep their strict gate with no give-up counter — their `readback_pending` is
  not cleared by a refusal, so they do not have this failure shape.
- **No flow reordering.** Collection order, `place_order_blockers` and PR 091's
  fabrication backstop are untouched; the fix is where speech is produced and
  captured, not sequencing.
- **`CONTACT_VERIFY` kept as-is** (`strict` default, `warn`/`off` rollback). No
  live env change is needed or proposed.
- **The `stt_noise` false positives.** Five turns of the same call (14, 19, 20,
  28, 36) were dropped on clear, in-context Punjabi/Hindi speech, making the
  caller repeat themselves. A separate defect, deliberately untouched here.
- **`parse_customer_name` truncating three-word names.** Found while replaying
  this call: `'Aman Deep Singh' → 'Deep Singh'`, `'Gurdeep Singh Dhillon' →
  'Singh Dhillon'` (`customer_info.py`, the `len(words) == 3` branch). It did
  not bite the live call, because "Paneer Tikka Singh" trips the menu-word check
  and falls back to the raw string. The rule looks deliberate — salvaging a name
  out of a filler-prefixed utterance — so fixing it needs its own decision and
  its own PR.

## How to Test
```
PYTHONPATH=. uv run --with pytest pytest tests
```
646 pass. `tests/test_hosted_checkout.py::test_place_pay_now_disabled_no_url`
and `::test_place_pay_now_hco_failure_still_places` fail on `main` today too —
pre-existing, unrelated to this PR.

Manual call-flow check — this is the live repro, turns 29–42:
1. Order an item, answer the wrap-up question, choose delivery, give an address,
   a name, and a phone number.
2. `get_contact_readback` must **speak** the name spelled out and every digit as
   an English word, in one uninterruptible line, whatever language the
   conversation is in. Sierra's own next line must ask if it's right **without
   repeating** the name or the number.
3. Correct the last two digits. The corrected number must be re-spoken — again
   in English digits — and one "ਹਾਂ ਜੀ" must confirm and move to the order
   read-back. **This is the exact point the live call looped.**
4. Check the log for a `contact_verify_forced` event: on a healthy call there
   must be none. If one appears, the real path failed and the give-up valve
   carried it — investigate rather than accept.
5. Confirm no Gurmukhi/Devanagari digit word (`ਜ਼ੀਰੋ`, `ਸੱਤ`, `ज़ीरो`) is ever
   audible inside a phone number.
6. Rollback drill: `CONTACT_VERIFY=off` skips verification; the read-back is
   still code-spoken, since that no longer depends on the verifier.

## Post-Merge: VPS Pull Command
`cd /opt/livekit-sarvam && git pull origin main && uv sync`
