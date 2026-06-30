"""Persist session analytics to Supabase with local JSON fallback."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger("analytics-store")

DEFAULT_FALLBACK_DIR = Path(os.getenv("SESSION_FALLBACK_DIR", "data/sessions"))


def analytics_enabled() -> bool:
    if os.getenv("SESSION_ANALYTICS_ENABLED", "1").strip() in ("0", "false", "False"):
        return False
    return bool(os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_SERVICE_ROLE_KEY"))


def _fallback_path(session_id: str) -> Path:
    DEFAULT_FALLBACK_DIR.mkdir(parents=True, exist_ok=True)
    return DEFAULT_FALLBACK_DIR / f"{session_id}.json"


def write_fallback(payload: dict[str, Any]) -> Path:
    session_id = payload["session"]["id"]
    path = _fallback_path(session_id)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Session analytics saved locally: %s", path)
    return path


def _persist_sync(payload: dict[str, Any]) -> None:
    from supabase import create_client

    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    client = create_client(url, key)

    session = payload["session"]
    session_id = session["id"]

    client.table("call_sessions").upsert(session).execute()

    turns = []
    for t in payload.get("turns") or []:
        turns.append({
            "session_id": session_id,
            "turn_number": t["turn_number"],
            "user_stt": t.get("user_stt"),
            "stt_language": t.get("stt_language"),
            "sierra_spoken": t.get("sierra_spoken"),
            "intent": t.get("intent"),
            "phase": t.get("phase"),
            "was_filtered": t.get("was_filtered", False),
            "filter_reason": t.get("filter_reason"),
            "auto_add": t.get("auto_add", False),
            "tools_called": t.get("tools_called") or [],
            "cart_snapshot": t.get("cart_snapshot"),
            "latency": t.get("latency"),
        })
    if turns:
        client.table("call_turns").insert(turns).execute()

    events = []
    for e in payload.get("events") or []:
        events.append({
            "session_id": session_id,
            "event_type": e["event_type"],
            "payload": e.get("payload") or {},
        })
    if events:
        client.table("call_events").insert(events).execute()

    order = payload.get("order")
    if order:
        client.table("orders").insert(order).execute()

    logger.info("Session analytics persisted to Supabase: %s", session_id)


async def persist_session(payload: dict[str, Any]) -> None:
    """Non-blocking persist — never raises to caller."""
    session_id = payload.get("session", {}).get("id", "unknown")
    try:
        if analytics_enabled():
            await asyncio.to_thread(_persist_sync, payload)
        else:
            write_fallback(payload)
    except Exception:
        logger.exception("Supabase persist failed for %s — writing fallback", session_id)
        try:
            write_fallback(payload)
        except Exception:
            logger.exception("Fallback write also failed for %s", session_id)
