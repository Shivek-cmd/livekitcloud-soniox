"""Store-facing Uber Direct quote orchestration (P1)."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from restaurant.uber_direct.address import (
    address_fingerprint,
    validate_structured_address,
)
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
            dropoff_address=addr,
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
        "dispatch_state": None,
        "attempts": 0,
        "reused": False,
    }
    if not store_uber_direct_enabled():
        out["error"] = "disabled"
        return out
    if (summary.get("order_type") or "").lower() != "delivery":
        out["error"] = "not_delivery"
        return out

    order_key = str(summary.get("order_id") or summary.get("session_id") or "").strip()
    if not order_key:
        out["error"] = "missing_order_key"
        return out
    quote_id = (summary.get("uber_quote_id") or "").strip()
    from restaurant.uber_direct.delivery_store import (
        claim_order_dispatch,
        mark_dispatch_required,
        mark_dispatch_success,
    )

    def require_dispatch(reason: str, *, uncertain: bool = False) -> dict[str, Any]:
        record = mark_dispatch_required(
            order_key=order_key,
            reason=reason,
            uncertain_outcome=uncertain,
        )
        attempts = int((record or {}).get("attempts") or 0)
        summary["uber_dispatch_state"] = "dispatch_required"
        summary["uber_dispatch_required"] = True
        summary["uber_dispatch_reason"] = reason
        summary["uber_dispatch_attempts"] = attempts
        summary["uber_dispatch_uncertain"] = bool(uncertain)
        out.update(
            {
                "error": reason,
                "dispatch_state": "dispatch_required",
                "attempts": attempts,
            }
        )
        return out

    if not quote_id:
        return require_dispatch("missing_quote")

    from restaurant.uber_direct.quote_store import get_valid_quote

    rec = get_valid_quote(quote_id)
    if rec is None:
        logger.warning("Uber dispatch skipped — quote invalid id=%s", quote_id)
        return require_dispatch("quote_expired_or_missing")

    pickup = pickup_from_env()
    if pickup is None:
        return require_dispatch("pickup_not_configured")

    # Dispatch from the checkout summary, never from an older quote payload.
    drop_raw = (
        summary.get("delivery_dropoff")
        if isinstance(summary.get("delivery_dropoff"), dict)
        else {}
    )
    customer = (
        summary.get("customer")
        if isinstance(summary.get("customer"), dict)
        else {}
    )
    dropoff, dropoff_blockers = validate_structured_address(
        street=str(drop_raw.get("street") or ""),
        city=str(drop_raw.get("city") or ""),
        state=str(drop_raw.get("state") or ""),
        postal=str(drop_raw.get("postal") or ""),
        country=str(drop_raw.get("country") or "CA"),
        unit=str(drop_raw.get("unit") or "") or None,
        lat=_opt_float(drop_raw.get("lat")),
        lng=_opt_float(drop_raw.get("lng")),
        phone=str(customer.get("phone") or drop_raw.get("phone") or "") or None,
        name=str(customer.get("name") or drop_raw.get("name") or "Customer"),
        notes=str(drop_raw.get("notes") or "") or None,
    )
    if dropoff is None or dropoff_blockers:
        return require_dispatch("dropoff_incomplete")
    if rec.get("address_fingerprint") != address_fingerprint(dropoff):
        logger.warning(
            "Uber dispatch skipped — checkout address does not match quote id=%s",
            quote_id,
        )
        return require_dispatch("quote_address_mismatch")

    claim = claim_order_dispatch(
        order_key=order_key,
        quote_id=quote_id,
        checkout_key=str(summary.get("checkout_key") or "") or None,
        session_id=str(summary.get("session_id") or "") or None,
    )
    action = claim.get("action")
    if action == "dispatched":
        attempts = int(claim.get("attempts") or 1)
        summary["uber_delivery_id"] = claim.get("delivery_id")
        summary["uber_tracking_url"] = claim.get("tracking_url")
        summary["uber_delivery_status"] = claim.get("status")
        summary["uber_dispatch_state"] = "dispatched"
        summary["uber_dispatch_required"] = False
        summary["uber_dispatch_attempts"] = attempts
        out.update(
            {
                "ok": True,
                "delivery_id": claim.get("delivery_id"),
                "tracking_url": claim.get("tracking_url"),
                "status": claim.get("status"),
                "dispatch_state": "dispatched",
                "attempts": attempts,
                "reused": True,
            }
        )
        return out
    if action == "dispatch_required":
        reason = str(claim.get("reason") or "dispatch_required")
        attempts = int(claim.get("attempts") or 0)
        summary["uber_dispatch_state"] = "dispatch_required"
        summary["uber_dispatch_required"] = True
        summary["uber_dispatch_reason"] = reason
        summary["uber_dispatch_attempts"] = attempts
        summary["uber_dispatch_uncertain"] = bool(claim.get("uncertain_outcome"))
        out.update(
            {
                "error": reason,
                "dispatch_state": "dispatch_required",
                "attempts": attempts,
                "reused": True,
            }
        )
        return out
    if action == "in_progress":
        attempts = int(claim.get("attempts") or 1)
        summary["uber_dispatch_state"] = "creating"
        summary["uber_dispatch_required"] = False
        summary["uber_dispatch_attempts"] = attempts
        out.update(
            {
                "error": "dispatch_in_progress",
                "dispatch_state": "creating",
                "attempts": attempts,
                "reused": True,
            }
        )
        return out
    if action != "claimed":
        return require_dispatch("dispatch_claim_failed")

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
        summary["uber_dispatch_error"] = str(e)
        uncertain = e.status is None or e.status in (408, 429) or e.status >= 500
        reason = (
            "uber_create_outcome_unknown"
            if uncertain
            else f"uber_create_rejected:{e.status or 'unknown'}"
        )
        return require_dispatch(reason, uncertain=uncertain)
    except Exception as e:
        logger.exception("Uber create delivery unexpected error")
        summary["uber_dispatch_error"] = str(e)
        return require_dispatch("uber_create_outcome_unknown", uncertain=True)

    persisted = mark_dispatch_success(
        order_key=order_key,
        delivery_id=created.delivery_id,
        status=created.status,
        tracking_url=created.tracking_url,
        notification_context={
            "channel": "web_store",
            "customer_name": str(customer.get("name") or "").strip() or None,
            "customer_phone": str(customer.get("phone") or "").strip() or None,
            "clover_order_id": str(summary.get("order_id") or order_key).strip(),
            "order_type": str(summary.get("order_type") or "delivery").strip(),
            "total": summary.get("total"),
            "session_id": str(summary.get("session_id") or "").strip() or None,
        },
        raw=created.raw,
    )
    summary["uber_delivery_id"] = created.delivery_id
    summary["uber_tracking_url"] = created.tracking_url
    summary["uber_delivery_status"] = created.status
    summary["uber_dispatch_state"] = "dispatched"
    summary["uber_dispatch_required"] = False
    summary["uber_dispatch_reason"] = None
    summary["uber_dispatch_attempts"] = int((persisted or {}).get("attempts") or 1)
    out.update(
        {
            "ok": True,
            "delivery_id": created.delivery_id,
            "tracking_url": created.tracking_url,
            "status": created.status,
            "error": None,
            "dispatch_state": "dispatched",
            "attempts": summary["uber_dispatch_attempts"],
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
