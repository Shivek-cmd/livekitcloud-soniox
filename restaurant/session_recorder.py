"""In-memory call session recorder — flushed to Supabase or local JSON on hangup."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


@dataclass
class TurnRecord:
    turn_number: int
    user_stt: str | None = None
    stt_language: str | None = None
    sierra_spoken: str | None = None
    intent: str | None = None
    phase: str | None = None
    was_filtered: bool = False
    filter_reason: str | None = None
    auto_add: bool = False
    tools_called: list[dict[str, Any]] = field(default_factory=list)
    cart_snapshot: dict | None = None
    latency: dict | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "turn_number": self.turn_number,
            "user_stt": self.user_stt,
            "stt_language": self.stt_language,
            "sierra_spoken": self.sierra_spoken,
            "intent": self.intent,
            "phase": self.phase,
            "was_filtered": self.was_filtered,
            "filter_reason": self.filter_reason,
            "auto_add": self.auto_add,
            "tools_called": self.tools_called,
            "cart_snapshot": self.cart_snapshot,
            "latency": self.latency,
        }


@dataclass
class EventRecord:
    event_type: str
    payload: dict[str, Any] = field(default_factory=dict)
    at: datetime = field(default_factory=_utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type,
            "payload": self.payload,
            "created_at": _iso(self.at),
        }


@dataclass
class SessionRecorder:
    """Buffers one call for analytics export."""

    tenant_id: str = "bizbull"
    room_name: str = ""
    channel: str = "web"
    participant_identity: str | None = None
    caller_phone: str | None = None
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    started_at: datetime = field(default_factory=_utcnow)
    ended_at: datetime | None = None

    turns: list[TurnRecord] = field(default_factory=list)
    events: list[EventRecord] = field(default_factory=list)

    outcome: str | None = None
    transfer_reason: str | None = None
    echo_filter_count: int = 0
    background_filter_count: int = 0

    _current: TurnRecord | None = field(default=None, repr=False)
    _latencies_ms: list[int] = field(default_factory=list, repr=False)

    def start(
        self,
        *,
        room_name: str,
        channel: str,
        participant_identity: str | None = None,
        caller_phone: str | None = None,
    ) -> None:
        self.room_name = room_name
        self.channel = channel
        self.participant_identity = participant_identity
        if caller_phone:
            self.caller_phone = caller_phone
        self.add_event("session_started", {
            "room_name": room_name,
            "channel": channel,
            "participant_identity": participant_identity,
        })

    def add_event(self, event_type: str, payload: dict | None = None) -> None:
        self.events.append(EventRecord(event_type, payload or {}))

    def begin_user_turn(self, user_stt: str, *, stt_language: str | None = None) -> TurnRecord:
        turn = TurnRecord(
            turn_number=len(self.turns) + 1,
            user_stt=user_stt.strip() or None,
            stt_language=stt_language,
        )
        self.turns.append(turn)
        self._current = turn
        return turn

    @property
    def current_turn(self) -> TurnRecord | None:
        return self._current

    def mark_filtered(self, reason: str) -> None:
        turn = self._current
        if turn is None:
            turn = self.begin_user_turn("")
        turn.was_filtered = True
        turn.filter_reason = reason
        if reason == "echo":
            self.echo_filter_count += 1
        elif reason == "background":
            self.background_filter_count += 1

    def complete_turn(
        self,
        *,
        intent: str | None = None,
        phase: str | None = None,
        auto_add: bool = False,
        cart_snapshot: dict | None = None,
    ) -> None:
        turn = self._current
        if turn is None:
            return
        if intent is not None:
            turn.intent = intent
        if phase is not None:
            turn.phase = phase
        turn.auto_add = auto_add
        if cart_snapshot is not None:
            turn.cart_snapshot = cart_snapshot

    def append_sierra(self, text: str) -> None:
        line = text.strip()
        if not line:
            return
        turn = self._current
        if turn is None:
            turn = TurnRecord(turn_number=len(self.turns) + 1)
            self.turns.append(turn)
            self._current = turn
        if turn.sierra_spoken:
            turn.sierra_spoken = f"{turn.sierra_spoken}\n{line}"
        else:
            turn.sierra_spoken = line

    def log_tool(self, name: str, args: dict, result: str) -> None:
        turn = self._current
        if turn is None:
            turn = TurnRecord(turn_number=len(self.turns) + 1)
            self.turns.append(turn)
            self._current = turn
        snippet = (result or "")[:500]
        turn.tools_called.append({"name": name, "args": args, "result": snippet})

    def attach_latency(self, latency: dict) -> None:
        turn = self._current
        if turn is None:
            return
        turn.latency = latency
        ms = latency.get("user_stop_to_speaking_ms")
        if isinstance(ms, int) and ms >= 0:
            self._latencies_ms.append(ms)

    def set_outcome(self, outcome: str) -> None:
        self.outcome = outcome

    def set_transfer(self, reason: str) -> None:
        self.transfer_reason = reason
        self.outcome = "transfer"
        self.add_event("transfer_requested", {"reason": reason})

    def finalize(self, cart, flow) -> dict[str, Any]:
        """Build export payload from cart + order flow controller."""
        self.ended_at = _utcnow()
        duration = int((self.ended_at - self.started_at).total_seconds())

        if self.outcome is None:
            if cart.placed:
                self.outcome = "placed"
            elif cart.is_empty and not any(
                e.event_type == "reservation_booked" for e in self.events
            ):
                self.outcome = "empty"
            elif not cart.is_empty:
                self.outcome = "abandoned"
            else:
                self.outcome = "empty"

        if any(e.event_type == "reservation_booked" for e in self.events):
            self.outcome = "reservation"

        final_cart = cart.to_state_dict()
        avg_lat = None
        p95_lat = None
        if self._latencies_ms:
            avg_lat = int(sum(self._latencies_ms) / len(self._latencies_ms))
            sorted_lat = sorted(self._latencies_ms)
            p95_lat = sorted_lat[int(len(sorted_lat) * 0.95) - 1]

        session_row = {
            "id": self.session_id,
            "tenant_id": self.tenant_id,
            "room_name": self.room_name,
            "channel": self.channel,
            "participant_identity": self.participant_identity,
            "caller_phone": self.caller_phone or cart.customer_phone,
            "started_at": _iso(self.started_at),
            "ended_at": _iso(self.ended_at),
            "duration_seconds": duration,
            "outcome": self.outcome,
            "turn_count": len(self.turns),
            "preferred_language": getattr(
                flow.state.preferred_language, "value", str(flow.state.preferred_language)
            ),
            "customer_name": cart.customer_name,
            "customer_phone": cart.customer_phone,
            "order_type": cart.order_type,
            "delivery_address": cart.delivery_address,
            "final_cart": final_cart,
            "order_total": float(cart.total) if cart.items else None,
            "items_count": len(cart.items),
            "transfer_reason": self.transfer_reason,
            "echo_filter_count": self.echo_filter_count,
            "background_filter_count": self.background_filter_count,
            "avg_latency_ms": avg_lat,
            "p95_latency_ms": p95_lat,
            "tags": self.tags,
            "metadata": self.metadata,
        }

        order_row = None
        if cart.placed and cart.items:
            order_row = {
                "session_id": self.session_id,
                "tenant_id": self.tenant_id,
                "channel": self.channel,
                "placed_at": _iso(self.ended_at),
                "status": "logged",
                "order_type": cart.order_type,
                "items": final_cart.get("items", []),
                "subtotal": float(cart.subtotal),
                "delivery_charge": float(cart.delivery_charge)
                if cart.order_type == "delivery"
                else 0,
                "total": float(cart.total),
                "customer_name": cart.customer_name,
                "customer_phone": cart.customer_phone,
                "delivery_address": cart.delivery_address,
            }

        return {
            "session": session_row,
            "turns": [t.to_dict() for t in self.turns],
            "events": [e.to_dict() for e in self.events],
            "order": order_row,
        }
