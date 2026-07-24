"""Persist Uber Direct delivery status from webhooks (PR 093 P5)."""

from __future__ import annotations

import json
import logging
import os
import threading
from datetime import datetime, timezone
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


def _load(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"deliveries": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        logger.exception("Corrupt Uber delivery store at %s — starting empty", path)
        return {"deliveries": {}}
    if not isinstance(data, dict):
        return {"deliveries": {}}
    if not isinstance(data.get("deliveries"), dict):
        data["deliveries"] = {}
    return data


def _save(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


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
