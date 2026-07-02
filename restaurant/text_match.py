"""Indic-safe word boundaries for intent/keyword regexes.

Python re's ``\\b`` treats Gurmukhi/Devanagari vowel signs and nasalization
marks (matras, bindi, tippi, halant) as NON-word characters, so a pattern like
``\\bਨਹੀਂ\\b`` can never match — the word ends in bindi and ``\\b`` needs a word
character on one side. Every Gurmukhi keyword ending in a matra/bindi inside a
``\\b(...)\\b`` alternation is silently dead (PR 034 live bug: callers answering
"ਨਹੀਂ ਨਹੀਂ" at the allergies step were dropped as background noise).

Replacement semantics:

- left boundary  ``(?<![\\w + marks])`` — no match starting mid-word (the old
  ``\\b`` wrongly allowed a match right after a matra, e.g. ਲੈ inside ਮਿਲੈਗਾ)
- right boundary ``(?!\\w)`` — forbids letter continuation but ALLOWS combining
  marks, so intentional stem patterns keep working (ਕਰ ਦ → ਕਰ ਦਿਓ,
  ਮਿਲੇਗ → ਮਿਲੇਗਾ, ਚਾਹੀ → ਚਾਹੀਦਾ)

Indic LETTERS already count as ``\\w``; only the combining-mark ranges need
special handling.
"""

from __future__ import annotations

import re

# Devanagari signs/matras + Gurmukhi signs/matras (combining marks, not \w)
INDIC_MARKS = (
    "ऀ-ः"  # Devanagari candrabindu/anusvara/visarga
    "ऺ-ॏ"  # Devanagari matras, nukta, halant
    "॑-ॗ"  # Devanagari stress/vedic marks
    "ॢ-ॣ"  # Devanagari vocalic marks
    "ਁ-ਃ"  # Gurmukhi adak bindi/bindi/visarga
    "਼"         # Gurmukhi nukta
    "ਾ-੍"  # Gurmukhi matras + halant
    "ੰ-ੱ"  # Gurmukhi tippi + addak
    "ੵ"         # Gurmukhi yakash
)

_LEFT_GUARD = rf"(?<![\w{INDIC_MARKS}])"


def word_bounded(body: str) -> str:
    """Wrap a regex alternation with Indic-safe word boundaries.

    Drop-in replacement for ``\\b(?:body)\\b`` that works for Gurmukhi,
    Devanagari, and Latin alike. The body keeps its own capture groups.
    """
    return rf"{_LEFT_GUARD}(?:{body})(?!\w)"


def indic_word_re(body: str, flags: int = re.IGNORECASE) -> re.Pattern[str]:
    return re.compile(word_bounded(body), flags)
