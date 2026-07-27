"""Fire-and-forget order events to self-hosted n8n (GHL CRM sync).

Phase G1 — see docs/plan/13-ghl-n8n-order-sync.md.
Fail-open: never raise into the voice agent hot path.
"""

from __future__ import annotations

import json
import logging
import os
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

logger = logging.getLogger("n8n-webhook")

_DEFAULT_TIMEOUT_SEC = 3.0
_TENANT_ID = "bizbull"


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name, "").strip().lower()
    if not raw:
        return default
    return raw in ("1", "true", "yes", "on")


def n8n_sync_enabled() -> bool:
    """Kill switch — default off until VPS explicitly enables."""
    return _env_bool("N8N_SYNC_ENABLED", False)


def n8n_webhook_url() -> str | None:
    url = (os.getenv("N8N_WEBHOOK_ORDERS_URL") or "").strip()
    return url or None


def n8n_webhook_secret() -> str | None:
    secret = (os.getenv("N8N_WEBHOOK_SECRET") or "").strip()
    return secret or None


def n8n_timeout_seconds() -> float:
    raw = (os.getenv("N8N_WEBHOOK_TIMEOUT_SEC") or "").strip()
    if not raw:
        return _DEFAULT_TIMEOUT_SEC
    try:
        return max(0.5, float(raw))
    except ValueError:
        return _DEFAULT_TIMEOUT_SEC


def phone_to_e164(raw: str | None, *, default_region: str = "1") -> str:
    """Best-effort E.164 for GHL upsert. Bizbull default region = NANP (+1)."""
    digits = re.sub(r"\D", "", raw or "")
    if not digits:
        return ""
    if digits.startswith("1") and len(digits) == 11:
        return f"+{digits}"
    if len(digits) == 10:
        return f"+{default_region}{digits}"
    if digits.startswith("91") and len(digits) >= 12:
        return f"+{digits}"
    return f"+{digits}"


def build_order_placed_envelope(
    *,
    channel: str,
    customer_name: str | None,
    customer_phone: str | None,
    order_type: str | None,
    items: list[dict[str, Any]],
    subtotal: float | None = None,
    total: float | None = None,
    address: str | None = None,
    allergy_note: str | None = None,
    clover_order_id: str | None = None,
    clover_submitted: bool = False,
    session_id: str | None = None,
    eta: str | None = None,
    event_id: str | None = None,
    language: str | None = None,
    delivery_fulfillment_status: str | None = None,
    delivery_dispatch_reason: str | None = None,
) -> dict[str, Any]:
    """Normalized payload matching n8n G0 / plan §6."""
    phone_raw = (customer_phone or "").strip()
    phone_e164 = phone_to_e164(phone_raw)
    eid = event_id or clover_order_id or session_id or str(uuid4())
    return {
        "schema_version": 1,
        "event": "order.placed",
        "event_id": eid,
        "occurred_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "tenant_id": _TENANT_ID,
        "channel": channel or "phone",
        "session_id": session_id,
        "customer": {
            "name": (customer_name or "").strip() or None,
            "phone_e164": phone_e164 or None,
            "phone_raw": phone_raw or None,
        },
        "order": {
            "clover_order_id": clover_order_id,
            "clover_submitted": bool(clover_submitted),
            "order_type": order_type,
            "status": "placed",
            "items": items,
            "subtotal": subtotal,
            "total": total,
            "address": address,
            "allergy_note": allergy_note,
            "eta": eta,
            "delivery_fulfillment_status": delivery_fulfillment_status,
            "delivery_dispatch_reason": delivery_dispatch_reason,
        },
        "meta": {
            "source": "sierra",
            "language": getattr(language, "value", language) if language is not None else None,
            "sms_hint": (
                "Kitchen accepted the order, but no courier is confirmed yet."
                if delivery_fulfillment_status == "dispatch_required"
                else None
            ),
        },
    }


