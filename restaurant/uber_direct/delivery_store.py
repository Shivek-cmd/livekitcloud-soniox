"""Persist Uber Direct delivery status from webhooks (PR 093 P5)."""

from __future__ import annotations

import json
import logging
import os
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("uber-direct-delivery-store")

_lock = threading.Lock()


def _store_path() -> Path:
    return Path(
        os.getenv(
            "UBER_DIRECT_DELIVERY_STORE_PATH", "data/store_uber_deliveries.json"
        )
    )


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_time(raw: str | None) -> datetime | None:
    text = (raw or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        value = datetime.fromisoformat(text)
    except ValueError:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value


def _load(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"deliveries": {}, "orders": {}, "events": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        logger.exception("Corrupt Uber delivery store at %s — starting empty", path)
        return {"deliveries": {}, "orders": {}, "events": {}}
    if not isinstance(data, dict):
        return {"deliveries": {}, "orders": {}, "events": {}}
    if not isinstance(data.get("deliveries"), dict):
        data["deliveries"] = {}
    if not isinstance(data.get("orders"), dict):
        data["orders"] = {}
    if not isinstance(data.get("events"), dict):
        data["events"] = {}
    return data


def _save(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def claim_order_dispatch(
    *,
    order_key: str,
    quote_id: str,
    checkout_key: str | None = None,
    session_id: str | None = None,
    stale_after_seconds: int = 120,
) -> dict[str, Any]:
    """Atomically claim one Uber Create Delivery attempt for an order.

    A fresh claim returns ``action=claimed``. Completed, active, and failed
    claims are replayed without another Uber POST. A claim left in ``creating``
    beyond the stale window becomes ``dispatch_required`` because the remote
    outcome is unknown and Uber cannot safely be retried without a delivery id.
    """
    key = (order_key or "").strip()
    qid = (quote_id or "").strip()
    if not key or not qid:
        return {"action": "invalid", "state": "dispatch_required"}

    path = _store_path()
    with _lock:
        data = _load(path)
        orders: dict[str, Any] = data.setdefault("orders", {})
        prev = orders.get(key)
        if isinstance(prev, dict):
            record = dict(prev)
            state = str(record.get("state") or "")
            if state == "dispatched":
                return {"action": "dispatched", **record}
            if state == "dispatch_required":
                return {"action": "dispatch_required", **record}
            if state == "creating":
                started = _parse_time(record.get("attempt_started_at"))
                cutoff = datetime.now(timezone.utc) - timedelta(
                    seconds=max(1, stale_after_seconds)
                )
                if started is not None and started >= cutoff:
                    return {"action": "in_progress", **record}
                record.update(
                    {
                        "state": "dispatch_required",
                        "reason": "dispatch_outcome_unknown",
                        "uncertain_outcome": True,
                        "dispatch_required_at": _now(),
                        "updated_at": _now(),
                    }
                )
                orders[key] = record
                _save(path, data)
                return {"action": "dispatch_required", **record}

        now = _now()
        record = {
            "order_key": key,
            "quote_id": qid,
            "checkout_key": (checkout_key or "").strip() or None,
            "session_id": (session_id or "").strip() or None,
            "state": "creating",
            "attempts": int(prev.get("attempts") or 0) + 1
            if isinstance(prev, dict)
            else 1,
            "attempt_started_at": now,
            "created_at": prev.get("created_at") or now
            if isinstance(prev, dict)
            else now,
            "updated_at": now,
        }
        orders[key] = record
        _save(path, data)
        return {"action": "claimed", **record}


def mark_dispatch_success(
    *,
    order_key: str,
    delivery_id: str,
    status: str | None = None,
    tracking_url: str | None = None,
    notification_context: dict[str, Any] | None = None,
    raw: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    key = (order_key or "").strip()
    did = (delivery_id or "").strip()
    if not key or not did:
        return None
    path = _store_path()
    with _lock:
        data = _load(path)
        orders: dict[str, Any] = data.setdefault("orders", {})
        prev = orders.get(key) if isinstance(orders.get(key), dict) else {}
        now = _now()
        order_record = {
            **prev,
            "order_key": key,
            "delivery_id": did,
            "state": "dispatched",
            "status": status or prev.get("status") or "pending",
            "tracking_url": tracking_url or prev.get("tracking_url"),
            "dispatched_at": prev.get("dispatched_at") or now,
            "reason": None,
            "uncertain_outcome": False,
            "updated_at": now,
        }
        if notification_context is not None:
            order_record["notification_context"] = dict(notification_context)
        if raw is not None:
            order_record["create_raw"] = raw
        orders[key] = order_record

        deliveries: dict[str, Any] = data.setdefault("deliveries", {})
        delivery_record = (
            deliveries.get(did) if isinstance(deliveries.get(did), dict) else {}
        )
        deliveries[did] = {
            **delivery_record,
            "delivery_id": did,
            "order_key": key,
            "status": status or delivery_record.get("status") or "pending",
            "tracking_url": tracking_url or delivery_record.get("tracking_url"),
            "created_at": delivery_record.get("created_at") or now,
            "updated_at": now,
        }
        if notification_context is not None:
            deliveries[did]["notification_context"] = dict(notification_context)
        if raw is not None:
            deliveries[did]["create_raw"] = raw
        _save(path, data)
        return dict(order_record)


def mark_dispatch_required(
    *,
    order_key: str,
    reason: str,
    uncertain_outcome: bool = False,
) -> dict[str, Any] | None:
    key = (order_key or "").strip()
    if not key:
        return None
    path = _store_path()
    with _lock:
        data = _load(path)
        orders: dict[str, Any] = data.setdefault("orders", {})
        prev = orders.get(key) if isinstance(orders.get(key), dict) else {}
        now = _now()
        record = {
            **prev,
            "order_key": key,
            "state": "dispatch_required",
            "reason": (reason or "unknown")[:500],
            "uncertain_outcome": bool(uncertain_outcome),
            "dispatch_required_at": prev.get("dispatch_required_at") or now,
            "updated_at": now,
        }
        orders[key] = record
        _save(path, data)
        return dict(record)


def get_order_dispatch(order_key: str) -> dict[str, Any] | None:
    key = (order_key or "").strip()
    if not key:
        return None
    with _lock:
        data = _load(_store_path())
        rec = data.get("orders", {}).get(key)
        return dict(rec) if isinstance(rec, dict) else None


_STATUS_RANK = {
    "pending": 0,
    "pickup": 1,
    "shopping_completed": 2,
    "pickup_complete": 3,
    "dropoff": 4,
    "delivered": 5,
    "canceled": 5,
    "failed": 5,
    "returned": 6,
}
_TERMINAL_STATUSES = {"delivered", "canceled", "failed", "returned"}


def _customer_milestone(
    *, previous_status: str | None, status: str
) -> str | None:
    """Choose one customer/staff milestone for an accepted status transition."""
    if status == "pickup_complete":
        return "on_the_way"
    if status == "dropoff" and previous_status != "pickup_complete":
        return "on_the_way"
    if status == "delivered":
        return "delivered"
    if status in {"canceled", "failed", "returned"}:
        return "staff_alert"
    return None


def _is_stale_transition(
    *,
    previous_status: str | None,
    previous_event_time_ms: int | None,
    status: str,
    event_time_ms: int,
) -> str | None:
    if previous_event_time_ms is not None and event_time_ms < previous_event_time_ms:
        return "older_event_time"
    if previous_status in _TERMINAL_STATUSES:
        if previous_status == "canceled" and status == "returned":
            return None
        if status != previous_status:
            return "terminal_state"
    previous_rank = _STATUS_RANK.get(previous_status or "")
    next_rank = _STATUS_RANK.get(status)
    if (
        previous_rank is not None
        and next_rank is not None
        and next_rank < previous_rank
    ):
        return "status_regression"
    return None


def apply_delivery_webhook_event(
    *,
    event_id: str,
    event_time_ms: int,
    delivery_id: str,
    status: str,
    shape: str,
    tracking_url: str | None = None,
    external_id: str | None = None,
    cancellation_reason: str | None = None,
    undeliverable_reason: str | None = None,
    undeliverable_action: str | None = None,
    resource_href: str | None = None,
    related_deliveries: list[Any] | None = None,
    raw: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Apply one authenticated event exactly once and without state regression."""
    eid = (event_id or "").strip()
    did = (delivery_id or "").strip()
    normalized_status = (status or "").strip().lower()
    if not eid or not did or normalized_status not in _STATUS_RANK:
        return {"action": "invalid", "accepted": False}

    path = _store_path()
    with _lock:
        data = _load(path)
        events: dict[str, Any] = data.setdefault("events", {})
        existing_event = events.get(eid)
        if isinstance(existing_event, dict):
            delivery = data.get("deliveries", {}).get(did)
            return {
                "action": "duplicate",
                "accepted": False,
                "event": dict(existing_event),
                "delivery": (
                    dict(delivery) if isinstance(delivery, dict) else None
                ),
            }

        deliveries: dict[str, Any] = data.setdefault("deliveries", {})
        previous = (
            dict(deliveries[did]) if isinstance(deliveries.get(did), dict) else {}
        )
        previous_time_raw = previous.get("last_event_time_ms")
        try:
            previous_time = (
                int(previous_time_raw) if previous_time_raw is not None else None
            )
        except (TypeError, ValueError):
            previous_time = None
        ignored_reason = _is_stale_transition(
            previous_status=(
                str(previous.get("status")).lower()
                if previous.get("status")
                else None
            ),
            previous_event_time_ms=previous_time,
            status=normalized_status,
            event_time_ms=int(event_time_ms),
        )
        now = _now()
        previous_status = (
            str(previous.get("status")).lower()
            if previous.get("status")
            else None
        )
        event_record = {
            "event_id": eid,
            "delivery_id": did,
            "status": normalized_status,
            "previous_status": previous_status,
            "event_time_ms": int(event_time_ms),
            "shape": shape,
            "accepted": ignored_reason is None,
            "ignored_reason": ignored_reason,
            "customer_milestone": (
                _customer_milestone(
                    previous_status=previous_status,
                    status=normalized_status,
                )
                if ignored_reason is None
                else None
            ),
            "received_at": now,
        }
        events[eid] = event_record

        if ignored_reason is not None:
            _save(path, data)
            return {
                "action": "stale",
                "accepted": False,
                "reason": ignored_reason,
                "event": dict(event_record),
                "delivery": previous or None,
            }

        record = {
            **previous,
            "delivery_id": did,
            "status": normalized_status,
            "last_event_id": eid,
            "last_event_time_ms": int(event_time_ms),
            "last_webhook_shape": shape,
            "updated_at": now,
        }
        if tracking_url:
            record["tracking_url"] = tracking_url
        if external_id:
            record["external_id"] = external_id
            record.setdefault("order_key", external_id)
        if cancellation_reason:
            record["cancellation_reason"] = cancellation_reason
        if undeliverable_reason:
            record["undeliverable_reason"] = undeliverable_reason
        if undeliverable_action:
            record["undeliverable_action"] = undeliverable_action
        if resource_href:
            record["resource_href"] = resource_href
        if related_deliveries is not None:
            record["related_deliveries"] = related_deliveries
        if raw is not None:
            record["last_raw"] = raw
        deliveries[did] = record

        order_key = str(record.get("order_key") or external_id or "").strip()
        if order_key:
            orders: dict[str, Any] = data.setdefault("orders", {})
            order_previous = (
                dict(orders[order_key])
                if isinstance(orders.get(order_key), dict)
                else {}
            )
            orders[order_key] = {
                **order_previous,
                "order_key": order_key,
                "delivery_id": did,
                "state": "dispatched",
                "status": normalized_status,
                "tracking_url": record.get("tracking_url"),
                "last_event_id": eid,
                "last_event_time_ms": int(event_time_ms),
                "updated_at": now,
            }

        _save(path, data)
        return {
            "action": "applied",
            "accepted": True,
            "event": dict(event_record),
            "delivery": dict(record),
        }


def mark_delivery_event_notification(
    *,
    event_id: str,
    notified: bool,
    error: str | None = None,
) -> dict[str, Any] | None:
    """Persist n8n delivery status relay evidence for retry-safe webhooks."""
    eid = (event_id or "").strip()
    if not eid:
        return None
    path = _store_path()
    with _lock:
        data = _load(path)
        events: dict[str, Any] = data.setdefault("events", {})
        current = events.get(eid)
        if not isinstance(current, dict):
            return None
        record = dict(current)
        record["n8n_notify_attempts"] = int(
            record.get("n8n_notify_attempts") or 0
        ) + 1
        record["n8n_last_attempt_at"] = _now()
        if notified:
            record["n8n_notified_at"] = _now()
            record["n8n_last_error"] = None
        else:
            record["n8n_last_error"] = (error or "n8n_notify_failed")[:500]
        events[eid] = record
        _save(path, data)
        return dict(record)


def record_delivery_status(
    *,
    delivery_id: str,
    status: str | None = None,
    tracking_url: str | None = None,
    raw: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    did = (delivery_id or "").strip()
    if not did:
        return None
    path = _store_path()
    with _lock:
        data = _load(path)
        prev = data["deliveries"].get(did)
        if not isinstance(prev, dict):
            prev = {"delivery_id": did}
        if status:
            prev["status"] = status
        if tracking_url:
            prev["tracking_url"] = tracking_url
        if raw is not None:
            prev["last_raw"] = raw
        prev["updated_at"] = _now()
        data["deliveries"][did] = prev
        _save(path, data)
        return prev


def get_delivery(delivery_id: str) -> dict[str, Any] | None:
    did = (delivery_id or "").strip()
    if not did:
        return None
    path = _store_path()
    with _lock:
        data = _load(path)
        rec = data["deliveries"].get(did)
    return rec if isinstance(rec, dict) else None


def get_delivery_event(event_id: str) -> dict[str, Any] | None:
    eid = (event_id or "").strip()
    if not eid:
        return None
    path = _store_path()
    with _lock:
        data = _load(path)
        rec = data["events"].get(eid)
    return dict(rec) if isinstance(rec, dict) else None
