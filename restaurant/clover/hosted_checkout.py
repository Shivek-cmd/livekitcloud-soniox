"""Clover Hosted Checkout (HCO) — pay-now link for Store orders.

Creates a short-lived checkout session (≈15 min). Not inventory-linked;
amounts come from our validated Store summary (cents).

Docs: https://docs.clover.com/dev/docs/creating-a-hosted-checkout-session
"""

from __future__ import annotations

import json
import logging
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger("clover-hosted-checkout")


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name, "").strip().lower()
    if not raw:
        return default
    return raw in ("1", "true", "yes", "on")


def store_pay_now_enabled() -> bool:
    """Kill switch — default off until Ecommerce token is configured on VPS."""
    return _env_bool("STORE_PAY_NOW_ENABLED", False)


def _ecom_token() -> str | None:
    """Ecommerce private key preferred; falls back to CLOVER_API_TOKEN."""
    for key in (
        "CLOVER_ECOM_PRIVATE_TOKEN",
        "CLOVER_HOSTED_CHECKOUT_TOKEN",
        "CLOVER_API_TOKEN",
    ):
        val = (os.getenv(key) or "").strip()
        if val:
            return val
    return None


def _base_url() -> str:
    return (os.getenv("CLOVER_BASE_URL") or "https://apisandbox.dev.clover.com").rstrip(
        "/"
    )


def _merchant_id(*, fallback: str | None = None) -> str | None:
    mid = (os.getenv("CLOVER_MID") or "").strip()
    return mid or (fallback or None)


@dataclass(frozen=True)
class HostedCheckoutSession:
    href: str
    checkout_session_id: str | None
    expiration_time: int | None = None


class HostedCheckoutError(Exception):
    """HCO session could not be created."""


def _dollars_to_cents(amount: float) -> int:
    return int(round(float(amount) * 100))


def _split_name(full: str) -> tuple[str, str]:
    parts = (full or "").strip().split(None, 1)
    if not parts:
        return "Guest", "Customer"
    if len(parts) == 1:
        return parts[0][:64], "Customer"
    return parts[0][:64], parts[1][:64]


def _phone_digits(phone: str | None) -> str | None:
    digits = re.sub(r"\D", "", phone or "")
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    return digits if len(digits) >= 10 else None


def build_hosted_checkout_body(
    summary: dict[str, Any],
    *,
    order_id: str | None = None,
) -> dict[str, Any]:
    """Build HCO create-session JSON from a Store summary."""
    line_items: list[dict[str, Any]] = []
    for line in summary.get("items") or []:
        name = str(line.get("name") or "Item")[:127]
        qty = int(line.get("qty") or 1)
        unit = float(line.get("unit_price") or 0)
        mods = line.get("modifiers") or []
        note_parts = [str(m) for m in mods if m]
        if order_id and not line_items:
            note_parts.insert(0, f"Order {order_id}")
        entry: dict[str, Any] = {
            "name": name,
            "price": _dollars_to_cents(unit),
            "unitQty": max(1, qty),
        }
        if note_parts:
            entry["note"] = ", ".join(note_parts)[:255]
        line_items.append(entry)

    delivery = float(summary.get("delivery_charge") or 0)
    if delivery > 0:
        line_items.append(
            {
                "name": "Delivery",
                "price": _dollars_to_cents(delivery),
                "unitQty": 1,
            }
        )

    if not line_items:
        raise HostedCheckoutError("Cannot create checkout for an empty cart.")

    customer = summary.get("customer") or {}
    first, last = _split_name(str(customer.get("name") or "Guest"))
    customer_body: dict[str, Any] = {
        "firstName": first,
        "lastName": last,
    }
    phone = _phone_digits(customer.get("phone"))
    if phone:
        customer_body["phoneNumber"] = phone

    body: dict[str, Any] = {
        "customer": customer_body,
        "shoppingCart": {"lineItems": line_items},
        "tips": {"enabled": False},
    }

    success = (os.getenv("STORE_PAY_SUCCESS_URL") or "").strip()
    failure = (os.getenv("STORE_PAY_FAILURE_URL") or "").strip()
    if success or failure:
        redirects: dict[str, str] = {}
        if success:
            redirects["success"] = success
        if failure:
            redirects["failure"] = failure
        body["redirectUrls"] = redirects

    page_uuid = (os.getenv("CLOVER_HCO_PAGE_CONFIG_UUID") or "").strip()
    if page_uuid:
        body["pageConfigUuid"] = page_uuid

    return body


def create_hosted_checkout_session(
    summary: dict[str, Any],
    *,
    order_id: str | None = None,
    merchant_id: str | None = None,
    base_url: str | None = None,
    token: str | None = None,
) -> HostedCheckoutSession:
    """POST /invoicingcheckoutservice/v1/checkouts → href.

    Raises HostedCheckoutError on config or API failure.
    """
    tok = (token or _ecom_token() or "").strip()
    if not tok:
        raise HostedCheckoutError(
            "Missing CLOVER_ECOM_PRIVATE_TOKEN (or CLOVER_API_TOKEN fallback)."
        )
    mid = _merchant_id(fallback=merchant_id)
    if not mid:
        raise HostedCheckoutError("Missing CLOVER_MID for Hosted Checkout.")

    root = (base_url or _base_url()).rstrip("/")
    url = f"{root}/invoicingcheckoutservice/v1/checkouts"
    body = build_hosted_checkout_body(summary, order_id=order_id)
    raw = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=raw,
        method="POST",
        headers={
            "Authorization": f"Bearer {tok}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-Clover-Merchant-Id": mid,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = json.loads(resp.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        err_body = e.read().decode()[:500]
        logger.warning(
            "HCO create failed status=%s body=%s", e.code, err_body
        )
        raise HostedCheckoutError(f"Hosted Checkout HTTP {e.code}: {err_body}") from e
    except Exception as e:
        raise HostedCheckoutError(f"Hosted Checkout request failed: {e}") from e

    href = (payload.get("href") or "").strip() if isinstance(payload, dict) else ""
    if not href:
        raise HostedCheckoutError(f"Hosted Checkout response missing href: {payload}")

    return HostedCheckoutSession(
        href=href,
        checkout_session_id=(payload.get("checkoutSessionId") or None),
        expiration_time=payload.get("expirationTime"),
    )
