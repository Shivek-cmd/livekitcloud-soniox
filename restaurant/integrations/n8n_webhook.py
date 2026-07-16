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
        },
        "meta": {
            "source": "sierra",
            "language": getattr(language, "value", language) if language is not None else None,
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
