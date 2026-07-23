"""Persist Store pay-now checkout sessions + payment receipts (P3).

Maps Clover Hosted Checkout session id → our kitchen order id, then
records payment_id + receipt_url when the HCO webhook fires APPROVED.

Default path: data/store_pay_now.json (override with STORE_PAY_NOW_STORE_PATH).
"""

from __future__ import annotations

import json
import logging
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("store-pay-now-store")

_lock = threading.Lock()


def _store_path() -> Path:
    return Path(
        os.getenv("STORE_PAY_NOW_STORE_PATH", "data/store_pay_now.json")
    )


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"sessions": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        logger.exception("Corrupt pay-now store at %s — starting empty", path)
        return {"sessions": {}}
    if not isinstance(data, dict):
        return {"sessions": {}}
    sessions = data.get("sessions")
    if not isinstance(sessions, dict):
        data["sessions"] = {}
    return data


def _save(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def receipt_url_for_payment(payment_id: str) -> str:
    """Build a customer-facing Clover web receipt URL.

    Override with CLOVER_RECEIPT_URL_TEMPLATE using `{payment_id}` placeholder.
    Default matches common Clover web receipt links.
    """
    pid = (payment_id or "").strip()
    template = (
        os.getenv("CLOVER_RECEIPT_URL_TEMPLATE") or "https://www.clover.com/r/{payment_id}"
    ).strip()
    return template.replace("{payment_id}", pid)


def record_pending_checkout(
    *,
    checkout_session_id: str,
    order_id: str | None,
    customer_name: str | None = None,
    customer_phone: str | None = None,
    total: float | None = None,
    order_type: str | None = None,
    session_id: str | None = None,
    checkout_expires_at_ms: int | None = None,
) -> None:
    sid = (checkout_session_id or "").strip()
    if not sid:
        return
    path = _store_path()
    with _lock:
        data = _load(path)
        sessions: dict[str, Any] = data.setdefault("sessions", {})
        prev = sessions.get(sid) if isinstance(sessions.get(sid), dict) else {}
        sessions[sid] = {
            **prev,
            "checkout_session_id": sid,
            "order_id": order_id,
            "customer_name": customer_name,
            "customer_phone": customer_phone,
            "total": total,
            "order_type": order_type,
            "sierra_session_id": session_id,
            "checkout_expires_at_ms": checkout_expires_at_ms,
            "status": prev.get("status") or "pending",
            "created_at": prev.get("created_at") or _now(),
            "updated_at": _now(),
        }
        _save(path, data)
    logger.info(
        "STORE_PAY_PENDING session=%s order_id=%s", sid, order_id
    )


def record_payment_approved(
    *,
    checkout_session_id: str,
    payment_id: str,
    merchant_id: str | None = None,
    message: str | None = None,
    raw: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Mark session paid. Returns the updated record, or None if unknown session."""
    sid = (checkout_session_id or "").strip()
    pid = (payment_id or "").strip()
    if not sid or not pid:
        return None
    receipt_url = receipt_url_for_payment(pid)
    path = _store_path()
    with _lock:
        data = _load(path)
        sessions: dict[str, Any] = data.setdefault("sessions", {})
        prev = sessions.get(sid)
        if not isinstance(prev, dict):
            # Still record so we don't lose the payment if place mapping was missed.
            prev = {
                "checkout_session_id": sid,
                "order_id": None,
                "status": "pending",
                "created_at": _now(),
            }
        record = {
            **prev,
            "checkout_session_id": sid,
            "payment_id": pid,
            "receipt_url": receipt_url,
            "merchant_id": merchant_id,
            "status": "paid",
            "message": message,
            "paid_at": _now(),
            "updated_at": _now(),
        }
        if raw is not None:
            record["webhook_raw"] = raw
        sessions[sid] = record
        _save(path, data)
    logger.info(
        "STORE_PAY_APPROVED session=%s payment_id=%s order_id=%s receipt=%s",
        sid,
        pid,
        record.get("order_id"),
        receipt_url,
    )
    return record


def record_payment_declined(
    *,
    checkout_session_id: str,
    payment_id: str | None = None,
    message: str | None = None,
) -> dict[str, Any] | None:
    sid = (checkout_session_id or "").strip()
    if not sid:
        return None
    path = _store_path()
    with _lock:
        data = _load(path)
        sessions: dict[str, Any] = data.setdefault("sessions", {})
        prev = sessions.get(sid) if isinstance(sessions.get(sid), dict) else {
            "checkout_session_id": sid,
            "created_at": _now(),
        }
        record = {
            **prev,
            "status": "declined",
            "payment_id": payment_id or prev.get("payment_id"),
            "message": message,
            "updated_at": _now(),
        }
        sessions[sid] = record
        _save(path, data)
    return record


def get_by_checkout_session(checkout_session_id: str) -> dict[str, Any] | None:
    sid = (checkout_session_id or "").strip()
    if not sid:
        return None
    with _lock:
        data = _load(_store_path())
        rec = data.get("sessions", {}).get(sid)
        return dict(rec) if isinstance(rec, dict) else None


def get_by_order_id(order_id: str) -> dict[str, Any] | None:
    oid = (order_id or "").strip()
    if not oid:
        return None
    with _lock:
        data = _load(_store_path())
        sessions = data.get("sessions") or {}
        for rec in sessions.values():
            if isinstance(rec, dict) and str(rec.get("order_id") or "") == oid:
                return dict(rec)
    return None


def mark_n8n_paid_notified(checkout_session_id: str) -> None:
    sid = (checkout_session_id or "").strip()
    if not sid:
        return
    path = _store_path()
    with _lock:
        data = _load(path)
        sessions: dict[str, Any] = data.setdefault("sessions", {})
        prev = sessions.get(sid)
        if not isinstance(prev, dict):
            return
        prev["n8n_paid_notified_at"] = _now()
        prev["updated_at"] = _now()
        sessions[sid] = prev
        _save(path, data)


def public_payment_view(rec: dict[str, Any] | None) -> dict[str, Any] | None:
    """Strip internals for API responses."""
    if not rec:
        return None
    return {
        "checkout_session_id": rec.get("checkout_session_id"),
        "order_id": rec.get("order_id"),
        "status": rec.get("status"),
        "payment_id": rec.get("payment_id"),
        "receipt_url": rec.get("receipt_url"),
        "paid_at": rec.get("paid_at"),
    }
