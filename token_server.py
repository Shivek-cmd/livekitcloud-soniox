import asyncio
import json
import logging
import os
import uuid

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from livekit.api import AccessToken, VideoGrants, LiveKitAPI, CreateAgentDispatchRequest
from pydantic import BaseModel, Field

from restaurant import menu_provider
from restaurant.clover.hco_webhook import (
    parse_hco_webhook_payload,
    verify_clover_signature,
)
from restaurant.integrations.n8n_webhook import (
    n8n_sync_enabled,
    notify_delivery_status_changed,
    notify_order_paid,
)
from restaurant.store_checkout import (
    STORE_CHANNEL,
    place_store_order,
    validate_store_checkout,
)
from restaurant.store_pay_now_store import (
    get_by_checkout_session,
    get_by_order_id,
    mark_n8n_paid_notified,
    public_payment_view,
    record_payment_approved,
    record_payment_declined,
)
from restaurant.store_rate_limit import allow_hco_webhook, allow_store_checkout
from restaurant.clover.hosted_checkout import store_pay_now_enabled
from restaurant.uber_direct import (
    public_store_flags,
    request_store_delivery_quote,
    store_uber_direct_enabled,
)
from restaurant.uber_direct.client import fetch_delivery_resource
from restaurant.uber_direct.config import webhook_secret
from restaurant.uber_direct.delivery_store import (
    apply_delivery_webhook_event,
    get_delivery,
    mark_delivery_event_notification,
)
from restaurant.uber_direct.webhook import (
    enrich_parsed_delivery,
    parse_uber_delivery_webhook,
    verify_uber_webhook_signature,
)

load_dotenv()
logger = logging.getLogger("token-server")

LIVEKIT_API_KEY = os.environ["LIVEKIT_API_KEY"]
LIVEKIT_API_SECRET = os.environ["LIVEKIT_API_SECRET"]
LIVEKIT_URL = os.environ["LIVEKIT_URL"]

app = FastAPI(title="Restaurant Token Server")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


class StoreCheckoutCustomer(BaseModel):
    name: str = ""
    phone: str = ""


class StoreCheckoutItem(BaseModel):
    id: str
    qty: int = 1
    modifiers: list[str] = Field(default_factory=list)


class StoreDeliveryDropoff(BaseModel):
    street: str = ""
    city: str = ""
    state: str = ""  # province
    postal: str = ""
    country: str = "CA"
    unit: str | None = None
    lat: float | None = None
    lng: float | None = None
    phone: str | None = None
    name: str | None = None
    notes: str | None = None


class StoreCheckoutRequest(BaseModel):
    items: list[StoreCheckoutItem] = Field(default_factory=list)
    order_type: str = ""
    customer: StoreCheckoutCustomer = Field(default_factory=StoreCheckoutCustomer)
    delivery_address: str | None = None
    delivery_dropoff: StoreDeliveryDropoff | None = None
    note: str | None = None
    payment_preference: str | None = None  # later | now (PR 090)
    checkout_key: str | None = None  # PR 097 P2 — client Place idempotency
    uber_quote_id: str | None = None  # PR 093 — Uber Direct quote
    place: bool = False


class StoreDeliveryQuoteRequest(BaseModel):
    dropoff: StoreDeliveryDropoff = Field(default_factory=StoreDeliveryDropoff)
    dropoff_phone: str | None = None
    subtotal: float | None = None


def _client_key(request: Request) -> str:
    forwarded = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
    if forwarded:
        return forwarded
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/menu")
async def get_menu():
    """Full menu catalog (grouped by category) for the web menu panel."""
    catalog = menu_provider.catalog()
    if catalog is None:
        raise HTTPException(status_code=503, detail="Menu is not available")
    return catalog


@app.get("/store/config")
async def store_config():
    """Public Store flags for the web UI (no secrets)."""
    flags = {
        "pay_now_enabled": store_pay_now_enabled(),
        "channel": STORE_CHANNEL,
    }
    flags.update(public_store_flags())
    return flags