def build_order_paid_envelope(
    *,
    channel: str,
    customer_name: str | None,
    customer_phone: str | None,
    order_type: str | None = None,
    clover_order_id: str | None = None,
    payment_id: str | None = None,
    receipt_url: str | None = None,
    checkout_session_id: str | None = None,
    total: float | None = None,
    session_id: str | None = None,
    event_id: str | None = None,
) -> dict[str, Any]:
    """Normalized order.paid envelope for receipt SMS (PR 090 P4)."""
    phone_raw = (customer_phone or "").strip()
    phone_e164 = phone_to_e164(phone_raw)
    eid = (
        event_id
        or (f"order.paid:{payment_id}" if payment_id else None)
        or (f"order.paid:session:{checkout_session_id}" if checkout_session_id else None)
        or str(uuid4())
    )
    return {
        "schema_version": 1,
        "event": "order.paid",
        "event_id": eid,
        "occurred_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "tenant_id": _TENANT_ID,
        "channel": channel or "web_store",
        "session_id": session_id,
        "customer": {
            "name": (customer_name or "").strip() or None,
            "phone_e164": phone_e164 or None,
            "phone_raw": phone_raw or None,
        },
        "order": {
            "clover_order_id": clover_order_id,
            "order_type": order_type,
            "status": "paid",
            "total": total,
            "payment_id": payment_id,
            "receipt_url": receipt_url,
            "checkout_session_id": checkout_session_id,
        },
        "meta": {
            "source": "sierra",
            "sms_hint": (
                "Send receipt SMS with receipt_url. Do not re-send order-placed confirm."
            ),
        },
    }


def _post_json_sync(url: str, payload: dict[str, Any], *, secret: str | None, timeout: float) -> int:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "sierra-bizbull-n8n/1.0",
    }
    if secret:
        headers["X-Webhook-Secret"] = secret
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return int(getattr(resp, "status", 200) or 200)


async def notify_order_placed(
    *,
    channel: str,
    customer_name: str | None,
    customer_phone: str | None,
    order_type: str | None,
    items: list[dict[str, Any]],
    subtotal: float | None = None,
    total: float | None = None,
    address: str | None = None,
    allergy_note: str | None = None,
    clover_order_id: str | None = None,
    clover_submitted: bool = False,
    session_id: str | None = None,
    eta: str | None = None,
    language: str | None = None,
    delivery_fulfillment_status: str | None = None,
    delivery_dispatch_reason: str | None = None,
) -> bool:
    """POST order.placed to n8n. Returns True on 2xx. Never raises."""
    import asyncio

    if not n8n_sync_enabled():
        return False
    url = n8n_webhook_url()
    if not url:
        logger.warning("N8N_SYNC_ENABLED but N8N_WEBHOOK_ORDERS_URL is empty — skip")
        return False

    envelope = build_order_placed_envelope(
        channel=channel,
        customer_name=customer_name,
        customer_phone=customer_phone,
        order_type=order_type,
        items=items,
        subtotal=subtotal,
        total=total,
        address=address,
        allergy_note=allergy_note,
        clover_order_id=clover_order_id,
        clover_submitted=clover_submitted,
        session_id=session_id,
        eta=eta,
        language=language,
        delivery_fulfillment_status=delivery_fulfillment_status,
        delivery_dispatch_reason=delivery_dispatch_reason,
    )
    timeout = n8n_timeout_seconds()
    secret = n8n_webhook_secret()
    try:
        status = await asyncio.to_thread(
            _post_json_sync, url, envelope, secret=secret, timeout=timeout
        )
        if 200 <= status < 300:
            logger.info(
                "N8N_ORDER_PLACED ok status=%s event_id=%s phone=%s",
                status,
                envelope.get("event_id"),
                (envelope.get("customer") or {}).get("phone_e164"),
            )
            return True
        logger.warning(
            "N8N_ORDER_PLACED unexpected status=%s event_id=%s",
            status,
            envelope.get("event_id"),
        )
        return False
    except urllib.error.HTTPError as e:
        logger.warning(
            "N8N_ORDER_PLACED http_error status=%s event_id=%s",
            e.code,
            envelope.get("event_id"),
        )
        return False
    except Exception:
        logger.exception(
            "N8N_ORDER_PLACED failed event_id=%s — continuing voice path",
            envelope.get("event_id"),
        )
        return False


