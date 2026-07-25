# PR 095 — The additional-requests question must actually be asked

## Branch
`pr_095_additional-requests-spoken-gate`

## What This PR Does
`place_order_blockers` has always refused to place an order until
`record_additional_requests` was called, but a tool call is not a question. On
live calls Sierra was clearing that blocker **silently** — calling the tool with
"no" without ever asking the customer about allergies or special instructions —
so the gate passed while the question was skipped. This PR closes that: the
answer can only be recorded once the question has been **spoken**, checked
against Sierra's actual assistant lines the same way the order read-back
(PR 078) and the name/phone read-back (PR 092) are checked.

The order of the flow is unchanged (items → additional requests → pickup/
delivery → name/phone → contact confirm → read-back), and the existing
placement blocker is untouched. This adds the missing half: the blocker can no
longer be cleared by something the customer never heard.

## Files Added

### `restaurant/agent/additional_requests_verify.py`
Pure, LLM-free verifier, same shape as `add_claim_verify.py`.
- `asks_additional_requests(line)` — true when a spoken line raises allergies,
  or **asks** about special instructions / requests / dietary restrictions.
  Allergy stems (`allerg`, `ਐਲਰਜ`, `एलर्ज`…) are prefix-matched and count
  however they come up, since the customer volunteering one still means the
  subject was handled. The request half additionally requires a question mark:
  that vocabulary shows up in ordinary acknowledgements ("noted your request",
  "your dietary note is on the order") which must never arm the gate.
  The per-item **"anything else?"** prompt matches neither half — asking it
  never clears the allergies gate, which is the exact live confusion.
- `additional_requests_verify_mode()` — `ADDITIONAL_REQUESTS_VERIFY` env:
  `strict` (default), `warn` (log + analytics, allow), `off` (kill switch).
  Its own switch, separate from `READBACK_VERIFY`/`CONTACT_VERIFY`, so this can
  be relaxed live without weakening the read-back checks.

### `tests/test_additional_requests_verify.py`
Parametrized recognition tests across English, Punjabi and Hindi phrasings, the
non-triggering lines above (including `Anything else for you?` and
`ਹੋਰ ਕੁਝ ਚਾਹੀਦਾ ਹੈ ਜੀ?`), and the env-var mode resolution.

## Files Modified

### `restaurant/agent/gates.py`
New `OrderSessionState.additional_requests_asked` flag. No gate, blocker text
or phase-chain change — `readback_blockers`/`place_order_blockers` are exactly
as before.

### `restaurant/agent/core.py`
- `note_agent_speech`: arms `additional_requests_asked` the moment a spoken
  line raises the question. Every assistant utterance reaches this hook from
  `worker.py`'s `conversation_item_added`, so the flag reflects real speech,
  not intent.
- New `_unasked_additional_requests_refusal()`: in `strict` it returns the
  refusal, in `warn` it logs + records an `additional_requests_verify_warn`
  analytics event and allows, in `off` it does nothing. The wording follows the
  Roman-name refusal shape from PR 086 — ⛔ nothing-was-recorded marker, a named
  `REQUIRED NEXT ACTION`, and an explicit "do not move on to the read-back";
  a plain "not recorded" let the model carry on as if it had asked.
- `record_additional_requests`: runs that check after the existing blockers, so
  a refusal records nothing and leaves `additional_requests_recorded` false —
  the order stays unplaceable.

### `restaurant/agent/prompt.py`
`_your_job()`: the wrap-up step now says ASK IT OUT LOUD, never skip it, and
notes the tool refuses if you never asked. The `record_additional_requests`
tool-contract line says the same — **in both the persona and the legacy
(`PROMPT_STYLE=legacy`) copies.**

### `tests/test_agent_tools.py`, `tests/test_agent_place_order.py`
Shared `_record_wrapup(agent, response)` helper — speaks the question, then
records — replacing the bare tool calls in every flow helper. New tests:
- `test_wrapup_refused_until_the_question_is_actually_asked` — the silent call
  is refused, `get_order_readback` still blocks, and a real spoken question
  arms it.
- `test_wrapup_verify_warn_and_off_modes`.
- `test_unrelated_agent_speech_does_not_arm_the_wrapup` — "anything else?" in
  English and Punjabi.

## Files Deleted
- `turnwatchdog.md` — PR 065–067 noisy-env EOU plan/handoff, shipped and merged.
- `watchdog_gaps.md` — the follow-up gap audit for the same work, all findings
  landed in commit `467d8c3`.

Both were root-level working docs for finished work, same cleanup as commit
`4bbd8aa` (`refactor.md`).

## What's NOT in This PR
- **No flow reordering.** An earlier attempt moved the question after the
  contact gate; that was reverted — the fix is enforcement, not sequencing.
- The existing `place_order_blockers` / `readback_blockers` texts and the
  `allergy_note` path to Clover/n8n — unchanged.
- No re-arming of `additional_requests_recorded` when the cart changes after
  the question was asked; the question was still genuinely asked.
- The Store/web checkout path — it has its own server-side validation and no
  spoken channel.

## How to Test
```
PYTHONPATH=. uv run --with pytest pytest tests
```
560 pass. `tests/test_hosted_checkout.py::test_place_pay_now_disabled_no_url`
and `::test_place_pay_now_hco_failure_still_places` fail on `main` today too —
pre-existing, unrelated to this PR.

Manual call-flow check:
1. Order an item and let Sierra go for the read-back without asking about
   allergies — `get_order_readback` refuses as before.
2. Watch the logs for a `record_additional_requests` call that isn't preceded
   by the spoken question — it must come back `⛔ NOTHING WAS RECORDED` and
   Sierra must then ask.
3. Answering "anything else?" repeatedly must never satisfy the gate.
4. Ask the real question in Punjabi (`ਕੋਈ ਐਲਰਜੀ ਜਾਂ ਖਾਸ ਹਿਦਾਇਤ?`) — the answer
   records normally.
5. Rollback drill: `ADDITIONAL_REQUESTS_VERIFY=off` restores the old behaviour
   exactly.

## Post-Merge: VPS Pull Command
`cd /opt/livekit-sarvam && git pull origin main && uv sync`