@app.post("/store/delivery-quote")
async def store_delivery_quote(body: StoreDeliveryQuoteRequest, request: Request):
    """Uber Direct Create Quote for Store delivery (PR 093 P1).

    Kill switch off → ok + enabled=False + flat fallback fee (no Uber call).
    """
    if not allow_store_checkout(_client_key(request)):
        raise HTTPException(
            status_code=429,
            detail={
                "ok": False,
                "enabled": store_uber_direct_enabled(),
                "blockers": [
                    "Too many requests. Please wait a minute and try again."
                ],
            },
        )

    result = request_store_delivery_quote(body.model_dump())
    if not result.ok:
        raise HTTPException(status_code=400, detail=result.to_dict())
    return result.to_dict()


@app.post("/store/uber-direct-webhook")
async def store_uber_direct_webhook(request: Request):
    """Authenticate and apply an Uber delivery status event exactly once."""
    if not allow_hco_webhook(_client_key(request)):
        raise HTTPException(status_code=429, detail="Too many webhook requests")

    raw = await request.body()
    secret = webhook_secret()
    if not secret:
        raise HTTPException(
            status_code=503,
            detail="Uber webhook signing key is not configured",
        )
    if not verify_uber_webhook_signature(
        raw,
        secret=secret,
        uber_signature=request.headers.get("x-uber-signature"),
        postmates_signature=request.headers.get("x-postmates-signature"),
    ):
        raise HTTPException(status_code=401, detail="Invalid Uber signature")

    try:
        payload = json.loads(raw.decode("utf-8") or "{}")
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise HTTPException(status_code=400, detail="Invalid JSON") from None

    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Expected JSON object")

    parsed = parse_uber_delivery_webhook(payload)
    if not parsed.get("valid"):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported or malformed Uber webhook: {parsed.get('error')}",
        )

    # Legacy DAPI status events intentionally carry a resource pointer rather
    # than the full delivery. Reconcile optional tracking/cancellation fields
    # only through the documented Uber API host/path; status application does
    # not depend on this best-effort read.
    if parsed.get("shape") == "dapi.status_changed" and parsed.get(
        "resource_href"
    ):
        try:
            resource = await asyncio.to_thread(
                fetch_delivery_resource,
                resource_href=parsed["resource_href"],
            )
            parsed = enrich_parsed_delivery(parsed, resource)
        except Exception as exc:
            logger.warning(
                "UBER_WEBHOOK reconciliation failed event_id=%s err=%s",
                parsed.get("event_id"),
                exc,
            )

    result = apply_delivery_webhook_event(
        event_id=parsed["event_id"],
        event_time_ms=parsed["event_time_ms"],
        delivery_id=parsed["delivery_id"],
        status=parsed["status"],
        shape=parsed["shape"],
        tracking_url=parsed.get("tracking_url"),
        external_id=parsed.get("external_id"),
        cancellation_reason=parsed.get("cancellation_reason"),
        undeliverable_reason=parsed.get("undeliverable_reason"),
        undeliverable_action=parsed.get("undeliverable_action"),
        resource_href=parsed.get("resource_href"),
        related_deliveries=parsed.get("related_deliveries"),
        raw=payload,
    )
    event_record = result.get("event") or {}
    n8n_notified = bool(event_record.get("n8n_notified_at"))
    should_relay = (
        result.get("action") in {"applied", "duplicate"}
        and bool(event_record.get("accepted"))
        and not n8n_notified
        and n8n_sync_enabled()
    )
    if should_relay:
        delivery = result.get("delivery") or get_delivery(parsed["delivery_id"]) or {}
        context = delivery.get("notification_context") or {}
        try:
            n8n_notified = await notify_delivery_status_changed(
                uber_event_id=parsed["event_id"],
                event_time_ms=parsed["event_time_ms"],
                delivery_id=parsed["delivery_id"],
                delivery_status=parsed["status"],
                previous_status=event_record.get("previous_status"),
                customer_milestone=event_record.get("customer_milestone"),
                channel=context.get("channel") or "web_store",
                customer_name=context.get("customer_name"),
                customer_phone=context.get("customer_phone"),
                clover_order_id=(
                    context.get("clover_order_id")
                    or delivery.get("order_key")
                    or parsed.get("external_id")
                ),
                order_type=context.get("order_type") or "delivery",
                tracking_url=delivery.get("tracking_url")
                or parsed.get("tracking_url"),
                total=context.get("total"),
                session_id=context.get("session_id"),
                cancellation_reason=delivery.get("cancellation_reason"),
                undeliverable_reason=delivery.get("undeliverable_reason"),
                undeliverable_action=delivery.get("undeliverable_action"),
                webhook_shape=parsed.get("shape"),
            )
        except Exception:
            logger.exception(
                "UBER_WEBHOOK n8n relay raised event_id=%s",
                parsed["event_id"],
            )
            n8n_notified = False
        notification_record = mark_delivery_event_notification(
            event_id=parsed["event_id"],
            notified=n8n_notified,
            error=None if n8n_notified else "n8n_delivery_status_notify_failed",
        )
        if not n8n_notified or notification_record is None:
            raise HTTPException(
                status_code=502,
                detail="Delivery status saved; downstream notification pending retry",
            )
    return {
        "ok": True,
        "handled": result.get("action") == "applied",
        "action": result.get("action"),
        "delivery_id": parsed["delivery_id"],
        "status": parsed["status"],
        "event_id": parsed["event_id"],
        "n8n_notified": n8n_notified,
    }


