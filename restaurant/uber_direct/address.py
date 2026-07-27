"""Structured address helpers for Uber Direct quotes."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from restaurant.uber_direct.config import StructuredAddress

# Canadian postal: A1A 1A1 (space optional)
_POSTAL_CA_RE = re.compile(
    r"^[ABCEGHJ-NPRSTVXY]\d[ABCEGHJ-NPRSTV-Z]\s?\d[ABCEGHJ-NPRSTV-Z]\d$",
    re.IGNORECASE,
)


def _clean_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


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
    street_c = _clean_text(street)
    city_c = _clean_text(city)
    state_c = _clean_text(state).upper()
    postal_c = (postal or "").strip().upper()
    country_c = _clean_text(country or "CA").upper() or "CA"
    unit_c = _clean_text(unit) or None
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
            phone=_clean_text(phone) or None,
            name=_clean_text(name) or None,
            notes=_clean_text(notes) or None,
        ),
        [],
    )


def structured_address_to_dict(addr: StructuredAddress) -> dict[str, Any]:
    """JSON-safe normalized Store/Uber address."""
    return {
        "street": addr.street,
        "unit": addr.unit,
        "city": addr.city,
        "state": addr.state,
        "postal": addr.postal,
        "country": addr.country,
        "lat": addr.lat,
        "lng": addr.lng,
        "phone": addr.phone,
        "name": addr.name,
        "notes": addr.notes,
    }


def canonical_address_payload(addr: StructuredAddress) -> dict[str, Any]:
    """Address identity used to bind a quote to checkout.

    Contact name/phone and delivery notes are deliberately excluded: they do not
    change the priced route. Text comparison is case/whitespace insensitive.
    Coordinates are included when supplied because they can affect Uber routing.
    """

    def identity_text(value: str | None) -> str:
        return _clean_text(value).casefold()

    def coordinate(value: float | None) -> float | None:
        return round(float(value), 6) if value is not None else None

    return {
        "street": identity_text(addr.street),
        "unit": identity_text(addr.unit),
        "city": identity_text(addr.city),
        "state": identity_text(addr.state),
        "postal": re.sub(r"\s+", "", addr.postal or "").upper(),
        "country": (addr.country or "CA").strip().upper(),
        "lat": coordinate(addr.lat),
        "lng": coordinate(addr.lng),
    }


def address_fingerprint(addr: StructuredAddress) -> str:
    """Stable SHA-256 binding for a normalized quote destination."""
    raw = json.dumps(
        canonical_address_payload(addr),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


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