async def notify_order_paid(
    *,
    channel: str,
    customer_name: str | None,
    customer_phone: str | None,
    order_type: str | None = None,
    clover_order_id: str | None = None,
    payment_id: str | None = None,
    receipt_url: str | None = None,
    checkout_session_id: str | None = None,
    total: float | None = None,
    session_id: str | None = None,
) -> bool:
    """POST order.paid to n8n (receipt SMS). Fail-open — never raises."""
    import asyncio

    if not n8n_sync_enabled():
        return False
    url = n8n_webhook_url()
    if not url:
        logger.warning("N8N_SYNC_ENABLED but N8N_WEBHOOK_ORDERS_URL is empty — skip paid")
        return False
    if not receipt_url:
        logger.warning("N8N_ORDER_PAID skip — missing receipt_url payment_id=%s", payment_id)
        return False
    if not phone_to_e164(customer_phone):
        logger.warning("N8N_ORDER_PAID skip — missing phone payment_id=%s", payment_id)
        return False

    envelope = build_order_paid_envelope(
        channel=channel,
        customer_name=customer_name,
        customer_phone=customer_phone,
        order_type=order_type,
        clover_order_id=clover_order_id,
        payment_id=payment_id,
        receipt_url=receipt_url,
        checkout_session_id=checkout_session_id,
        total=total,
        session_id=session_id,
    )
    timeout = n8n_timeout_seconds()
    secret = n8n_webhook_secret()
    try:
        status = await asyncio.to_thread(
            _post_json_sync, url, envelope, secret=secret, timeout=timeout
        )
        if 200 <= status < 300:
            logger.info(
                "N8N_ORDER_PAID ok status=%s event_id=%s phone=%s",
                status,
                envelope.get("event_id"),
                (envelope.get("customer") or {}).get("phone_e164"),
            )
            return True
        logger.warning(
            "N8N_ORDER_PAID unexpected status=%s event_id=%s",
            status,
            envelope.get("event_id"),
        )
        return False
    except urllib.error.HTTPError as e:
        logger.warning(
            "N8N_ORDER_PAID http_error status=%s event_id=%s",
            e.code,
            envelope.get("event_id"),
        )
        return False
    except Exception:
        logger.exception(
            "N8N_ORDER_PAID failed event_id=%s — continuing",
            envelope.get("event_id"),
        )
        return False


def build_delivery_dispatched_envelope(
    *,
    channel: str,
    customer_name: str | None,
    customer_phone: str | None,
    order_type: str | None = None,
    clover_order_id: str | None = None,
    delivery_id: str | None = None,
    tracking_url: str | None = None,
    total: float | None = None,
    session_id: str | None = None,
    event_id: str | None = None,
) -> dict[str, Any]:
    """Normalized delivery.dispatched envelope for tracking SMS (PR 093)."""
    phone_raw = (customer_phone or "").strip()
    phone_e164 = phone_to_e164(phone_raw)
    eid = (
        event_id
        or (f"delivery.dispatched:{delivery_id}" if delivery_id else None)
        or str(uuid4())
    )
    return {
        "schema_version": 1,
        "event": "delivery.dispatched",
        "event_id": eid,
        "occurred_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "tenant_id": _TENANT_ID,
        "channel": channel or "web_store",
        "session_id": session_id,
        "customer": {
            "name": (customer_name or "").strip() or None,
            "phone_e164": phone_e164 or None,
            "phone_raw": phone_raw or None,
        },
        "order": {
            "clover_order_id": clover_order_id,
            "order_type": order_type or "delivery",
            "status": "delivery_dispatched",
            "total": total,
            "uber_delivery_id": delivery_id,
            "tracking_url": tracking_url,
        },
    }


async def notify_delivery_dispatched(
    *,
    channel: str,
    customer_name: str | None,
    customer_phone: str | None,
    order_type: str | None = None,
    clover_order_id: str | None = None,
    delivery_id: str | None = None,
    tracking_url: str | None = None,
    total: float | None = None,
    session_id: str | None = None,
) -> bool:
    """POST delivery.dispatched to n8n (tracking SMS). Fail-open — never raises."""
    import asyncio

    if not n8n_sync_enabled():
        return False
    url = n8n_webhook_url()
    if not url:
        logger.warning(
            "N8N_SYNC_ENABLED but N8N_WEBHOOK_ORDERS_URL is empty — skip dispatch"
        )
        return False
    if not tracking_url:
        logger.warning(
            "N8N_DELIVERY_DISPATCHED skip — missing tracking_url delivery_id=%s",
            delivery_id,
        )
        return False
    if not phone_to_e164(customer_phone):
        logger.warning(
            "N8N_DELIVERY_DISPATCHED skip — missing phone delivery_id=%s",
            delivery_id,
        )
        return False

    envelope = build_delivery_dispatched_envelope(
        channel=channel,
        customer_name=customer_name,
        customer_phone=customer_phone,
        order_type=order_type,
        clover_order_id=clover_order_id,
        delivery_id=delivery_id,
        tracking_url=tracking_url,
        total=total,
        session_id=session_id,
    )
    timeout = n8n_timeout_seconds()
    secret = n8n_webhook_secret()
    try:
        status = await asyncio.to_thread(
            _post_json_sync, url, envelope, secret=secret, timeout=timeout
        )
        if 200 <= status < 300:
            logger.info(
                "N8N_DELIVERY_DISPATCHED ok status=%s event_id=%s",
                status,
                envelope.get("event_id"),
            )
            return True
        logger.warning(
            "N8N_DELIVERY_DISPATCHED unexpected status=%s event_id=%s",
            status,
            envelope.get("event_id"),
        )
        return False
    except Exception:
        logger.exception(
            "N8N_DELIVERY_DISPATCHED failed event_id=%s — continuing",
            envelope.get("event_id"),
        )
        return False


