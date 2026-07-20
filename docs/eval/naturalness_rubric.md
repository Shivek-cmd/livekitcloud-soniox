# Naturalness rubric (PR 086)

Scores what "sounds natural" means for Sierra, so model/prompt changes have a
number instead of a vibe. Applied per call (one harness scenario transcript or
one live-call transcript) by `scripts/judge_transcripts.py` — an LLM judge for
the judgment dimensions plus mechanical checks for the countable ones. **Human
review remains the authority**; the judge exists to rank candidates and flag
transcripts worth reading, not to green-light a deploy by itself.

## Scored dimensions (1–5 each)

Score 5 = a human caller would not notice anything off; 3 = noticeably
mechanical but acceptable; 1 = obviously robotic or broken.

1. **Acknowledgement variety** — no stock acknowledgement phrase used more
   than 2× in one call (e.g. "Anything else?", "ਹਾਂ ਜੀ" as a reflex opener).
   Mechanical assist: the judge script counts repeated agent-turn openers and
   exact repeated sentences; >2 repeats caps this score at 2.
2. **Sentence-length variety** — turns are not all the same shape; short
   confirms mix with fuller sentences. All-clipped or all-long both lose
   points.
3. **Code-mix appropriateness** — replies mirror the customer's language of
   the moment; Punjabi in Gurmukhi, Hindi in Devanagari, English checkout
   terms kept in English. Natural code-mixing is GOOD; wrong-direction
   switches are not.
4. **Zero meta-speech** — never narrates tools/system ("let me add that to
   the system", "the tool says…"), never re-greets mid-call, never speaks
   GUIDE/facts lines verbatim (e.g. saying "ADDED: 2 x …" or the grounding
   parenthetical "ਗਾਰਲਿਕ ਨਾਨ (Garlic Naan)" aloud).
5. **Confusion-handling grace** — ambiguity, corrections, and "what do you
   have?" moments are handled warmly and land on a concrete next step, without
   blaming the customer or looping.
6. **Checkout efficiency** — mechanical, computed by the script, not the LLM
   judge: user turns from first order-intent to `place_order` success must not
   exceed the Step 1 baseline for the same scenario by more than 20%.
   Within budget = 5; each additional +20% over budget −1.

## Hard-marker flags (counted, not scored — any occurrence is a defect)

These are the failure classes observed on live calls (gap_fixes.md final
verification) and in harness history. The judge reports a count per transcript;
the comparison table shows totals per model.

- **stray-language** — any language outside English / Punjabi (Gurmukhi) /
  Hindi (Devanagari) appears in agent speech (live example: "少々お待ちください"),
  or a phone digit rendered in a non-English script (live example: "आठ").
- **roman-indic** — Punjabi/Hindi rendered in Roman script ("haan ji",
  "dhanyavaad") — a TTS-correctness violation, not a style choice.
- **ungrounded-dish** — agent names a specific dish that appears in NO tool
  result in the transcript and is not a menu item the customer named (live
  example: offering "Dominion Punjabi Special" unprompted with no
  `get_recommendations`/`search_menu` call).
- **fact-contradiction** — spoken quantity/name/total contradicts the
  ADDED/ORDER NOW/READBACK FACTS lines from tool results.
- **meta-speech** — instance counts backing dimension 4 (spoken tool-reply
  scaffolding, re-greeting, "as an AI" filler beyond the honest-AI persona).
- **spoken-parenthetical** — the grounding parenthetical "(English Name)"
  spoken inside a non-English sentence (PR 077 watch item).

## What is deliberately NOT scored

- Order-data correctness — the harness's machine assertions and the gates
  already own that (PR 030 lesson: the money path is code, not judgment).
- Inflection, honorifics, spice/note phrasing — unverifiable across languages
  (same boundary as the readback verifier).
- TTS audio quality — out of scope; this rubric sees text only.

## Aggregation

Per transcript: 6 dimension scores + flag counts. Per model: mean of each
dimension across transcripts, total flag counts, plus harness pass-rate and
LLM latency stats carried in from the harness run. A model is only a
candidate if harness machine assertions stay green — rubric scores rank
candidates, they never excuse a red harness.
