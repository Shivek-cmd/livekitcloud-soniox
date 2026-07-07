"""Stage 2 — adapter between the engine and the (kept) Clover menu matcher.

Turns the existing MenuCache into the engine's `MenuResolver`: exact/confident
match -> Resolved, a term that maps to several available dishes -> Ambiguous,
nothing -> NotFound. This is the ONLY place the engine touches the menu, so the
engine stays pure and the matcher stays reusable.
"""

from __future__ import annotations

import os

from restaurant.clover.match import normalize
from restaurant.engine.core import Ambiguous, Dish, NotFound, Resolution, Resolved


def _resolve_min_conf() -> float:
    """A direct match is trusted at/above this confidence. Below it (the
    matcher's weak single-token tiers, e.g. one shared word like "deluxe"), we
    fall through and require the caller's actual phrase to appear in the dish —
    so "unicorn burger deluxe" does NOT become the Deluxe Platter."""
    try:
        return float(os.getenv("ENGINE_RESOLVE_MIN_CONF", "0.7"))
    except ValueError:
        return 0.7


def _has_spice(hit) -> bool:
    return any(g.name == "Spice Level" for g in hit.modifier_groups)


def _to_dish(hit) -> Dish:
    return Dish(
        id=hit.clover_item_id,
        name=hit.name,
        voice_line=hit.voice_line or hit.name,
        price=float(hit.price_dollars),
        has_spice=_has_spice(hit),
    )


class CloverResolver:
    """Wraps a MenuCache. `ambiguity_limit` caps how many options we read back."""

    def __init__(self, cache, *, ambiguity_limit: int = 3):
        self.cache = cache
        self.ambiguity_limit = ambiguity_limit

    def resolve(self, query: str) -> Resolution:
        q = (query or "").strip()
        if not q:
            return NotFound(query)

        scored = self.cache.find_item_scored(q)
        if scored is not None:
            hit, conf = scored
            if hit.available and float(conf) >= _resolve_min_conf():
                return Resolved(_to_dish(hit), float(conf))
            # Weak or unavailable -> fall through to the substring-gated check.

        # Matcher abstained (or matched an unavailable item): decide between a
        # genuine "which one?" and "not on the menu". Only consider a dish a
        # candidate if the caller's ACTUAL term appears in it (substring of the
        # dish's own text) — sharing one generic word ("deluxe") is not a match.
        nq = normalize(q)
        options = []
        for h in self.cache.search(q, limit=self.ambiguity_limit * 4):
            if not h.available:
                continue
            hay = normalize(" ".join(
                [h.name, h.speak_as or "", h.voice_line or "", *h.aliases]
            ))
            if nq and nq in hay:
                options.append(h)

        if len(options) >= 2:
            picks = tuple(_to_dish(h) for h in options[: self.ambiguity_limit])
            return Ambiguous(q, picks)
        if len(options) == 1:
            # The caller's term is contained in exactly one dish — return it. The
            # engine confirms every item, so a wrong guess is caught by the
            # caller's yes/no, never silently added.
            return Resolved(_to_dish(options[0]), 0.6)
        return NotFound(query)
