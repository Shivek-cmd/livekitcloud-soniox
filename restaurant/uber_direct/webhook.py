"""Authenticate and parse supported Uber Direct delivery webhooks."""

from __future__ import annotations

import hashlib
import hmac
from datetime import datetime, timezone
from typing import Any


_STATUS_ALIASES = {
    "scheduled": "pending",
    "en_route_to_pickup": "pickup",
    "arrived_at_pickup": "pickup",
    "en_route_to_dropoff": "dropoff",
    "arrived_at_dropoff": "dropoff",
    "completed": "delivered",
}

SUPPORTED_STATUSES = {
    "pending",
    "pickup",
    "shopping_completed",
    "pickup_complete",
    "dropoff",
    "delivered",
    "canceled",
    "failed",
    "returned",
}


def verify_uber_webhook_signature(
    raw_body: bytes,
    *,
    secret: str,
    uber_signature: str | None = None,
    postmates_signature: str | None = None,
) -> bool:
    """Verify Uber's hexadecimal HMAC-SHA256 signature over exact body bytes."""
    signing_key = (secret or "").strip()
    if not signing_key:
        return False
    expected = hmac.new(
        signing_key.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()
    for candidate in (uber_signature, postmates_signature):
        supplied = (candidate or "").strip().lower()
        if supplied.startswith("sha256="):
            supplied = supplied[7:]
        if len(supplied) == 64 and hmac.compare_digest(expected, supplied):
            return True
    return False


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _event_time_ms(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = float(value)
        if number <= 0:
            return None
        # Legacy payloads document milliseconds, but tolerate Unix seconds.
        return int(number * 1000) if number < 10_000_000_000 else int(number)
    text = _text(value)
    if not text:
        return None
    normalized = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return int(parsed.timestamp() * 1000)


def _status(value: Any) -> str | None:
    normalized = (_text(value) or "").lower()
    normalized = _STATUS_ALIASES.get(normalized, normalized)
    return normalized if normalized in SUPPORTED_STATUSES else None


def _cancellation_reason(data: dict[str, Any]) -> str | None:
    raw = data.get("cancelation_reason")
    if not isinstance(raw, dict):
        raw = data.get("cancellation_reason")
    if isinstance(raw, dict):
        secondary = _text(raw.get("secondary_reason"))
        primary = _text(raw.get("primary_reason"))
        return secondary or primary
    return _text(raw)


def _invalid(reason: str, *, shape: str | None = None) -> dict[str, Any]:
    return {
        "valid": False,
        "error": reason,
        "shape": shape,
        "event_id": None,
        "delivery_id": None,
        "status": None,
    }


def parse_uber_delivery_webhook(payload: dict[str, Any]) -> dict[str, Any]:
    """Parse the modern DaaS or legacy DAPI delivery-status event shape."""
    if not isinstance(payload, dict):
        return _invalid("expected_object")

    kind = _text(payload.get("kind"))
    event_type = _text(payload.get("event_type"))

    if kind == "event.delivery_status":
        data = payload.get("data")
        if not isinstance(data, dict):
            return _invalid("missing_data", shape="event.delivery_status")
        event_id = _text(payload.get("id"))
        delivery_id = _text(
            payload.get("delivery_id") or data.get("id")
        )
        status = _status(payload.get("status") or data.get("status"))
        event_time_ms = _event_time_ms(
            payload.get("created") or data.get("updated") or data.get("created")
        )
        if not event_id:
            return _invalid("missing_event_id", shape="event.delivery_status")
        if not delivery_id:
            return _invalid("missing_delivery_id", shape="event.delivery_status")
        if not status:
            return _invalid("missing_or_unknown_status", shape="event.delivery_status")
        if event_time_ms is None:
            return _invalid("missing_or_invalid_event_time", shape="event.delivery_status")
        return {
            "valid": True,
            "shape": "event.delivery_status",
            "event_id": event_id,
            "event_time_ms": event_time_ms,
            "delivery_id": delivery_id,
            "status": status,
            "tracking_url": _text(
                data.get("tracking_url") or payload.get("tracking_url")
            ),
            "external_id": _text(data.get("external_id")),
            "cancellation_reason": _cancellation_reason(data),
            "undeliverable_reason": _text(data.get("undeliverable_reason")),
            "undeliverable_action": _text(data.get("undeliverable_action")),
            "resource_href": None,
            "related_deliveries": (
                data.get("related_deliveries")
                if isinstance(data.get("related_deliveries"), list)
                else None
            ),
        }

    if event_type == "dapi.status_changed":
        meta = payload.get("meta")
        if not isinstance(meta, dict):
            return _invalid("missing_meta", shape="dapi.status_changed")
        event_id = _text(payload.get("event_id"))
        delivery_id = _text(meta.get("order_id"))
        status = _status(meta.get("status"))
        event_time_ms = _event_time_ms(payload.get("event_time"))
        if not event_id:
            return _invalid("missing_event_id", shape="dapi.status_changed")
        if not delivery_id:
            return _invalid("missing_delivery_id", shape="dapi.status_changed")
        if not status:
            return _invalid("missing_or_unknown_status", shape="dapi.status_changed")
        if event_time_ms is None:
            return _invalid("missing_or_invalid_event_time", shape="dapi.status_changed")
        return {
            "valid": True,
            "shape": "dapi.status_changed",
            "event_id": event_id,
            "event_time_ms": event_time_ms,
            "delivery_id": delivery_id,
            "status": status,
            "tracking_url": None,
            "external_id": _text(meta.get("external_order_id")),
            "cancellation_reason": None,
            "undeliverable_reason": None,
            "undeliverable_action": None,
            "resource_href": _text(payload.get("resource_href")),
            "related_deliveries": (
                meta.get("related_deliveries")
                if isinstance(meta.get("related_deliveries"), list)
                else None
            ),
        }

    return _invalid("unsupported_event_shape", shape=kind or event_type)


def enrich_parsed_delivery(
    parsed: dict[str, Any],
    resource: dict[str, Any],
) -> dict[str, Any]:
    """Fill reconciliation fields from a trusted Uber Get Delivery response."""
    enriched = dict(parsed)
    if not isinstance(resource, dict):
        return enriched
    data = (
        resource.get("data")
        if isinstance(resource.get("data"), dict)
        else resource
    )
    enriched["tracking_url"] = (
        _text(enriched.get("tracking_url"))
        or _text(data.get("tracking_url"))
        or _text(data.get("order_tracking_url"))
    )
    enriched["external_id"] = (
        _text(enriched.get("external_id"))
        or _text(data.get("external_id"))
        or _text(data.get("external_order_id"))
    )
    enriched["cancellation_reason"] = (
        _text(enriched.get("cancellation_reason"))
        or _cancellation_reason(data)
    )
    enriched["undeliverable_reason"] = (
        _text(enriched.get("undeliverable_reason"))
        or _text(data.get("undeliverable_reason"))
    )
    enriched["undeliverable_action"] = (
        _text(enriched.get("undeliverable_action"))
        or _text(data.get("undeliverable_action"))
    )
    if (
        enriched.get("related_deliveries") is None
        and isinstance(data.get("related_deliveries"), list)
    ):
        enriched["related_deliveries"] = data["related_deliveries"]
    return enriched
