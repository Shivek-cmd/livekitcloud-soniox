"""Deterministic order engine — code owns state; the LLM only proposes.

Guarantees enforced here (not by prompt, by control flow):
  * A dish is NEVER added unless it resolved to exactly one menu item AND the
    caller confirmed it. Ambiguous/unknown => a question, never a guess.
  * A quantity is NEVER invented. If the caller didn't say a number, the engine
    asks; it does not default to anything on the money path.
  * "Correct the quantity" and "add more" are different operations and can never
    be confused (corrections set an exact total; adds are gated by confirmation).
  * The final order is read back from real cart data and confirmed before place.

The engine is a pure state machine: `handle(proposal) -> list[Action]`. It has
no I/O, no LLM, no clock. Actions describe WHAT to say (kind + grounded data);
a separate renderer turns them into the caller's language.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol


# --------------------------------------------------------------------------- #
# Menu resolution — thin result types over the existing (kept) matcher.
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Dish:
    id: str
    name: str
    voice_line: str          # exactly how TTS should say the dish
    price: float
    has_spice: bool = False


@dataclass(frozen=True)
class Resolved:
    dish: Dish
    confidence: float


@dataclass(frozen=True)
class Ambiguous:
    query: str
    options: tuple[Dish, ...]   # 2+ real dishes the term could mean


@dataclass(frozen=True)
class NotFound:
    query: str


Resolution = Resolved | Ambiguous | NotFound


class MenuResolver(Protocol):
    def resolve(self, query: str) -> Resolution: ...


# --------------------------------------------------------------------------- #
# Proposal — the ONLY thing the LLM produces. Pure language understanding.
# --------------------------------------------------------------------------- #
@dataclass
class AddRequest:
    query: str
    quantity: int | None = None   # None = caller did not state one -> engine asks


@dataclass
class Proposal:
    adds: list[AddRequest] = field(default_factory=list)
    corrections: list[tuple[str, int]] = field(default_factory=list)  # (query, new total)
    removals: list[str] = field(default_factory=list)
    choice: str | None = None          # answer to a "which one?" question
    quantity_answer: int | None = None  # answer to "how many?"
    yes: bool = False
    no: bool = False
    order_type: str | None = None       # "pickup" | "delivery"
    name: str | None = None
    phone: str | None = None
    done_adding: bool = False
    wants_human: bool = False
    understood: bool = True             # False => nothing parsed -> ask to repeat

    def _has_content(self) -> bool:
        return bool(
            self.adds or self.corrections or self.removals or self.choice
            or self.quantity_answer is not None or self.yes or self.no
            or self.order_type or self.name or self.phone or self.done_adding
        )


# --------------------------------------------------------------------------- #
# Cart
# --------------------------------------------------------------------------- #
@dataclass
class Line:
    dish: Dish
    quantity: int
    note: str = ""

    @property
    def total(self) -> float:
        return self.dish.price * self.quantity


@dataclass
class _Staged:
    dish: Dish
    quantity: int | None = None


# --------------------------------------------------------------------------- #
# Phases & Actions
# --------------------------------------------------------------------------- #
class Phase(str, Enum):
    COLLECTING = "collecting"        # ready for the next item / "done"
    CLARIFY_ITEM = "clarify_item"    # asked which of N dishes
    ASK_QUANTITY = "ask_quantity"    # asked how many of the staged dish
    CONFIRM_ITEM = "confirm_item"    # asked "one X — yes?"
    ASK_SPICE = "ask_spice"          # staged/added dish needs a spice level
    ASK_ALLERGIES = "ask_allergies"
    ASK_ORDER_TYPE = "ask_order_type"
    READBACK = "readback"            # read whole order, awaiting confirm
    ASK_NAME = "ask_name"
    ASK_PHONE = "ask_phone"
    PLACED = "placed"


@dataclass
class Action:
    kind: str
    data: dict = field(default_factory=dict)

    def __repr__(self) -> str:  # nicer test output
        return f"Action({self.kind}, {self.data or ''})".replace(", )", ")")


def _act(kind: str, **data) -> Action:
    return Action(kind, data)


# --------------------------------------------------------------------------- #
# Engine
# --------------------------------------------------------------------------- #
class OrderEngine:
    """One instance per call. Deterministic; no I/O."""

    def __init__(self, resolver: MenuResolver, *, delivery_charge: float = 0.0):
        self.resolver = resolver
        self.delivery_charge = delivery_charge
        self.phase: Phase = Phase.COLLECTING
        self.lines: list[Line] = []
        self.order_type: str | None = None
        self.name: str | None = None
        self.phone: str | None = None
        self.allergies_done: bool = False
        self.readback_confirmed: bool = False
        self._staged: _Staged | None = None
        self._clarify: tuple[Dish, ...] | None = None
        self._spice_line: Line | None = None   # committed line awaiting spice

    # ---- public ---------------------------------------------------------- #
    def handle(self, p: Proposal) -> list[Action]:
        if self.phase == Phase.PLACED:
            return [_act("already_placed")]
        if p.wants_human:
            return [_act("transfer")]

        # Corrections/removals are honoured in ANY phase and never additive.
        acts: list[Action] = []
        acts += self._apply_corrections(p.corrections)
        acts += self._apply_removals(p.removals)

        handler = {
            Phase.CLARIFY_ITEM: self._on_clarify,
            Phase.ASK_QUANTITY: self._on_quantity,
            Phase.CONFIRM_ITEM: self._on_confirm_item,
            Phase.ASK_SPICE: self._on_spice,
            Phase.ASK_ALLERGIES: self._on_allergies,
            Phase.ASK_ORDER_TYPE: self._on_order_type,
            Phase.READBACK: self._on_readback,
            Phase.ASK_NAME: self._on_name,
            Phase.ASK_PHONE: self._on_phone,
        }.get(self.phase, self._on_collecting)

        step = handler(p)
        if step:
            return acts + step
        if acts:
            return acts
        # Nothing understood and nothing pending resolved -> ask to repeat,
        # but never dead-air and never invent.
        if not p._has_content() or not p.understood:
            return [_act("repeat")]
        return [self._prompt_for_phase()]

    # ---- collecting / adding -------------------------------------------- #
    def _on_collecting(self, p: Proposal) -> list[Action]:
        if p.adds:
            return self._begin_add(p.adds[0], queued=p.adds[1:])
        if p.done_adding:
            if not self.lines:
                return [_act("cart_empty_cannot_finish")]
            return self._advance_after_items()
        return []

    def _begin_add(self, req: AddRequest, queued: list[AddRequest]) -> list[Action]:
        # (queued extra items are intentionally handled ONE at a time, each
        # confirmed — we never batch-add a list the model produced.)
        self._queued = list(queued)
        res = self.resolver.resolve(req.query)
        if isinstance(res, NotFound):
            return [_act("not_on_menu", query=req.query)]
        if isinstance(res, Ambiguous):
            self._clarify = res.options
            self.phase = Phase.CLARIFY_ITEM
            return [_act("clarify", query=res.query,
                         options=[d.name for d in res.options])]
        # Resolved -> stage; ask quantity if none was stated (never invent).
        self._staged = _Staged(dish=res.dish, quantity=req.quantity)
        return self._after_staged()

    def _after_staged(self) -> list[Action]:
        assert self._staged is not None
        if self._staged.quantity is None:
            self.phase = Phase.ASK_QUANTITY
            return [_act("ask_quantity", dish=self._staged.dish.voice_line)]
        self.phase = Phase.CONFIRM_ITEM
        return [_act("confirm_item", dish=self._staged.dish.voice_line,
                     quantity=self._staged.quantity)]

    def _on_clarify(self, p: Proposal) -> list[Action]:
        if self._clarify is None:
            self.phase = Phase.COLLECTING
            return []
        choice = p.choice or (p.adds[0].query if p.adds else None)
        if not choice:
            return [_act("clarify", options=[d.name for d in self._clarify])]
        picked = self._match_choice(choice, self._clarify)
        if picked is None:
            return [_act("clarify", options=[d.name for d in self._clarify])]
        qty = p.quantity_answer or (p.adds[0].quantity if p.adds else None)
        self._clarify = None
        self._staged = _Staged(dish=picked, quantity=qty)
        return self._after_staged()

    def _on_quantity(self, p: Proposal) -> list[Action]:
        assert self._staged is not None
        qty = p.quantity_answer
        if qty is None and p.adds and p.adds[0].quantity is not None:
            qty = p.adds[0].quantity
        if qty is None or qty < 1:
            return [_act("ask_quantity", dish=self._staged.dish.voice_line)]
        self._staged.quantity = qty
        self.phase = Phase.CONFIRM_ITEM
        return [_act("confirm_item", dish=self._staged.dish.voice_line, quantity=qty)]

    def _on_confirm_item(self, p: Proposal) -> list[Action]:
        assert self._staged is not None
        if p.no:
            self._staged = None
            self.phase = Phase.COLLECTING
            return [_act("cancelled_item")] + self._next_queued_or_prompt()
        if not p.yes:
            # Not a yes/no — re-ask the confirmation rather than assume.
            return [_act("confirm_item", dish=self._staged.dish.voice_line,
                         quantity=self._staged.quantity)]
        line = Line(dish=self._staged.dish, quantity=self._staged.quantity or 1)
        self.lines.append(line)
        self._staged = None
        if line.dish.has_spice:
            self._spice_line = line
            self.phase = Phase.ASK_SPICE
            return [_act("ask_spice", dish=line.dish.voice_line)]
        self.phase = Phase.COLLECTING
        return [_act("item_added", dish=line.dish.voice_line, quantity=line.quantity)] \
            + self._next_queued_or_prompt()

    def _on_spice(self, p: Proposal) -> list[Action]:
        if self._spice_line is None:
            self.phase = Phase.COLLECTING
            return []
        note = (p.choice or "").strip()
        if not note and not p.understood:
            return [_act("ask_spice", dish=self._spice_line.dish.voice_line)]
        self._spice_line.note = note
        dish = self._spice_line.dish
        self._spice_line = None
        self.phase = Phase.COLLECTING
        return [_act("item_added", dish=dish.voice_line, note=note)] \
            + self._next_queued_or_prompt()

    def _next_queued_or_prompt(self) -> list[Action]:
        queued = getattr(self, "_queued", [])
        if queued:
            nxt = queued[0]
            return self._begin_add(nxt, queued[1:])
        return [_act("anything_else")]

    # ---- checkout chain -------------------------------------------------- #
    def _advance_after_items(self) -> list[Action]:
        self.phase = Phase.ASK_ALLERGIES
        return [_act("ask_allergies")]

    def _on_allergies(self, p: Proposal) -> list[Action]:
        # Any answer (a note, "no", yes) completes the step — but code marks it,
        # so it is asked exactly once and never skipped.
        if not (p.yes or p.no or p.choice or p.understood):
            return [_act("ask_allergies")]
        self.allergies_done = True
        note = (p.choice or "").strip()
        self.phase = Phase.ASK_ORDER_TYPE
        return [_act("noted_allergies", note=note), _act("ask_order_type")]

    def _on_order_type(self, p: Proposal) -> list[Action]:
        if p.order_type not in ("pickup", "delivery"):
            return [_act("ask_order_type")]
        self.order_type = p.order_type
        return self._go_readback()

    def _go_readback(self) -> list[Action]:
        self.phase = Phase.READBACK
        return [_act("readback", **self.order_summary())]

    def _on_readback(self, p: Proposal) -> list[Action]:
        if p.no:
            # Something's wrong — go back to collecting so they can fix it.
            self.phase = Phase.COLLECTING
            return [_act("readback_rejected")]
        if not p.yes:
            return [_act("readback", **self.order_summary())]
        self.readback_confirmed = True
        self.phase = Phase.ASK_NAME
        return [_act("ask_name")]

    def _on_name(self, p: Proposal) -> list[Action]:
        if not p.name:
            return [_act("ask_name")]
        self.name = p.name.strip()
        self.phase = Phase.ASK_PHONE
        return [_act("ask_phone", name=self.name)]

    def _on_phone(self, p: Proposal) -> list[Action]:
        digits = "".join(ch for ch in (p.phone or "") if ch.isdigit())
        if len(digits) != 10:
            return [_act("ask_phone", name=self.name or "")]
        self.phone = digits
        self.phase = Phase.PLACED
        return [_act("order_placed", **self.order_summary())]

    # ---- corrections / removals (any phase) ------------------------------ #
    def _apply_corrections(self, corrections: list[tuple[str, int]]) -> list[Action]:
        acts: list[Action] = []
        for query, new_total in corrections:
            line = self._find_line(query)
            if line is None:
                acts.append(_act("correction_no_such_item", query=query))
                continue
            if new_total <= 0:
                self.lines.remove(line)
                acts.append(_act("item_removed", dish=line.dish.voice_line))
            else:
                line.quantity = new_total       # exact set — never additive
                acts.append(_act("quantity_corrected",
                                 dish=line.dish.voice_line, quantity=new_total))
        return acts

    def _apply_removals(self, removals: list[str]) -> list[Action]:
        acts: list[Action] = []
        for query in removals:
            line = self._find_line(query)
            if line is not None:
                self.lines.remove(line)
                acts.append(_act("item_removed", dish=line.dish.voice_line))
        return acts

    # ---- helpers --------------------------------------------------------- #
    def _prompt_for_phase(self) -> Action:
        return {
            Phase.CLARIFY_ITEM: _act("clarify",
                                     options=[d.name for d in (self._clarify or ())]),
            Phase.ASK_QUANTITY: _act("ask_quantity",
                                     dish=self._staged.dish.voice_line if self._staged else ""),
            Phase.CONFIRM_ITEM: _act("confirm_item",
                                     dish=self._staged.dish.voice_line if self._staged else "",
                                     quantity=self._staged.quantity if self._staged else None),
            Phase.ASK_SPICE: _act("ask_spice",
                                  dish=self._spice_line.dish.voice_line if self._spice_line else ""),
            Phase.ASK_ALLERGIES: _act("ask_allergies"),
            Phase.ASK_ORDER_TYPE: _act("ask_order_type"),
            Phase.READBACK: _act("readback", **self.order_summary()),
            Phase.ASK_NAME: _act("ask_name"),
            Phase.ASK_PHONE: _act("ask_phone", name=self.name or ""),
        }.get(self.phase, _act("anything_else"))

    def _find_line(self, query: str) -> Line | None:
        res = self.resolver.resolve(query)
        target_id = res.dish.id if isinstance(res, Resolved) else None
        q = query.strip().lower()
        for line in self.lines:
            if target_id and line.dish.id == target_id:
                return line
            if q and (q in line.dish.name.lower() or q in line.dish.voice_line.lower()):
                return line
        return None

    @staticmethod
    def _match_choice(choice: str, options: tuple[Dish, ...]) -> Dish | None:
        c = choice.strip().lower()
        for d in options:
            if c == d.name.lower() or c == d.voice_line.lower():
                return d
        for d in options:
            if c and (c in d.name.lower() or d.name.lower() in c):
                return d
        return None

    def subtotal(self) -> float:
        return sum(l.total for l in self.lines)

    def total(self) -> float:
        extra = self.delivery_charge if self.order_type == "delivery" else 0.0
        return self.subtotal() + extra

    def order_summary(self) -> dict:
        return {
            "items": [
                {"dish": l.dish.voice_line, "quantity": l.quantity, "note": l.note}
                for l in self.lines
            ],
            "order_type": self.order_type,
            "name": self.name,
            "total": round(self.total(), 2),
        }
