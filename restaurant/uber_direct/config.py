"""Uber Direct config — Bizbull/env today; tenant-shaped for later.

Sierra is the integration partner; each restaurant owns Uber billing.
This PR reads Bizbull defaults from env (see docs/plan/16-store-uber-direct.md).
"""

from __future__ import annotations

import os
from dataclasses import dataclass


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name, "").strip().lower()
    if not raw:
        return default
    return raw in ("1", "true", "yes", "on")


def store_uber_direct_enabled() -> bool:
    """Kill switch — default off until P1+ is approved on VPS."""
    return _env_bool("STORE_UBER_DIRECT_ENABLED", False)


def uber_direct_env() -> str:
    raw = (os.getenv("UBER_DIRECT_ENV") or "sandbox").strip().lower()
    return raw if raw in ("sandbox", "production") else "sandbox"


def webhook_secret() -> str:
    """Signing key for the configured Uber Direct webhook endpoint."""
    return (os.getenv("UBER_DIRECT_WEBHOOK_SECRET") or "").strip()


def fee_policy() -> str:
    """v1 locked to pass-through (A). Later: per-tenant A/B/C/D."""
    return (os.getenv("UBER_DIRECT_FEE_POLICY") or "pass_through").strip().lower()


def prep_minutes() -> int:
    raw = (os.getenv("UBER_DIRECT_PREP_MINUTES") or "25").strip()
    try:
        return max(0, min(120, int(raw)))
    except ValueError:
        return 25


def fallback_delivery_charge() -> float:
    """When Direct off / quote fails — tenant flat fee (Bizbull $5 today)."""
    raw = (os.getenv("DELIVERY_CHARGE") or "5").strip()
    try:
        return max(0.0, float(raw))
    except ValueError:
        return 5.0


@dataclass(frozen=True)
class UberDirectCredentials:
    customer_id: str
    client_id: str
    client_secret: str


def credentials_from_env() -> UberDirectCredentials | None:
    customer_id = (os.getenv("UBER_DIRECT_CUSTOMER_ID") or "").strip()
    client_id = (os.getenv("UBER_DIRECT_CLIENT_ID") or "").strip()
    client_secret = (os.getenv("UBER_DIRECT_CLIENT_SECRET") or "").strip()
    if not customer_id or not client_id or not client_secret:
        return None
    return UberDirectCredentials(
        customer_id=customer_id,
        client_id=client_id,
        client_secret=client_secret,
    )


@dataclass(frozen=True)
class StructuredAddress:
    street: str
    city: str
    state: str
    postal: str
    country: str = "CA"
    unit: str | None = None
    lat: float | None = None
    lng: float | None = None
    phone: str | None = None
    name: str | None = None
    notes: str | None = None

    def line(self) -> str:
        """Single-line form for Clover / n8n / display."""
        street = self.street.strip()
        if self.unit and self.unit.strip():
            street = f"{street}, {self.unit.strip()}"
        parts = [
            street,
            self.city.strip(),
            f"{self.state.strip()} {self.postal.strip()}".strip(),
            self.country.strip(),
        ]
        return ", ".join(p for p in parts if p)


def pickup_from_env() -> StructuredAddress | None:
    street = (os.getenv("UBER_DIRECT_PICKUP_STREET") or "").strip()
    city = (os.getenv("UBER_DIRECT_PICKUP_CITY") or "").strip()
    state = (os.getenv("UBER_DIRECT_PICKUP_STATE") or "").strip()
    postal = (os.getenv("UBER_DIRECT_PICKUP_POSTAL") or "").strip()
    if not street or not city or not state or not postal:
        return None

    def _float(name: str) -> float | None:
        raw = (os.getenv(name) or "").strip()
        if not raw:
            return None
        try:
            return float(raw)
        except ValueError:
            return None

    country = (os.getenv("UBER_DIRECT_PICKUP_COUNTRY") or "CA").strip() or "CA"
    return StructuredAddress(
        street=street,
        city=city,
        state=state,
        postal=postal,
        country=country,
        unit=None,
        lat=_float("UBER_DIRECT_PICKUP_LAT"),
        lng=_float("UBER_DIRECT_PICKUP_LNG"),
        phone=(os.getenv("UBER_DIRECT_PICKUP_PHONE") or "").strip() or None,
        name=(os.getenv("UBER_DIRECT_PICKUP_NAME") or "Bizbull Restaurant").strip(),
        notes=(os.getenv("UBER_DIRECT_PICKUP_NOTES") or "").strip() or None,
    )


def public_store_flags() -> dict:
    """Safe flags for GET /store/config (no secrets)."""
    return {
        "uber_direct_enabled": store_uber_direct_enabled(),
        "uber_direct_fee_policy": fee_policy(),
        "uber_direct_prep_minutes": prep_minutes(),
        "delivery_charge_fallback": fallback_delivery_charge(),
    }