def build_delivery_status_changed_envelope(
    *,
    uber_event_id: str,
    event_time_ms: int,
    delivery_id: str,
    delivery_status: str,
    previous_status: str | None = None,
    customer_milestone: str | None = None,
    channel: str = "web_store",
    customer_name: str | None = None,
    customer_phone: str | None = None,
    clover_order_id: str | None = None,
    order_type: str | None = "delivery",
    tracking_url: str | None = None,
    total: float | None = None,
    session_id: str | None = None,
    cancellation_reason: str | None = None,
    undeliverable_reason: str | None = None,
    undeliverable_action: str | None = None,
    webhook_shape: str | None = None,
) -> dict[str, Any]:
    """Stable Sierra envelope for one accepted Uber lifecycle transition."""
    phone_raw = (customer_phone or "").strip()
    uber_eid = (uber_event_id or "").strip()
    occurred_at = datetime.fromtimestamp(
        int(event_time_ms) / 1000,
        tz=timezone.utc,
    ).strftime("%Y-%m-%dT%H:%M:%SZ")
    status = (delivery_status or "").strip().lower()
    return {
        "schema_version": 1,
        "event": "delivery.status_changed",
        "event_id": f"delivery.status:{uber_eid}",
        "occurred_at": occurred_at,
        "tenant_id": _TENANT_ID,
        "channel": channel or "web_store",
        "session_id": session_id,
        "customer": {
            "name": (customer_name or "").strip() or None,
            "phone_e164": phone_to_e164(phone_raw) or None,
            "phone_raw": phone_raw or None,
        },
        "order": {
            "clover_order_id": clover_order_id,
            "order_type": order_type or "delivery",
            "status": status,
            "total": total,
            "uber_delivery_id": delivery_id,
            "uber_event_id": uber_eid,
            "uber_event_time_ms": int(event_time_ms),
            "delivery_status": status,
            "previous_delivery_status": previous_status,
            "tracking_url": tracking_url,
            "cancellation_reason": cancellation_reason,
            "undeliverable_reason": undeliverable_reason,
            "undeliverable_action": undeliverable_action,
        },
        "meta": {
            "source": "uber_direct",
            "webhook_shape": webhook_shape,
            "customer_milestone": customer_milestone,
            "staff_alert_required": customer_milestone == "staff_alert",
        },
    }


async def notify_delivery_status_changed(
    *,
    uber_event_id: str,
    event_time_ms: int,
    delivery_id: str,
    delivery_status: str,
    previous_status: str | None = None,
    customer_milestone: str | None = None,
    channel: str = "web_store",
    customer_name: str | None = None,
    customer_phone: str | None = None,
    clover_order_id: str | None = None,
    order_type: str | None = "delivery",
    tracking_url: str | None = None,
    total: float | None = None,
    session_id: str | None = None,
    cancellation_reason: str | None = None,
    undeliverable_reason: str | None = None,
    undeliverable_action: str | None = None,
    webhook_shape: str | None = None,
) -> bool:
    """Relay an accepted Uber status to n8n. Fail-open for callers."""
    import asyncio

    if not n8n_sync_enabled():
        return False
    url = n8n_webhook_url()
    if not url:
        logger.warning(
            "N8N_SYNC_ENABLED but N8N_WEBHOOK_ORDERS_URL is empty — "
            "skip delivery status"
        )
        return False
    if not (uber_event_id and delivery_id and delivery_status):
        logger.warning("N8N_DELIVERY_STATUS skip — incomplete lifecycle identity")
        return False

    envelope = build_delivery_status_changed_envelope(
        uber_event_id=uber_event_id,
        event_time_ms=event_time_ms,
        delivery_id=delivery_id,
        delivery_status=delivery_status,
        previous_status=previous_status,
        customer_milestone=customer_milestone,
        channel=channel,
        customer_name=customer_name,
        customer_phone=customer_phone,
        clover_order_id=clover_order_id,
        order_type=order_type,
        tracking_url=tracking_url,
        total=total,
        session_id=session_id,
        cancellation_reason=cancellation_reason,
        undeliverable_reason=undeliverable_reason,
        undeliverable_action=undeliverable_action,
        webhook_shape=webhook_shape,
    )
    try:
        status = await asyncio.to_thread(
            _post_json_sync,
            url,
            envelope,
            secret=n8n_webhook_secret(),
            timeout=n8n_timeout_seconds(),
        )
        if 200 <= status < 300:
            logger.info(
                "N8N_DELIVERY_STATUS ok status=%s event_id=%s delivery=%s",
                status,
                envelope.get("event_id"),
                delivery_id,
            )
            return True
        logger.warning(
            "N8N_DELIVERY_STATUS unexpected status=%s event_id=%s",
            status,
            envelope.get("event_id"),
        )
        return False
    except Exception:
        logger.exception(
            "N8N_DELIVERY_STATUS failed event_id=%s — pending retry",
            envelope.get("event_id"),
        )
        return False


