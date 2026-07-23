# PR 091 — Order-flow phase gates + contact-fabrication backstop

## Branch
`pr_091_order-flow-phase-gates`

## What This PR Does
Closes a live-call bug: during a phone test call, Sierra called
`set_customer_contact` with an invented name ("Sir"/"Customer") and invented
phone number ("555-123-4567"/"416-555-1234") — data the caller never said —
before the conversation had even reached the point in the flow where
collecting contact info is appropriate (`order_type` wasn't set yet). Not a
symptom of the Gemini `PROHIBITED_CONTENT` filter (that fires later, after
contact info is already in context — confirmed unrelated).

Root cause: order-of-operations enforcement was **100% prompt-based**, except
for the last two steps (`get_order_readback`/`place_order`), which are the
only tools with real code-level preconditions via pure gate functions in
`gates.py`. Every other order-mutating tool — `set_customer_contact`,
`set_order_type`, `record_additional_requests` — could be called in any
order, any number of times, with no phase check, and `set_customer_contact`'s
`name`/`phone` args were validated for format only, never for whether the
caller actually said them.

This PR extends the existing `readback_blockers`/`place_order_blockers`
idiom (pure gate function → tool checks it → refuses with an instructional
string, never executes, never throws) to the three earlier steps, and adds a
narrow plausibility/placeholder backstop on `set_customer_contact` so
invented-but-syntactically-valid data can't be saved even once the flow has
legitimately reached that step. No new phase enum or state-machine — the
chain of composed gate functions in `gates.py` **is** the code-owned phase
concept, same as `place_order_blockers` already composing on top of
`readback_blockers`.

## Files Modified

### `restaurant/agent/gates.py`
- New `additional_requests_blockers(cart)` — cart must be non-empty before
  the closing additional-requests question.
- New `order_type_blockers(cart, state)` — wraps the above; additional
  requests must be recorded before pickup/delivery is asked.
- New `contact_blockers(cart, state)` — wraps the above; `order_type` (+
  `delivery_address` if delivery) must be set before `set_customer_contact`
  may run. This is the check that directly closes the reported bug: at the
  point of the incident, `cart.order_type` was unset, so this gate refuses
  the call outright.
- `readback_blockers`/`place_order_blockers` untouched — they remain the
  superset check right before readback/placement; the new gates only encode
  *ordering*, not final name/phone validity.

### `restaurant/agent/core.py`
- Imports the three new gate functions.
- `record_additional_requests`, `set_order_type`, `set_customer_contact` each
  check their gate as the first statement in the tool body; on a blocker,
  return `"Cannot <do X> yet:\n- ..."` and log via `_record_tool` without any
  mutation — identical shape to `get_order_readback`'s existing refusal.
- `set_customer_contact`'s phone-save branch also runs the new
  `is_plausible_phone` check when `accumulate_phone` reports `event ==
  "saved"`; on failure, appends a `PHONE NOT SAVED` fact/guide instead of
  saving (falls through the existing facts/guides accumulation rather than
  short-circuiting, so a `NAME SAVED` fact from the same call isn't dropped).
- `set_customer_contact`'s `PHONE SAVED` guide no longer tells the LLM to
  confirm the number back itself right away — that produced a redundant
  spoken readback before the real one (main already gained a phone line in
  `format_readback_facts` plus strict spoken-phone verification in
  `readback_verify.py` from an earlier, unrelated PR merged ahead of this
  branch; this change just stops `set_customer_contact` from pre-empting
  it). The guide now says not to read it back yet — it'll be read back once,
  in English word digits, during `get_order_readback`.
- Left deliberately ungated: `add_item`/`set_item_quantity`/`remove_item`/
  `set_item_spice` (prompt explicitly allows item changes at any point — no
  fabrication risk in a menu lookup that already goes through
  `_resolve_menu_item`) and `set_delivery_address` (inert until
  `set_order_type` fires, which is itself now gated).

### `restaurant/customer_info.py`
- `is_valid_customer_name` extended with `_PLACEHOLDER_NAME_RE` — rejects
  single-token honorifics/placeholders ("sir", "sirji", "ma'am", "madam",
  "miss", "mister", "customer", "caller", "guest", "unknown", "n/a"), same
  "only reject when the word basically *is* the whole name" rule already
  used by `_BLOCKED_NAME_RE` so multi-word real names aren't affected.
- New `is_plausible_phone(digits) -> bool` — false for the reserved/fictional
  NANP `555` area code or exchange, all-same-digit numbers, and the two
  canonical sequential strings. Scoped to the LLM-authored
  `set_customer_contact` path only — never applied inside
  `extract_phone_digits`/`accumulate_phone`, which stay pure and must never
  second-guess a real caller's digits captured by the PR 082 code-side
  transcript-capture path.

## Tests
- `tests/test_agent_gates.py` (+8): each new gate function — empty-cart
  block, additional-requests-not-recorded block, order-type-not-set block,
  delivery-address-missing block, and a direct repro
  (`test_contact_blocked_reproduces_the_incident`) asserting
  `contact_blockers(OrderCart(), OrderSessionState())` is non-empty.
- `tests/test_customer_info.py` (+6): placeholder names rejected, real names
  still accepted, `555` area code/exchange rejected, repeated/sequential
  digit numbers rejected, a real-looking number accepted.
- `tests/test_agent_tools.py`: new `test_contact_rejects_implausible_phone`
  and `test_contact_blocked_before_order_type_set` (direct regression test
  for the incident shape — `set_customer_contact(name="Sir",
  phone="555-123-4567")` before `order_type` is set refuses and saves
  nothing). Existing contact/order-type/additional-requests tests updated
  with a `_ready_for_contact` helper (add item → record additional requests
  → set order type) since those tools now gate on flow position; `_complete_order`
  and `_make_ready` fixtures across `test_agent_tools.py`/`test_agent_place_order.py`
  switched their test phone number off the `555` exchange (`7805551234` →
  `7804441234`) since it now legitimately fails the new plausibility check —
  this also required updating the spoken-readback fixtures
  (`_GOOD_READBACK` in `test_agent_tools.py`, the `note_agent_speech` text
  in `_make_ready` in `test_agent_place_order.py`) to speak the new digits,
  since main's strict `readback_verify` phone check would otherwise fail
  against the old spoken number. New
  `test_set_customer_contact_no_longer_prompts_immediate_phone_readback`
  asserts the `PHONE SAVED` guide no longer tells the LLM to read the
  number back itself.
- Full suite: **480 passed** (post-rebase onto main, which added its own
  tests since this branch was cut).

## Deviations from Plan
- `is_plausible_phone`'s `555` check covers both the area-code and
  exchange position (`digits[0:3]` and `digits[3:6]`) — the original repro
  number `555-123-4567` has `555` as the *area code*, not the exchange, so
  an exchange-only check would have missed it.
- The implausible-phone branch appends to `facts`/`guides` and falls through
  to the existing single return at the end of `set_customer_contact` rather
  than returning immediately, so a `NAME SAVED` fact from the same tool call
  isn't silently dropped when the phone in the same call is rejected.

## What's NOT in This PR
- Transcript corroboration for `name`/`phone` (matching the LLM's claimed
  value token-for-token against the raw caller utterance) — would need a new
  rolling transcript buffer and fuzzy cross-language matching; the phase
  gate + placeholder/plausibility blocklist already close the reported
  incident. Flagged as a possible follow-up only if a later incident shows a
  plausible-but-unspoken *real-sounding* name/number being invented mid-flow
  (phase gate satisfied, blocklist doesn't catch it).
- Gemini `PROHIBITED_CONTENT`/`FallbackAdapter` — ruled out as the cause of
  this incident; untouched.

## How to Test
```
PYTHONPATH=. uv run --with pytest pytest tests -q
```

Manual call-flow check:
1. Start a call/web session, order at least one item.
2. Before answering the additional-requests question, try to skip ahead
   ("my name is John, phone is 555-1234" mid-item-taking) — confirm Sierra
   does NOT save contact info and continues the normal flow instead.
3. Complete the flow normally through order type; confirm phone/name are now
   collectable and saved once actually spoken. Confirm Sierra does NOT read
   the phone number back right after saving it — it should only be spoken
   once, during the read-back step.
4. Answer the name question ambiguously (e.g. "sir") — confirm placeholder
   names are rejected and re-asked rather than silently saved.
5. Confirm the full happy path (items → additional requests → order type →
   name → phone → readback → confirm → place) still completes with no
   spurious refusals.

## Post-Merge: VPS Pull Command
`cd /opt/livekit-sarvam && git pull origin main && uv sync`
