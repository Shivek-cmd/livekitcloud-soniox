"""Uber Direct HTTP client — OAuth + create delivery quote (P1)."""

from __future__ import annotations

import json
import logging
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

from restaurant.uber_direct.address import to_uber_address_json
from restaurant.uber_direct.config import (
    StructuredAddress,
    UberDirectCredentials,
    credentials_from_env,
)

logger = logging.getLogger("uber-direct")

AUTH_URL = "https://auth.uber.com/oauth/v2/token"
API_BASE = "https://api.uber.com"
SCOPE = "eats.deliveries"


class UberDirectError(Exception):
    def __init__(self, message: str, *, status: int | None = None, payload: Any = None):
        self.status = status
        self.payload = payload
        super().__init__(message)


@dataclass(frozen=True)
class DeliveryQuote:
    quote_id: str
    fee_cents: int
    currency: str
    duration_minutes: int | None
    pickup_duration_minutes: int | None
    dropoff_eta: str | None
    expires_at: str | None
    raw: dict[str, Any]

    @property
    def fee(self) -> float:
        return round(self.fee_cents / 100.0, 2)


@dataclass
class _TokenCache:
    access_token: str = ""
    expires_at_monotonic: float = 0.0


_token_lock = threading.Lock()
_token_cache = _TokenCache()