def build_delivery_dispatch_required_envelope(
    *,
    channel: str,
    customer_name: str | None,
    customer_phone: str | None,
    clover_order_id: str | None,
    order_key: str,
    reason: str,
    uncertain_outcome: bool = False,
    attempts: int = 0,
    total: float | None = None,
    address: str | None = None,
    session_id: str | None = None,
    event_id: str | None = None,
) -> dict[str, Any]:
    """Restaurant escalation after kitchen place but no confirmed courier."""
    phone_raw = (customer_phone or "").strip()
    stable_order = (clover_order_id or order_key or session_id or "").strip()
    eid = event_id or (
        f"delivery.dispatch_required:{stable_order}" if stable_order else str(uuid4())
    )
    return {
        "schema_version": 1,
        "event": "delivery.dispatch_required",
        "event_id": eid,
        "occurred_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "tenant_id": _TENANT_ID,
        "channel": channel or "web_store",
        "session_id": session_id,
        "customer": {
            "name": (customer_name or "").strip() or None,
            "phone_e164": phone_to_e164(phone_raw) or None,
            "phone_raw": phone_raw or None,
        },
        "order": {
            "clover_order_id": clover_order_id,
            "order_key": order_key,
            "order_type": "delivery",
            "status": "dispatch_required",
            "total": total,
            "delivery_address": address,
            "dispatch_reason": reason,
            "dispatch_attempts": int(attempts),
            "uncertain_outcome": bool(uncertain_outcome),
        },
        "meta": {
            "source": "sierra",
            "staff_action": (
                "Check Uber Direct before creating any courier manually. "
                "The prior Create Delivery outcome may be uncertain."
                if uncertain_outcome
                else "Arrange or retry courier fulfillment for this kitchen order."
            ),
        },
    }


async def notify_delivery_dispatch_required(
    *,
    channel: str,
    customer_name: str | None,
    customer_phone: str | None,
    clover_order_id: str | None,
    order_key: str,
    reason: str,
    uncertain_outcome: bool = False,
    attempts: int = 0,
    total: float | None = None,
    address: str | None = None,
    session_id: str | None = None,
) -> bool:
    """POST a staff escalation event. Fail-open and never raises."""
    import asyncio

    if not n8n_sync_enabled():
        return False
    url = n8n_webhook_url()
    if not url:
        logger.warning(
            "N8N_SYNC_ENABLED but N8N_WEBHOOK_ORDERS_URL is empty — "
            "skip dispatch-required alert"
        )
        return False
    envelope = build_delivery_dispatch_required_envelope(
        channel=channel,
        customer_name=customer_name,
        customer_phone=customer_phone,
        clover_order_id=clover_order_id,
        order_key=order_key,
        reason=reason,
        uncertain_outcome=uncertain_outcome,
        attempts=attempts,
        total=total,
        address=address,
        session_id=session_id,
    )
    try:
        status = await asyncio.to_thread(
            _post_json_sync,
            url,
            envelope,
            secret=n8n_webhook_secret(),
            timeout=n8n_timeout_seconds(),
        )
        if 200 <= status < 300:
            logger.info(
                "N8N_DELIVERY_DISPATCH_REQUIRED ok status=%s event_id=%s",
                status,
                envelope.get("event_id"),
            )
            return True
        logger.warning(
            "N8N_DELIVERY_DISPATCH_REQUIRED unexpected status=%s event_id=%s",
            status,
            envelope.get("event_id"),
        )
        return False
    except Exception:
        logger.exception(
            "N8N_DELIVERY_DISPATCH_REQUIRED failed event_id=%s — continuing",
            envelope.get("event_id"),
        )
        return False
