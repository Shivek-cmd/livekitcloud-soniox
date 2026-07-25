"""PR 095 — spoken additional-requests question verifier (pure, LLM-free).

place_order_blockers already refuses to place an order until
record_additional_requests has been called, but a tool call is not a question:
live calls showed the LLM clearing that blocker silently — calling the tool
with "no" without ever asking the customer about allergies or special
instructions. This module checks the SPOKEN assistant lines (captured through
note_agent_speech) for the question itself, so the gate can only be satisfied
by something the customer actually heard.

Same shape as readback_verify (PR 078) and the contact verifier (PR 092):
recognition is keyword-based and deliberately generous — the LLM owns the
phrasing, we only require that allergies or special instructions were raised
out loud. A false positive records an answer to a question phrased oddly; a
false negative costs one extra "please ask it now" round trip.

ADDITIONAL_REQUESTS_VERIFY env: "strict" (default — refuse to record),
"warn" (log + analytics, allow), "off" (emergency rollback).
"""

from __future__ import annotations

import os

from restaurant.agent.readback_verify import normalize_tokens


def additional_requests_verify_mode() -> str:
    """'strict' (default) | 'warn' | 'off' via ADDITIONAL_REQUESTS_VERIFY.

    Its own kill switch, separate from READBACK_VERIFY/CONTACT_VERIFY: this
    check guards a different failure (a question never asked), so it can be
    relaxed live without weakening the read-back checks.
    """
    mode = (os.getenv("ADDITIONAL_REQUESTS_VERIFY") or "").strip().lower()
    return mode if mode in ("warn", "off") else "strict"


# Allergy stems, prefix-matched so allergy/allergies/allergic (and the
# Gurmukhi/Devanagari spellings gpt-4.1-mini produces mid-Punjabi/Hindi) all
# count. The prompt keeps checkout lines in English, but the question is the
# one thing that must never be missed — accept every script.
_ALLERGY_PREFIXES = tuple(normalize_tokens("allerg ਐਲਰਜ ਅਲਰਜ एलर्ज अलर्ज"))

# The other half of the same question: special instructions / requests /
# dietary restrictions for the kitchen.
_REQUEST_TOKENS = frozenset(
    {
        "instruction",
        "instructions",
        "request",
        "requests",
        "requirement",
        "requirements",
        "dietary",
        "restriction",
        "restrictions",
    }
)
_REQUEST_PREFIXES = tuple(normalize_tokens("ਹਿਦਾਇਤ ਹਦਾਇਤ ਖਾਸ निर्देश हिदायत"))


def asks_additional_requests(spoken: str) -> bool:
    """True if the line raises allergies or special instructions with the
    customer — the wrap-up question, however the LLM chose to phrase it.

    Allergies count however they come up (the customer volunteering one is
    still the subject being handled). The request half additionally has to be
    a QUESTION: "special instructions" vocabulary shows up in ordinary
    acknowledgements too ("noted your request", "your dietary note is on the
    order"), and those must never arm the gate.

    The per-item "anything else?" prompt matches neither half — it is not this
    question, and asking it never clears the allergies gate.
    """
    tokens = normalize_tokens(spoken)
    if any(tok.startswith(_ALLERGY_PREFIXES) for tok in tokens):
        return True
    if "?" not in (spoken or ""):
        return False
    return any(
        tok in _REQUEST_TOKENS or tok.startswith(_REQUEST_PREFIXES)
        for tok in tokens
    )