@app.get("/store/delivery-status")
async def store_delivery_status(delivery_id: str | None = None):
    """Poll Uber delivery status we recorded from webhooks."""
    if not delivery_id:
        raise HTTPException(status_code=400, detail="delivery_id required")
    rec = get_delivery(delivery_id)
    if not rec:
        return {"found": False, "delivery": None}
    return {"found": True, "delivery": rec}


@app.post("/store/checkout")
async def store_checkout(body: StoreCheckoutRequest, request: Request):
    """Validate Store checkout; place when place=True (S4). Rate-limited (S5)."""
    if not allow_store_checkout(_client_key(request)):
        raise HTTPException(
            status_code=429,
            detail={
                "ok": False,
                "status": "rate_limited",
                "blockers": [
                    "Too many checkout attempts. Please wait a minute and try again."
                ],
            },
        )

    payload = body.model_dump()
    if body.place:
        result = await place_store_order(payload)
    else:
        result = validate_store_checkout(payload)

    if not result.ok:
        status = 400
        if body.place and result.summary and result.blockers and any(
            "kitchen" in b.lower() or "pos" in b.lower() for b in result.blockers
        ):
            status = 502
        raise HTTPException(status_code=status, detail=result.to_dict())

    out = result.to_dict()
    out["place_requested"] = bool(body.place)
    out["placed"] = bool(result.summary and result.summary.get("placed"))
    return out


