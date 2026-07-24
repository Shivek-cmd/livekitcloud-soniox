"""Structured address helpers for Uber Direct quotes."""

from __future__ import annotations

import json
import re

from restaurant.uber_direct.config import StructuredAddress

# Canadian postal: A1A 1A1 (space optional)
_POSTAL_CA_RE = re.compile(
    r"^[ABCEGHJ-NPRSTVXY]\d[ABCEGHJ-NPRSTV-Z]\s?\d[ABCEGHJ-NPRSTV-Z]\d$",
    re.IGNORECASE,
)


def _normalize_ca_postal(postal: str) -> str | None:
    compact = re.sub(r"\s+", "", (postal or "").upper())
    if len(compact) != 6:
        return None
    spaced = f"{compact[:3]} {compact[3:]}"
    if not _POSTAL_CA_RE.match(spaced):
        return None
    return spaced


def validate_structured_address(
    *,
    street: str,
    city: str,
    state: str,
    postal: str,
    country: str = "CA",
    unit: str | None = None,
    lat: float | None = None,
    lng: float | None = None,
    phone: str | None = None,
    name: str | None = None,
    notes: str | None = None,
    require_ca_postal: bool = True,
) -> tuple[StructuredAddress | None, list[str]]:
    blockers: list[str] = []
    street_c = (street or "").strip()
    city_c = (city or "").strip()
    state_c = (state or "").strip().upper()
    postal_c = (postal or "").strip().upper()
    country_c = (country or "CA").strip().upper() or "CA"
    unit_c = (unit or "").strip() or None
    is_ca = country_c in ("CA", "CAN", "CANADA")

    if len(street_c) < 3:
        blockers.append("Delivery street is required.")
    if len(city_c) < 2:
        blockers.append("Delivery city is required.")
    if len(state_c) < 2:
        blockers.append("Delivery province/state is required.")
    if len(postal_c) < 3:
        blockers.append("Delivery postal/ZIP is required.")
    elif require_ca_postal and is_ca:
        normalized = _normalize_ca_postal(postal_c)
        if normalized is None:
            blockers.append("Delivery postal code looks invalid for Canada.")
        else:
            postal_c = normalized

    if blockers:
        return None, blockers

    return (
        StructuredAddress(
            street=street_c,
            city=city_c,
            state=state_c,
            postal=postal_c,
            country="CA" if is_ca else country_c,
            unit=unit_c,
            lat=lat,
            lng=lng,
            phone=(phone or "").strip() or None,
            name=(name or "").strip() or None,
            notes=(notes or "").strip() or None,
        ),
        [],
    )


def to_uber_address_json(addr: StructuredAddress) -> str:
    """Uber expects pickup/dropoff address as a JSON *string* of a structured object."""
    street_lines = [addr.street]
    if addr.unit:
        street_lines.append(addr.unit)
    payload = {
        "street_address": street_lines,
        "city": addr.city,
        "state": addr.state,
        "zip_code": addr.postal,
        "country": addr.country,
    }
    return json.dumps(payload, separators=(",", ":"))
