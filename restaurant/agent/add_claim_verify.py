"""PR 081 — post-refusal false-add-claim verifier (money path, pure, LLM-free).

add_item refuses (NOT FOUND / AMBIGUOUS / unavailable) without touching the
cart, but a tool result is just a string — the LLM can narrate a successful
add anyway ("I've added one Chana Masala"). This module checks the next
SPOKEN assistant line (captured via note_agent_speech while a refusal is
pending) for exactly that lie.

Kept deliberately conservative: a false positive speaks an unnecessary
apology, a false negative is the live bug — but the checker still requires
BOTH a mention of the refused item AND an add-claim verb, with a negation
guard first, so honest refusal speech never trips it.

ADD_CLAIM_VERIFY env: "strict" (default — corrective speech + re-anchor),
"warn" (log + analytics only), "off" (emergency rollback).
"""

from __future__ import annotations

import os

from restaurant.agent.readback_verify import normalize_tokens
from restaurant.clover.match import content_tokens, phonetic_key


def add_claim_verify_mode() -> str:
    """'strict' (default) | 'warn' | 'off' via the ADD_CLAIM_VERIFY env var."""
    mode = (os.getenv("ADD_CLAIM_VERIFY") or "").strip().lower()
    return mode if mode in ("warn", "off") else "strict"


# Negation / apology vocabulary — any hit means the line is (or contains) a
# refusal, so it can never be flagged as a false add claim. Single tokens
# only; apostrophe contractions ("don't", "couldn't") tokenize to a pair
# ending in ("…n", "t") and are caught by _has_negation's pair rule.
_NEG_TOKENS = frozenset(
    normalize_tokens(
        "not cannot cant dont didnt doesnt isnt wasnt couldnt wouldnt wont "
        "havent hasnt sorry unfortunately unable nahi nahin "
        "ਨਹੀਂ ਮਾਫ਼ ਮਾਫ नहीं माफ़ माफ"
    )
)

# Closed add-claim verb list — English exact tokens; Gurmukhi/Devanagari
# stems prefix-matched (ਲਿਖ ਲਈ / ਜੋੜ ਦਿੱਤਾ / ਪਾ ਦਿੱਤਾ / लिख लिया / जोड़ दिया…).
_EN_VERBS = frozenset({"added", "adding", "got", "noted", "put", "down"})
_VERB_PREFIXES = tuple(normalize_tokens("ਲਿਖ ਜੋੜ ਪਾ ਨੋਟ लिख जोड़ डाल"))

_MIN_PHONETIC_KEY = 3  # shorter keys collide too easily to identify a dish


def _has_negation(tokens: list[str]) -> bool:
    for i, tok in enumerate(tokens):
        if tok in _NEG_TOKENS:
            return True
        # "don't" / "isn't" / "couldn't" → ("don", "t") after tokenization.
        if tok == "t" and i > 0 and tokens[i - 1].endswith("n"):
            return True
    return False


def _mentions_query(tokens: list[str], refused_query: str) -> bool:
    """≥1 distinctive content token of the refused query spoken — exact or by
    equal phonetic key (catches cross-script ਚਨਾ ਮਸਾਲਾ for 'Chana Masala')."""
    query_pairs = [
        (tok, key)
        for tok in content_tokens(refused_query)
        if len(key := phonetic_key(tok)) >= _MIN_PHONETIC_KEY
    ]
    if not query_pairs:
        return False
    spoken_keys = {phonetic_key(tok) for tok in tokens}
    spoken_set = set(tokens)
    return any(tok in spoken_set or key in spoken_keys for tok, key in query_pairs)


def _has_add_verb(tokens: list[str]) -> bool:
    return any(
        tok in _EN_VERBS or tok.startswith(_VERB_PREFIXES) for tok in tokens
    )


def falsely_claims_add(spoken: str, refused_query: str) -> bool:
    """True only if the spoken line claims the refused item was added:
    no negation, the item is mentioned, AND an add-claim verb is present.
    ("Did you mean Chana Chaat?" → False; "Sorry, no Chana Masala" → False.)
    """
    tokens = normalize_tokens(spoken)
    if not tokens or _has_negation(tokens):
        return False
    return _mentions_query(tokens, refused_query) and _has_add_verb(tokens)
