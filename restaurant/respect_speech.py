"""Enforce formal/respectful second-person register in assistant speech.

Restaurant phone orders address unknown callers with Punjabi ``\u0a24\u0a41\u0a38\u0a40\u0a02 / \u0a24\u0a41\u0a39\u0a3e\u0a21\u0a3e``
or Hindi ``\u0906\u092a / \u0906\u092a\u0915\u093e``. LLM output sometimes slips to informal
``\u0a24\u0a42\u0a02 / \u0924\u0942``; this module rewrites those forms before TTS (PR 035).
"""

from __future__ import annotations

# (informal, formal) — sorted longest-first at import.
_RESPECT_PAIRS: tuple[tuple[str, str], ...] = (
    # Gurmukhi possessives / object pronouns
    ("\u0a24\u0a47\u0a30\u0a47", "\u0a24\u0a41\u0a39\u0a3e\u0a21\u0a47"),
    ("\u0a24\u0a47\u0a30\u0a40", "\u0a24\u0a41\u0a39\u0a3e\u0a21\u0a40"),
    ("\u0a24\u0a47\u0a30\u0a3e", "\u0a24\u0a41\u0a39\u0a3e\u0a21\u0a3e"),
    ("\u0a24\u0a47\u0a28\u0a42\u0a02", "\u0a24\u0a41\u0a39\u0a3e\u0a28\u0a42\u0a02"),
    ("\u0a24\u0a42\u0a02", "\u0a24\u0a41\u0a38\u0a40\u0a02"),
    # Hindi possessives / pronouns
    ("\u0924\u0941\u092e\u094d\u0939\u093e\u0930\u0947", "\u0906\u092a\u0915\u0947"),
    ("\u0924\u0941\u092e\u094d\u0939\u093e\u0930\u0940", "\u0906\u092a\u0915\u0940"),
    ("\u0924\u0941\u092e\u094d\u0939\u093e\u0930\u093e", "\u0906\u092a\u0915\u093e"),
    ("\u0924\u0941\u092e\u094d\u0939\u0947\u0902", "\u0906\u092a\u0915\u094b"),
    ("\u0924\u0947\u0930\u0947", "\u0906\u092a\u0915\u0947"),
    ("\u0924\u0947\u0930\u0940", "\u0906\u092a\u0915\u0940"),
    ("\u0924\u0947\u0930\u093e", "\u0906\u092a\u0915\u093e"),
    ("\u0924\u0941\u091d\u0947", "\u0906\u092a\u0915\u094b"),
    ("\u0924\u0941\u092e", "\u0906\u092a"),
    ("\u0924\u0942", "\u0906\u092a"),
    # Informal customer-directed verbs → respectful (unknown caller default)
    ("\u0a15\u0a30\u0a47\u0a17\u0a40", "\u0a15\u0a30\u0a4b\u0a17\u0a40"),
    ("\u0a15\u0a30\u0a47\u0a17\u0a06", "\u0a15\u0a30\u0a4b\u0a17\u0a47"),
    ("\u0a26\u0a47\u0a35\u0a47\u0a17\u0a40", "\u0a26\u0a47\u0a35\u0a4b\u0a17\u0a40"),
    ("\u0a26\u0a47\u0a35\u0a47\u0a17\u0a06", "\u0a26\u0a47\u0a35\u0a4b\u0a17\u0a47"),
    ("\u0a1a\u0a3e\u0a39\u0a47\u0a17\u0a40", "\u0a1a\u0a3e\u0a39\u0a4b\u0a17\u0a40"),
    ("\u0a1a\u0a3e\u0a39\u0a47\u0a17\u0a06", "\u0a1a\u0a3e\u0a39\u0a4b\u0a17\u0a47"),
    ("\u0a32\u0a35\u0a47\u0a17\u0a40", "\u0a32\u0a35\u0a4b\u0a17\u0a40"),
    ("\u0a32\u0a35\u0a47\u0a17\u0a06", "\u0a32\u0a35\u0a4b\u0a17\u0a47"),
    ("\u0915\u0930\u0947\u0917\u0940", "\u0915\u0930\u094b\u0917\u0940"),
    ("\u0915\u0930\u0947\u0917\u093e", "\u0915\u0930\u094b\u0917\u0947"),
)

_RESPECT_REPLACEMENTS: tuple[tuple[str, str], ...] = tuple(
    sorted(_RESPECT_PAIRS, key=lambda pair: len(pair[0]), reverse=True)
)

INFORMAL_REGISTER_MARKERS: frozenset[str] = frozenset(
    src for src, _ in _RESPECT_PAIRS
)


def apply_respectful_register(text: str) -> str:
    """Rewrite informal second-person forms to formal register."""
    if not text:
        return text
    out = text
    for informal, formal in _RESPECT_REPLACEMENTS:
        if informal in out:
            out = out.replace(informal, formal)
    return out
