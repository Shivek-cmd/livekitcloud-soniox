"""Deterministic order engine (rebuild).

The control philosophy of the old order_flow/agent ladder was: the LLM drives
the conversation and mutates the cart via free tool calls, and code chases it
with regexes and guard flags. That is why one ambiguous word ("fish") could
become two invented dishes with an invented quantity.

This package inverts it:

    LLM  = language only. It converts ONE messy multilingual utterance into a
           structured `Proposal` (understand + translate). It never touches state.
    CODE = owns 100% of state. The `OrderEngine` consumes a `Proposal`, resolves
           dishes through the (kept) menu matcher, and returns `Action`s. Every
           item and the final order are CONFIRMED before they lock. Ambiguity is
           always a question, never a guess.

Pure, synchronous, fully unit-testable. The LiveKit/STT/TTS layer is a thin
adapter around this (see docs); this module has zero I/O.
"""

from restaurant.engine.core import (
    Action,
    AddRequest,
    Ambiguous,
    Dish,
    Line,
    NotFound,
    OrderEngine,
    Phase,
    Proposal,
    Resolved,
)

__all__ = [
    "Action",
    "AddRequest",
    "Ambiguous",
    "Dish",
    "Line",
    "NotFound",
    "OrderEngine",
    "Phase",
    "Proposal",
    "Resolved",
]
