"""Store-facing Uber Direct quote orchestration (P1)."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from restaurant.uber_direct.address import validate_structured_address
from restaurant.uber_direct.client import UberDirectError, create_delivery_quote
from restaurant.uber_direct.config import (
    StructuredAddress,
    credentials_from_env,
    fallback_delivery_charge,
    fee_policy,
    pickup_from_env,
    store_uber_direct_enabled,
)
from restaurant.uber_direct.quote_store import record_quote

logger = logging.getLogger("uber-direct")


@dataclass
class QuoteResult:
    ok: bool
    enabled: bool
    blockers: list[str] = field(default_factory=list)
    quote_id: str | None = None
    fee: float | None = None
    fee_cents: int | None = None
    currency: str | None = None
    duration_minutes: int | None = None
    pickup_duration_minutes: int | None = None
    dropoff_eta: str | None = None
    expires_at: str | None = None
    fee_policy: str = "pass_through"
    fallback_fee: float | None = None
    dropoff_line: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "enabled": self.enabled,
            "blockers": list(self.blockers),
            "quote_id": self.quote_id,
            "fee": self.fee,
            "fee_cents": self.fee_cents,
            "currency": self.currency,
            "duration_minutes": self.duration_minutes,
            "pickup_duration_minutes": self.pickup_duration_minutes,
            "dropoff_eta": self.dropoff_eta,
            "expires_at": self.expires_at,
            "fee_policy": self.fee_policy,
            "fallback_fee": self.fallback_fee,
            "dropoff_line": self.dropoff_line,
        }


def request_store_delivery_quote(payload: dict[str, Any]) -> QuoteResult:
    """Validate dropoff + (if enabled) call Uber Create Quote.

    When kill switch is off: ok=True, enabled=False, fee=fallback flat — no Uber call.
    """
    policy = fee_policy()
    fallback = fallback_delivery_charge()

    if not store_uber_direct_enabled():
        return QuoteResult(
            ok=True,
            enabled=False,
            fee=fallback,
            fee_cents=int(round(fallback * 100)),
            currency="CAD",
            fee_policy="fallback_flat",
            fallback_fee=fallback,
            blockers=[],
        )

    drop = payload.get("dropoff") if isinstance(payload.get("dropoff"), dict) else payload
    addr, blockers = validate_structured_address(
        street=str(drop.get("street") or ""),
        city=str(drop.get("city") or ""),
        state=str(drop.get("state") or drop.get("province") or ""),
        postal=str(drop.get("postal") or drop.get("zip") or ""),
        country=str(drop.get("country") or "CA"),
        unit=(str(drop["unit"]) if drop.get("unit") else None),
        lat=_opt_float(drop.get("lat")),
        lng=_opt_float(drop.get("lng")),
        phone=(
            str(payload.get("dropoff_phone") or drop.get("phone") or "").strip() or None
        ),
        name=(str(drop.get("name") or "").strip() or None),
        notes=(str(drop.get("notes") or "").strip() or None),
    )
    if blockers or addr is None:
        return QuoteResult(
            ok=False,
            enabled=True,
            blockers=blockers or ["Invalid delivery address."],
            fee_policy=policy,
            fallback_fee=fallback,
        )

    pickup = pickup_from_env()
    if pickup is None:
        return QuoteResult(
            ok=False,
            enabled=True,
            blockers=[
                "Restaurant pickup address is not configured "
                "(UBER_DIRECT_PICKUP_* env)."
            ],
            fee_policy=policy,
            fallback_fee=fallback,
            dropoff_line=addr.line(),
        )

    if credentials_from_env() is None:
        return QuoteResult(
            ok=False,
            enabled=True,
            blockers=["Uber Direct credentials are not configured."],
            fee_policy=policy,
            fallback_fee=fallback,
            dropoff_line=addr.line(),
        )

    manifest_cents = None
    if payload.get("subtotal") is not None:
        try:
            manifest_cents = int(round(float(payload["subtotal"]) * 100))
        except (TypeError, ValueError):
            manifest_cents = None

    try:
        quote = create_delivery_quote(
            pickup=pickup,
            dropoff=addr,
            manifest_total_value_cents=manifest_cents,
        )
    except UberDirectError as e:
        logger.warning("Uber Direct quote failed: %s", e)
        return QuoteResult(
            ok=False,
            enabled=True,
            blockers=[
                "Could not get a delivery quote right now. "
                "Try again, or choose pickup."
            ],
            fee_policy=policy,
            fallback_fee=fallback,
            dropoff_line=addr.line(),
        )

    # v1: pass-through only (A)
    fee = quote.fee
    fee_cents = quote.fee_cents
    try:
        record_quote(
            quote_id=quote.quote_id,
            fee_cents=fee_cents,
            currency=quote.currency,
            expires_at=quote.expires_at,
            dropoff_line=addr.line(),
            duration_minutes=quote.duration_minutes,
            dropoff={
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
            },
        )
    except Exception:
        logger.exception("Failed to persist Uber quote %s", quote.quote_id)

    return QuoteResult(
        ok=True,
        enabled=True,
        quote_id=quote.quote_id,
        fee=fee,
        fee_cents=fee_cents,
        currency=quote.currency,
        duration_minutes=quote.duration_minutes,
        pickup_duration_minutes=quote.pickup_duration_minutes,
        dropoff_eta=quote.dropoff_eta,
        expires_at=quote.expires_at,
        fee_policy=policy,
        fallback_fee=fallback,
        dropoff_line=addr.line(),
    )


def dispatch_store_delivery(summary: dict[str, Any]) -> dict[str, Any]:
    """Create Uber delivery after kitchen place. Fail-open — never raises.

    Returns dict with keys: ok, delivery_id, tracking_url, status, error.
    Mutates summary in place when successful.
    """
    out = {
        "ok": False,
        "delivery_id": None,
        "tracking_url": None,
        "status": None,
        "error": None,
    }
    if not store_uber_direct_enabled():
        out["error"] = "disabled"
        return out
    if (summary.get("order_type") or "").lower() != "delivery":
        out["error"] = "not_delivery"
        return out

    quote_id = (summary.get("uber_quote_id") or "").strip()
    if not quote_id:
        out["error"] = "missing_quote"
        return out

    from restaurant.uber_direct.quote_store import get_valid_quote

    rec = get_valid_quote(quote_id)
    if rec is None:
        out["error"] = "quote_expired_or_missing"
        logger.warning("Uber dispatch skipped — quote invalid id=%s", quote_id)
        return out

    pickup = pickup_from_env()
    if pickup is None:
        out["error"] = "pickup_not_configured"
        return out

    drop_raw = rec.get("dropoff") if isinstance(rec.get("dropoff"), dict) else {}
    customer = summary.get("customer") if isinstance(summary.get("customer"), dict) else {}
    dropoff = StructuredAddress(
        street=str(drop_raw.get("street") or ""),
        city=str(drop_raw.get("city") or ""),
        state=str(drop_raw.get("state") or ""),
        postal=str(drop_raw.get("postal") or ""),
        country=str(drop_raw.get("country") or "CA"),
        unit=(str(drop_raw["unit"]) if drop_raw.get("unit") else None),
        lat=_opt_float(drop_raw.get("lat")),
        lng=_opt_float(drop_raw.get("lng")),
        phone=(
            str(drop_raw.get("phone") or customer.get("phone") or "").strip() or None
        ),
        name=(
            str(drop_raw.get("name") or customer.get("name") or "Customer").strip()
            or "Customer"
        ),
        notes=(str(drop_raw["notes"]) if drop_raw.get("notes") else None),
    )
    if not dropoff.street or not dropoff.city:
        out["error"] = "dropoff_incomplete"
        return out

    from datetime import datetime, timedelta, timezone

    from restaurant.uber_direct.client import UberDirectError, create_delivery
    from restaurant.uber_direct.config import prep_minutes

    ready = datetime.now(timezone.utc) + timedelta(minutes=prep_minutes())
    pickup_ready_dt = ready.strftime("%Y-%m-%dT%H:%M:%S.000Z")

    manifest: list[dict[str, Any]] = []
    for line in summary.get("items") or []:
        if not isinstance(line, dict):
            continue
        name = str(line.get("name") or "Item")
        try:
            qty = max(1, int(line.get("qty") or 1))
        except (TypeError, ValueError):
            qty = 1
        price_cents = int(round(float(line.get("unit_price") or 0) * 100))
        manifest.append(
            {
                "name": name[:120],
                "quantity": qty,
                "size": "small",
                "price": price_cents,
            }
        )
    if not manifest:
        manifest = [{"name": "Food order", "quantity": 1, "size": "small"}]

    try:
        created = create_delivery(
            quote_id=quote_id,
            pickup=pickup,
            dropoff=dropoff,
            manifest_items=manifest,
            external_id=str(summary.get("order_id") or summary.get("session_id") or ""),
            pickup_ready_dt=pickup_ready_dt,
        )
    except UberDirectError as e:
        logger.warning("Uber create delivery failed: %s", e)
        out["error"] = str(e)
        summary["uber_dispatch_error"] = str(e)
        return out
    except Exception as e:
        logger.exception("Uber create delivery unexpected error")
        out["error"] = str(e)
        summary["uber_dispatch_error"] = str(e)
        return out

    summary["uber_delivery_id"] = created.delivery_id
    summary["uber_tracking_url"] = created.tracking_url
    summary["uber_delivery_status"] = created.status
    out.update(
        {
            "ok": True,
            "delivery_id": created.delivery_id,
            "tracking_url": created.tracking_url,
            "status": created.status,
            "error": None,
        }
    )
    logger.info(
        "UBER_DELIVERY_CREATED id=%s order=%s tracking=%s",
        created.delivery_id,
        summary.get("order_id"),
        created.tracking_url,
    )
    return out


def _opt_float(val: Any) -> float | None:
    if val is None or val == "":
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None
