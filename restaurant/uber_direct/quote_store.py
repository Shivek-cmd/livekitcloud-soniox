"""Persist Uber Direct quotes briefly so checkout can re-validate fee (P3)."""

from __future__ import annotations

import json
import logging
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("uber-direct-quote-store")

_lock = threading.Lock()


def _store_path() -> Path:
    return Path(
        os.getenv("UBER_DIRECT_QUOTE_STORE_PATH", "data/store_uber_quotes.json")
    )


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_expires(raw: str | None) -> datetime | None:
    if not raw:
        return None
    text = raw.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _load(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"quotes": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        logger.exception("Corrupt Uber quote store at %s — starting empty", path)
        return {"quotes": {}}
    if not isinstance(data, dict):
        return {"quotes": {}}
    if not isinstance(data.get("quotes"), dict):
        data["quotes"] = {}
    return data


def _save(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def record_quote(
    *,
    quote_id: str,
    fee_cents: int,
    currency: str,
    expires_at: str | None,
    dropoff_line: str | None = None,
    duration_minutes: int | None = None,
    dropoff: dict[str, Any] | None = None,
) -> None:
    qid = (quote_id or "").strip()
    if not qid:
        return
    path = _store_path()
    with _lock:
        data = _load(path)
        data["quotes"][qid] = {
            "quote_id": qid,
            "fee_cents": int(fee_cents),
            "fee": round(int(fee_cents) / 100.0, 2),
            "currency": (currency or "CAD").upper(),
            "expires_at": expires_at,
            "dropoff_line": dropoff_line,
            "dropoff": dropoff if isinstance(dropoff, dict) else None,
            "duration_minutes": duration_minutes,
            "recorded_at": _now().strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        # Drop clearly expired entries (best-effort cleanup)
        now = _now()
        stale = []
        for key, rec in data["quotes"].items():
            exp = _parse_expires(rec.get("expires_at") if isinstance(rec, dict) else None)
            if exp is not None and exp < now:
                stale.append(key)
        for key in stale:
            if key != qid:
                data["quotes"].pop(key, None)
        _save(path, data)


def get_valid_quote(quote_id: str | None) -> dict[str, Any] | None:
    """Return quote record if present and not expired."""
    qid = (quote_id or "").strip()
    if not qid:
        return None
    path = _store_path()
    with _lock:
        data = _load(path)
        rec = data["quotes"].get(qid)
    if not isinstance(rec, dict):
        return None
    exp = _parse_expires(rec.get("expires_at"))
    if exp is not None and exp < _now():
        return None
    return rec


def clear_quote_store() -> None:
    """Test helper."""
    path = _store_path()
    with _lock:
        if path.exists():
            path.unlink()