def _request_json(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    body: dict | None = None,
    form: dict[str, str] | None = None,
    timeout: float = 30.0,
) -> Any:
    data: bytes | None = None
    req_headers = dict(headers or {})
    if form is not None:
        data = urllib.parse.urlencode(form).encode()
        req_headers.setdefault("Content-Type", "application/x-www-form-urlencoded")
    elif body is not None:
        data = json.dumps(body).encode()
        req_headers.setdefault("Content-Type", "application/json")
    req_headers.setdefault("Accept", "application/json")

    req = urllib.request.Request(url, data=data, method=method, headers=req_headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            payload = json.loads(raw) if raw else {"raw": ""}
        except json.JSONDecodeError:
            payload = {"raw": raw[:500]}
        raise UberDirectError(
            f"Uber HTTP {e.code}: {payload}",
            status=e.code,
            payload=payload,
        ) from e
    except urllib.error.URLError as e:
        raise UberDirectError(f"Uber network error: {e}") from e


def fetch_access_token(
    creds: UberDirectCredentials,
    *,
    force_refresh: bool = False,
) -> str:
    """Client-credentials OAuth; caches token until near expiry."""
    with _token_lock:
        now = time.monotonic()
        if (
            not force_refresh
            and _token_cache.access_token
            and now < _token_cache.expires_at_monotonic - 60
        ):
            return _token_cache.access_token

    payload = _request_json(
        "POST",
        AUTH_URL,
        form={
            "client_id": creds.client_id,
            "client_secret": creds.client_secret,
            "grant_type": "client_credentials",
            "scope": SCOPE,
        },
    )
    if not isinstance(payload, dict) or not payload.get("access_token"):
        raise UberDirectError("Uber OAuth response missing access_token", payload=payload)

    token = str(payload["access_token"])
    expires_in = int(payload.get("expires_in") or 2592000)
    with _token_lock:
        _token_cache.access_token = token
        _token_cache.expires_at_monotonic = time.monotonic() + max(60, expires_in)
    return token


def clear_token_cache() -> None:
    """Test helper."""
    with _token_lock:
        _token_cache.access_token = ""
        _token_cache.expires_at_monotonic = 0.0


def create_delivery_quote(
    *,
    pickup: StructuredAddress,
    dropoff: StructuredAddress,
    creds: UberDirectCredentials | None = None,
    manifest_total_value_cents: int | None = None,
) -> DeliveryQuote:
    """POST /v1/customers/{customer_id}/delivery_quotes."""
    creds = creds or credentials_from_env()
    if creds is None:
        raise UberDirectError("Uber Direct credentials are not configured")

    token = fetch_access_token(creds)
    body: dict[str, Any] = {
        "pickup_address": to_uber_address_json(pickup),
        "dropoff_address": to_uber_address_json(dropoff),
    }
    if pickup.lat is not None and pickup.lng is not None:
        body["pickup_latitude"] = pickup.lat
        body["pickup_longitude"] = pickup.lng
    if dropoff.lat is not None and dropoff.lng is not None:
        body["dropoff_latitude"] = dropoff.lat
        body["dropoff_longitude"] = dropoff.lng
    if pickup.phone:
        body["pickup_phone_number"] = pickup.phone
    if dropoff.phone:
        body["dropoff_phone_number"] = dropoff.phone
    if manifest_total_value_cents is not None:
        body["manifest_total_value"] = int(manifest_total_value_cents)

    url = f"{API_BASE}/v1/customers/{creds.customer_id}/delivery_quotes"
    try:
        payload = _request_json(
            "POST",
            url,
            headers={"Authorization": f"Bearer {token}"},
            body=body,
        )
    except UberDirectError as e:
        # One retry on 401 with fresh token
        if e.status == 401:
            token = fetch_access_token(creds, force_refresh=True)
            payload = _request_json(
                "POST",
                url,
                headers={"Authorization": f"Bearer {token}"},
                body=body,
            )
        else:
            raise

    if not isinstance(payload, dict):
        raise UberDirectError("Uber quote response was not an object", payload=payload)

    quote_id = str(payload.get("id") or "").strip()
    if not quote_id:
        raise UberDirectError("Uber quote missing id", payload=payload)

    fee_cents = int(payload.get("fee") or 0)
    currency = str(
        payload.get("currency_type") or payload.get("currency") or "CAD"
    ).upper()
    duration = payload.get("duration")
    pickup_duration = payload.get("pickup_duration")

    return DeliveryQuote(
        quote_id=quote_id,
        fee_cents=fee_cents,
        currency=currency,
        duration_minutes=int(duration) if duration is not None else None,
        pickup_duration_minutes=(
            int(pickup_duration) if pickup_duration is not None else None
        ),
        dropoff_eta=str(payload["dropoff_eta"]) if payload.get("dropoff_eta") else None,
        expires_at=str(payload["expires"]) if payload.get("expires") else None,
        raw=payload,
    )


@dataclass(frozen=True)
class CreatedDelivery:
    delivery_id: str
    tracking_url: str | None
    status: str | None
    fee_cents: int | None
    raw: dict[str, Any]


def create_delivery(
    *,
    quote_id: str,
    pickup: StructuredAddress,
    dropoff: StructuredAddress,
    manifest_items: list[dict[str, Any]],
    external_id: str | None = None,
    pickup_ready_dt: str | None = None,
    creds: UberDirectCredentials | None = None,
) -> CreatedDelivery:
    """POST /v1/customers/{customer_id}/deliveries."""
    creds = creds or credentials_from_env()
    if creds is None:
        raise UberDirectError("Uber Direct credentials are not configured")

    qid = (quote_id or "").strip()
    if not qid:
        raise UberDirectError("quote_id is required to create a delivery")

    token = fetch_access_token(creds)
    body: dict[str, Any] = {
        "quote_id": qid,
        "pickup_name": pickup.name or "Restaurant",
        "pickup_address": to_uber_address_json(pickup),
        "pickup_phone_number": pickup.phone or "+10000000000",
        "dropoff_name": dropoff.name or "Customer",
        "dropoff_address": to_uber_address_json(dropoff),
        "dropoff_phone_number": dropoff.phone or "+10000000000",
        "manifest_items": manifest_items
        or [{"name": "Food order", "quantity": 1, "size": "small"}],
    }
    if pickup.lat is not None and pickup.lng is not None:
        body["pickup_latitude"] = pickup.lat
        body["pickup_longitude"] = pickup.lng
    if dropoff.lat is not None and dropoff.lng is not None:
        body["dropoff_latitude"] = dropoff.lat
        body["dropoff_longitude"] = dropoff.lng
    if pickup.notes:
        body["pickup_notes"] = pickup.notes
    if dropoff.notes:
        body["dropoff_notes"] = dropoff.notes
    if external_id:
        body["external_id"] = external_id
    if pickup_ready_dt:
        body["pickup_ready_dt"] = pickup_ready_dt

    url = f"{API_BASE}/v1/customers/{creds.customer_id}/deliveries"
    try:
        payload = _request_json(
            "POST",
            url,
            headers={"Authorization": f"Bearer {token}"},
            body=body,
        )
    except UberDirectError as e:
        if e.status == 401:
            token = fetch_access_token(creds, force_refresh=True)
            payload = _request_json(
                "POST",
                url,
                headers={"Authorization": f"Bearer {token}"},
                body=body,
            )
        else:
            raise

    if not isinstance(payload, dict):
        raise UberDirectError(
            "Uber delivery response was not an object", payload=payload
        )

    delivery_id = str(payload.get("id") or "").strip()
    if not delivery_id:
        raise UberDirectError("Uber delivery missing id", payload=payload)

    fee = payload.get("fee")
    return CreatedDelivery(
        delivery_id=delivery_id,
        tracking_url=(
            str(payload["tracking_url"]) if payload.get("tracking_url") else None
        ),
        status=str(payload["status"]) if payload.get("status") else None,
        fee_cents=int(fee) if fee is not None else None,
        raw=payload,
    )


def fetch_delivery(
    *,
    delivery_id: str,
    creds: UberDirectCredentials | None = None,
) -> dict[str, Any]:
    """GET a modern Direct delivery by its known Uber delivery ID."""
    creds = creds or credentials_from_env()
    if creds is None:
        raise UberDirectError("Uber Direct credentials are not configured")
    did = (delivery_id or "").strip()
    if not did:
        raise UberDirectError("delivery_id is required")
    token = fetch_access_token(creds)
    encoded_id = urllib.parse.quote(did, safe="")
    url = (
        f"{API_BASE}/v1/customers/{creds.customer_id}/deliveries/{encoded_id}"
    )
    try:
        payload = _request_json(
            "GET",
            url,
            headers={"Authorization": f"Bearer {token}"},
        )
    except UberDirectError as e:
        if e.status != 401:
            raise
        token = fetch_access_token(creds, force_refresh=True)
        payload = _request_json(
            "GET",
            url,
            headers={"Authorization": f"Bearer {token}"},
        )
    if not isinstance(payload, dict):
        raise UberDirectError(
            "Uber Get Delivery response was not an object",
            payload=payload,
        )
    return payload


def fetch_delivery_resource(
    *,
    resource_href: str,
    creds: UberDirectCredentials | None = None,
) -> dict[str, Any]:
    """Fetch a legacy DAPI resource URL after strict Uber-host validation."""
    creds = creds or credentials_from_env()
    if creds is None:
        raise UberDirectError("Uber Direct credentials are not configured")
    parsed = urllib.parse.urlsplit((resource_href or "").strip())
    if (
        parsed.scheme != "https"
        or parsed.hostname != "api.uber.com"
        or not parsed.path.startswith("/v1/eats/deliveries/orders/")
        or parsed.username
        or parsed.password
        or parsed.port not in (None, 443)
    ):
        raise UberDirectError("Unsafe Uber resource_href")
    safe_url = urllib.parse.urlunsplit(
        ("https", "api.uber.com", parsed.path, parsed.query, "")
    )
    token = fetch_access_token(creds)
    try:
        payload = _request_json(
            "GET",
            safe_url,
            headers={"Authorization": f"Bearer {token}"},
        )
    except UberDirectError as e:
        if e.status != 401:
            raise
        token = fetch_access_token(creds, force_refresh=True)
        payload = _request_json(
            "GET",
            safe_url,
            headers={"Authorization": f"Bearer {token}"},
        )
    if not isinstance(payload, dict):
        raise UberDirectError(
            "Uber Get Delivery resource response was not an object",
            payload=payload,
        )
    return payload
