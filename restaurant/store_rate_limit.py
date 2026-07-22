"""Simple in-memory rate limit for Store checkout (S5).

Per-process only — fine for a single token_server worker on the VPS.
Not shared across multiple workers; raise STORE_CHECKOUT_RATE_LIMIT if needed.
"""

from __future__ import annotations

import os
import threading
import time
from collections import defaultdict, deque


def _limit() -> int:
    raw = (os.getenv("STORE_CHECKOUT_RATE_LIMIT") or "20").strip()
    try:
        return max(1, int(raw))
    except ValueError:
        return 20


def _window_sec() -> float:
    raw = (os.getenv("STORE_CHECKOUT_RATE_WINDOW_SEC") or "60").strip()
    try:
        return max(1.0, float(raw))
    except ValueError:
        return 60.0


_lock = threading.Lock()
_hits: dict[str, deque[float]] = defaultdict(deque)


def allow_store_checkout(client_key: str) -> bool:
    """Return True if this client may call checkout now; else False (429)."""
    now = time.monotonic()
    window = _window_sec()
    limit = _limit()
    key = (client_key or "unknown").strip() or "unknown"
    with _lock:
        q = _hits[key]
        while q and now - q[0] > window:
            q.popleft()
        if len(q) >= limit:
            return False
        q.append(now)
        return True


def reset_store_rate_limits() -> None:
    """Test helper."""
    with _lock:
        _hits.clear()