@app.post("/store/clover-hco-webhook")
async def store_clover_hco_webhook(request: Request):
    """Clover Hosted Checkout payment webhook (P3).

    Configure this HTTPS URL in Clover Merchant Dashboard → Hosted Checkout → Webhook.
    Always returns 200 when signature is valid so Clover does not retry forever on
    business-logic misses; invalid signatures → 401.
    """
    if not allow_hco_webhook(_client_key(request)):
        raise HTTPException(status_code=429, detail="Too many webhook requests")

    raw = await request.body()
    sig = request.headers.get("Clover-Signature") or request.headers.get(
        "clover-signature"
    )
    if not verify_clover_signature(raw_body=raw, signature_header=sig):
        raise HTTPException(status_code=401, detail="Invalid Clover-Signature")

    try:
        import json

        payload = json.loads(raw.decode("utf-8") or "{}")
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON") from None

    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Expected JSON object")

    parsed = parse_hco_webhook_payload(payload)
    status = parsed["status"]
    checkout_session_id = parsed["checkout_session_id"]
    payment_id = parsed["payment_id"]

    if status == "APPROVED" and checkout_session_id and payment_id:
        rec = record_payment_approved(
            checkout_session_id=checkout_session_id,
            payment_id=payment_id,
            merchant_id=parsed.get("merchant_id"),
            message=parsed.get("message"),
            raw=payload,
        )
        # Pay-first: kitchen ticket + confirm SMS only after successful payment.
        try:
            from restaurant.store_checkout import fulfill_store_order_after_payment

            rec = await fulfill_store_order_after_payment(checkout_session_id) or rec
        except Exception:
            import logging

            logging.getLogger("token-server").exception(
                "pay-now kitchen fulfill raised — payment still recorded"
            )
            rec = get_by_checkout_session(checkout_session_id) or rec

        n8n_notified = False
        if rec and not rec.get("n8n_paid_notified_at"):
            try:
                n8n_notified = await notify_order_paid(
                    channel=STORE_CHANNEL,
                    customer_name=rec.get("customer_name"),
                    customer_phone=rec.get("customer_phone"),
                    order_type=rec.get("order_type"),
                    clover_order_id=rec.get("order_id"),
                    payment_id=payment_id,
                    receipt_url=rec.get("receipt_url"),
                    checkout_session_id=checkout_session_id,
                    total=rec.get("total"),
                    session_id=rec.get("sierra_session_id"),
                )
                if n8n_notified:
                    mark_n8n_paid_notified(checkout_session_id)
                    rec = get_by_checkout_session(checkout_session_id) or rec
            except Exception:
                # Fail-open — never break Clover webhook ACK
                import logging

                logging.getLogger("token-server").exception(
                    "order.paid n8n notify raised — ignored"
                )
        return {
            "ok": True,
            "handled": "approved",
            "n8n_notified": n8n_notified,
            "payment": public_payment_view(rec),
        }

    if status == "DECLINED" and checkout_session_id:
        rec = record_payment_declined(
            checkout_session_id=checkout_session_id,
            payment_id=payment_id,
            message=parsed.get("message"),
        )
        return {
            "ok": True,
            "handled": "declined",
            "payment": public_payment_view(rec),
        }

    return {
        "ok": True,
        "handled": "ignored",
        "status": status or None,
    }


@app.get("/store/payment-status")
async def store_payment_status(
    checkout_session_id: str | None = None,
    order_id: str | None = None,
):
    """Poll pay-now status after Hosted Checkout (P3)."""
    rec = None
    if checkout_session_id:
        rec = get_by_checkout_session(checkout_session_id)
    elif order_id:
        rec = get_by_order_id(order_id)
    else:
        raise HTTPException(
            status_code=400,
            detail="Provide checkout_session_id or order_id",
        )
    view = public_payment_view(rec)
    if not view:
        return {"ok": True, "found": False, "payment": None}
    return {"ok": True, "found": True, "payment": view}


@app.get("/token")
async def get_token(room: str = None, identity: str = None):
    room_name = room or f"restaurant-{uuid.uuid4().hex[:8]}"
    user_identity = identity or f"user-{uuid.uuid4().hex[:8]}"

    try:
        token = (
            AccessToken(LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
            .with_identity(user_identity)
            .with_name("Customer")
            .with_grants(VideoGrants(room_join=True, room=room_name))
            .to_jwt()
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    try:
        async with LiveKitAPI(
            url=LIVEKIT_URL,
            api_key=LIVEKIT_API_KEY,
            api_secret=LIVEKIT_API_SECRET,
        ) as lk:
            await lk.agent_dispatch.create_dispatch(
                CreateAgentDispatchRequest(
                    room=room_name,
                    agent_name=os.getenv("AGENT_NAME", "restaurant-agent"),
                )
            )
    except Exception:
        pass

    return {
        "token": token,
        "url": LIVEKIT_URL,
        "room": room_name,
        "identity": user_identity,
    }
