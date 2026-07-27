"""Durable idempotency records for Web Store Place requests (PR 097 P2)."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("store-checkout-idempotency")

_lock = threading.Lock()


def _store_path() -> Path:
    return Path(
        os.getenv(
            "STORE_CHECKOUT_IDEMPOTENCY_PATH",
            "data/store_checkout_idempotency.json",
        )
    )


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"checkouts": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        logger.exception("Corrupt checkout idempotency store at %s", path)
        return {"checkouts": {}}
    if not isinstance(data, dict):
        return {"checkouts": {}}
    if not isinstance(data.get("checkouts"), dict):
        data["checkouts"] = {}
    return data


def _save(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def checkout_request_fingerprint(summary: dict[str, Any]) -> str:
    """Fingerprint stable customer/cart/payment inputs, excluding runtime output."""
    stable = {
        "items": summary.get("items"),
        "order_type": summary.get("order_type"),
        "customer": summary.get("customer"),
        "delivery_address": summary.get("delivery_address"),
        "delivery_dropoff": summary.get("delivery_dropoff"),
        "note": summary.get("note"),
        "payment_preference": summary.get("payment_preference"),
        "subtotal": summary.get("subtotal"),
        "delivery_charge": summary.get("delivery_charge"),
        "total": summary.get("total"),
        "uber_quote_id": summary.get("uber_quote_id"),
    }
    raw = json.dumps(
        stable,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def claim_checkout(
    *,
    checkout_key: str,
    request_fingerprint: str,
) -> dict[str, Any]:
    """Claim a Place key or replay its completed result."""
    key = (checkout_key or "").strip()
    fingerprint = (request_fingerprint or "").strip()
    if not key or not fingerprint:
        return {"action": "legacy"}
    path = _store_path()
    with _lock:
        data = _load(path)
        checkouts: dict[str, Any] = data.setdefault("checkouts", {})
        prev = checkouts.get(key)
        if isinstance(prev, dict):
            if prev.get("request_fingerprint") != fingerprint:
                return {"action": "conflict", **prev}
            if isinstance(prev.get("result"), dict):
                return {"action": "replay", **prev}
            return {"action": "in_progress", **prev}

        now = _now()
        record = {
            "checkout_key": key,
            "request_fingerprint": fingerprint,
            "state": "processing",
            "attempts": 1,
            "claimed_at": now,
            "created_at": now,
            "updated_at": now,
        }
        checkouts[key] = record
        _save(path, data)
        return {"action": "claimed", **record}


def complete_checkout(
    *,
    checkout_key: str,
    result: dict[str, Any],
) -> None:
    key = (checkout_key or "").strip()
    if not key:
        return
    path = _store_path()
    with _lock:
        data = _load(path)
        checkouts: dict[str, Any] = data.setdefault("checkouts", {})
        prev = checkouts.get(key) if isinstance(checkouts.get(key), dict) else {}
        checkouts[key] = {
            **prev,
            "checkout_key": key,
            "state": "completed",
            "result": result,
            "completed_at": _now(),
            "updated_at": _now(),
        }
        _save(path, data)


def get_checkout(checkout_key: str) -> dict[str, Any] | None:
    key = (checkout_key or "").strip()
    if not key:
        return None
    with _lock:
        data = _load(_store_path())
        rec = data.get("checkouts", {}).get(key)
        return dict(rec) if isinstance(rec, dict) else None
