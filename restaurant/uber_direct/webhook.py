"""Parse Uber Direct delivery status webhook payloads (best-effort)."""

from __future__ import annotations

from typing import Any


def parse_uber_delivery_webhook(payload: dict[str, Any]) -> dict[str, Any]:
    """Extract delivery_id / status / tracking_url from common Uber shapes."""
    data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    if not isinstance(data, dict):
        data = {}

    meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}

    delivery_id = (
        data.get("id")
        or data.get("delivery_id")
        or payload.get("delivery_id")
        or meta.get("order_id")
    )
    status = data.get("status") or payload.get("status") or meta.get("status")
    tracking_url = data.get("tracking_url") or payload.get("tracking_url")

    return {
        "delivery_id": str(delivery_id).strip() if delivery_id else None,
        "status": str(status).strip() if status else None,
        "tracking_url": str(tracking_url).strip() if tracking_url else None,
    }
