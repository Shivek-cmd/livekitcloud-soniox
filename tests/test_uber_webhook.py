"""PR 097 P3 — Uber webhook authentication, parsing, and lifecycle ordering."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import asyncio

import pytest
from fastapi import HTTPException

os.environ.setdefault("LIVEKIT_API_KEY", "test")
os.environ.setdefault("LIVEKIT_API_SECRET", "test")
os.environ.setdefault("LIVEKIT_URL", "wss://test.invalid")

import token_server

from restaurant.uber_direct.client import (
    UberDirectError,
    clear_token_cache,
    fetch_delivery,
    fetch_delivery_resource,
)
from restaurant.uber_direct.config import UberDirectCredentials
from restaurant.uber_direct.delivery_store import (
    apply_delivery_webhook_event,
    get_delivery,
    get_delivery_event,
    get_order_dispatch,
    mark_dispatch_success,
)
from restaurant.uber_direct.webhook import (
    enrich_parsed_delivery,
    parse_uber_delivery_webhook,
    verify_uber_webhook_signature,
)


SECRET = "webhook-test-secret"


def _signature(raw: bytes) -> str:
    return hmac.new(SECRET.encode(), raw, hashlib.sha256).hexdigest()


def _modern_event(
    *,
    event_id: str = "evt-1",
    status: str = "pickup",
    created: str = "2026-07-27T12:00:00.000Z",
) -> dict:
    return {
        "id": event_id,
        "kind": "event.delivery_status",
        "created": created,
        "delivery_id": "del-1",
        "status": status,
        "data": {
            "id": "del-1",
            "status": status,
            "external_id": "ORDER-1",
            "tracking_url": "https://tracking.example/del-1",
        },
    }


class _Request:
    def __init__(self, raw: bytes, signature: str | None):
        self._raw = raw
        self.headers = (
            {"x-uber-signature": signature} if signature is not None else {}
        )
        self.client = None

    async def body(self) -> bytes:
        return self._raw


def test_signature_verifies_exact_raw_body_and_both_header_names():
    raw = b'{"note":"escaped \\\\u0026 stays escaped"}'
    signature = _signature(raw)
    assert verify_uber_webhook_signature(
        raw,
        secret=SECRET,
        uber_signature=signature,
    )
    assert verify_uber_webhook_signature(
        raw,
        secret=SECRET,
        postmates_signature=f"sha256={signature}",
    )
    assert not verify_uber_webhook_signature(
        raw.replace(b"escaped", b"changed"),
        secret=SECRET,
        uber_signature=signature,
    )
    assert not verify_uber_webhook_signature(
        raw,
        secret=SECRET,
        uber_signature="bad",
    )
    assert not verify_uber_webhook_signature(raw, secret="", uber_signature=signature)


def test_endpoint_rejects_bad_signature_before_state_mutation(
    monkeypatch, tmp_path
):
    store_path = tmp_path / "deliveries.json"
    monkeypatch.setenv("UBER_DIRECT_WEBHOOK_SECRET", SECRET)
    monkeypatch.setenv("UBER_DIRECT_DELIVERY_STORE_PATH", str(store_path))
    monkeypatch.setattr(token_server, "allow_hco_webhook", lambda _key: True)
    raw = json.dumps(_modern_event(), separators=(",", ":")).encode()

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            token_server.store_uber_direct_webhook(_Request(raw, "0" * 64))
        )
    assert exc.value.status_code == 401
    assert not store_path.exists()


def test_endpoint_applies_valid_signature_and_deduplicates(monkeypatch, tmp_path):
    monkeypatch.setenv("UBER_DIRECT_WEBHOOK_SECRET", SECRET)
    monkeypatch.setenv(
        "UBER_DIRECT_DELIVERY_STORE_PATH", str(tmp_path / "deliveries.json")
    )
    monkeypatch.setattr(token_server, "allow_hco_webhook", lambda _key: True)
    monkeypatch.setattr(token_server, "n8n_sync_enabled", lambda: False)
    raw = json.dumps(_modern_event(), separators=(",", ":")).encode()
    request = _Request(raw, _signature(raw))

    first = asyncio.run(token_server.store_uber_direct_webhook(request))
    second = asyncio.run(token_server.store_uber_direct_webhook(request))
    assert first["action"] == "applied"
    assert first["handled"] is True
    assert second["action"] == "duplicate"
    assert second["handled"] is False


def test_endpoint_retries_pending_n8n_relay_without_reapplying_state(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("UBER_DIRECT_WEBHOOK_SECRET", SECRET)
    monkeypatch.setenv(
        "UBER_DIRECT_DELIVERY_STORE_PATH", str(tmp_path / "deliveries.json")
    )
    monkeypatch.setattr(token_server, "allow_hco_webhook", lambda _key: True)
    monkeypatch.setattr(token_server, "n8n_sync_enabled", lambda: True)
    mark_dispatch_success(
        order_key="ORDER-1",
        delivery_id="del-1",
        status="pending",
        tracking_url="https://tracking.example/del-1",
        notification_context={
            "channel": "web_store",
            "customer_name": "Alex",
            "customer_phone": "+15875551234",
            "clover_order_id": "ORDER-1",
            "order_type": "delivery",
            "total": 25.0,
            "session_id": "session-1",
        },
    )
    relay_calls = []

    async def fake_notify(**kwargs):
        relay_calls.append(kwargs)
        return len(relay_calls) >= 2

    monkeypatch.setattr(
        token_server,
        "notify_delivery_status_changed",
        fake_notify,
    )
    raw = json.dumps(_modern_event(), separators=(",", ":")).encode()
    request = _Request(raw, _signature(raw))

    with pytest.raises(HTTPException) as exc:
        asyncio.run(token_server.store_uber_direct_webhook(request))
    assert exc.value.status_code == 502
    first_event = get_delivery_event("evt-1")
    assert first_event is not None
    assert first_event["n8n_notify_attempts"] == 1
    assert not first_event.get("n8n_notified_at")

    retry = asyncio.run(token_server.store_uber_direct_webhook(request))
    assert retry["action"] == "duplicate"
    assert retry["handled"] is False
    assert retry["n8n_notified"] is True
    notified_event = get_delivery_event("evt-1")
    assert notified_event is not None
    assert notified_event["n8n_notify_attempts"] == 2
    assert notified_event.get("n8n_notified_at")
    assert relay_calls[-1]["customer_name"] == "Alex"
    assert relay_calls[-1]["clover_order_id"] == "ORDER-1"

    duplicate = asyncio.run(token_server.store_uber_direct_webhook(request))
    assert duplicate["n8n_notified"] is True
    assert len(relay_calls) == 2


def test_endpoint_rejects_signed_malformed_payload(monkeypatch, tmp_path):
    monkeypatch.setenv("UBER_DIRECT_WEBHOOK_SECRET", SECRET)
    monkeypatch.setenv(
        "UBER_DIRECT_DELIVERY_STORE_PATH", str(tmp_path / "deliveries.json")
    )
    monkeypatch.setattr(token_server, "allow_hco_webhook", lambda _key: True)
    raw = b'{"kind":"event.delivery_status","data":{}}'

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            token_server.store_uber_direct_webhook(_Request(raw, _signature(raw)))
        )
    assert exc.value.status_code == 400


def test_parse_modern_delivery_status_fields():
    payload = _modern_event(status="canceled")
    payload["data"]["cancelation_reason"] = {
        "primary_reason": "#Uber",
        "secondary_reason": "MERCHANT_CANCEL",
    }
    payload["data"]["undeliverable_reason"] = "merchant_closed"
    parsed = parse_uber_delivery_webhook(payload)
    assert parsed["valid"] is True
    assert parsed["shape"] == "event.delivery_status"
    assert parsed["event_id"] == "evt-1"
    assert parsed["delivery_id"] == "del-1"
    assert parsed["status"] == "canceled"
    assert parsed["external_id"] == "ORDER-1"
    assert parsed["cancellation_reason"] == "MERCHANT_CANCEL"
    assert parsed["undeliverable_reason"] == "merchant_closed"


def test_parse_legacy_status_normalizes_and_requires_known_shape():
    payload = {
        "event_id": "legacy-1",
        "event_type": "dapi.status_changed",
        "event_time": 1_721_000_000_000,
        "resource_href": (
            "https://api.uber.com/v1/eats/deliveries/orders/order-legacy"
        ),
        "meta": {
            "order_id": "order-legacy",
            "external_order_id": "ORDER-LEGACY",
            "status": "EN_ROUTE_TO_DROPOFF",
        },
    }
    parsed = parse_uber_delivery_webhook(payload)
    assert parsed["valid"] is True
    assert parsed["shape"] == "dapi.status_changed"
    assert parsed["status"] == "dropoff"
    assert parsed["external_id"] == "ORDER-LEGACY"

    unsupported = parse_uber_delivery_webhook(
        {"id": "courier-1", "kind": "event.courier_update", "data": {}}
    )
    assert unsupported["valid"] is False
    assert unsupported["error"] == "unsupported_event_shape"


@pytest.mark.parametrize(
    "payload,error",
    [
        (
            {
                "kind": "event.delivery_status",
                "created": "2026-07-27T12:00:00Z",
                "data": {"id": "del-1", "status": "pickup"},
            },
            "missing_event_id",
        ),
        (
            {
                "id": "evt-1",
                "kind": "event.delivery_status",
                "created": "bad-time",
                "data": {"id": "del-1", "status": "pickup"},
            },
            "missing_or_invalid_event_time",
        ),
        (
            {
                "id": "evt-1",
                "kind": "event.delivery_status",
                "created": "2026-07-27T12:00:00Z",
                "data": {"id": "del-1", "status": "invented"},
            },
            "missing_or_unknown_status",
        ),
    ],
)
def test_parse_rejects_malformed_events(payload, error):
    parsed = parse_uber_delivery_webhook(payload)
    assert parsed["valid"] is False
    assert parsed["error"] == error


def test_event_is_applied_once_and_updates_order_mapping(monkeypatch, tmp_path):
    monkeypatch.setenv(
        "UBER_DIRECT_DELIVERY_STORE_PATH", str(tmp_path / "deliveries.json")
    )
    parsed = parse_uber_delivery_webhook(_modern_event())
    first = apply_delivery_webhook_event(**{
        key: parsed.get(key)
        for key in (
            "event_id",
            "event_time_ms",
            "delivery_id",
            "status",
            "shape",
            "tracking_url",
            "external_id",
            "cancellation_reason",
            "undeliverable_reason",
            "undeliverable_action",
            "resource_href",
            "related_deliveries",
        )
    })
    second = apply_delivery_webhook_event(**{
        key: parsed.get(key)
        for key in (
            "event_id",
            "event_time_ms",
            "delivery_id",
            "status",
            "shape",
        )
    })
    assert first["action"] == "applied"
    assert second["action"] == "duplicate"
    delivery = get_delivery("del-1")
    assert delivery is not None
    assert delivery["status"] == "pickup"
    assert delivery["external_id"] == "ORDER-1"
    assert get_order_dispatch("ORDER-1")["status"] == "pickup"


def test_out_of_order_and_terminal_regressions_are_ignored(monkeypatch, tmp_path):
    monkeypatch.setenv(
        "UBER_DIRECT_DELIVERY_STORE_PATH", str(tmp_path / "deliveries.json")
    )
    applied = apply_delivery_webhook_event(
        event_id="evt-dropoff",
        event_time_ms=2_000,
        delivery_id="del-2",
        status="dropoff",
        shape="event.delivery_status",
    )
    older = apply_delivery_webhook_event(
        event_id="evt-pickup",
        event_time_ms=1_000,
        delivery_id="del-2",
        status="pickup",
        shape="event.delivery_status",
    )
    delivered = apply_delivery_webhook_event(
        event_id="evt-delivered",
        event_time_ms=3_000,
        delivery_id="del-2",
        status="delivered",
        shape="event.delivery_status",
    )
    terminal_regression = apply_delivery_webhook_event(
        event_id="evt-late-dropoff",
        event_time_ms=4_000,
        delivery_id="del-2",
        status="dropoff",
        shape="event.delivery_status",
    )
    assert applied["action"] == "applied"
    assert older["reason"] == "older_event_time"
    assert delivered["action"] == "applied"
    assert terminal_regression["reason"] == "terminal_state"
    assert get_delivery("del-2")["status"] == "delivered"


def test_canceled_delivery_can_progress_to_returned(monkeypatch, tmp_path):
    monkeypatch.setenv(
        "UBER_DIRECT_DELIVERY_STORE_PATH", str(tmp_path / "deliveries.json")
    )
    apply_delivery_webhook_event(
        event_id="evt-canceled",
        event_time_ms=1_000,
        delivery_id="del-return",
        status="canceled",
        shape="event.delivery_status",
        cancellation_reason="COURIER_CANCEL",
    )
    result = apply_delivery_webhook_event(
        event_id="evt-returned",
        event_time_ms=2_000,
        delivery_id="del-return",
        status="returned",
        shape="event.delivery_status",
        undeliverable_action="return",
        undeliverable_reason="customer_unavailable",
    )
    assert result["action"] == "applied"
    delivery = get_delivery("del-return")
    assert delivery["status"] == "returned"
    assert delivery["cancellation_reason"] == "COURIER_CANCEL"
    assert delivery["undeliverable_reason"] == "customer_unavailable"


def test_customer_on_the_way_milestone_is_emitted_once(monkeypatch, tmp_path):
    monkeypatch.setenv(
        "UBER_DIRECT_DELIVERY_STORE_PATH", str(tmp_path / "deliveries.json")
    )
    pickup_complete = apply_delivery_webhook_event(
        event_id="evt-pickup-complete",
        event_time_ms=1_000,
        delivery_id="del-milestone",
        status="pickup_complete",
        shape="event.delivery_status",
    )
    dropoff = apply_delivery_webhook_event(
        event_id="evt-dropoff",
        event_time_ms=2_000,
        delivery_id="del-milestone",
        status="dropoff",
        shape="event.delivery_status",
    )
    direct_dropoff = apply_delivery_webhook_event(
        event_id="evt-direct-dropoff",
        event_time_ms=1_000,
        delivery_id="del-direct-dropoff",
        status="dropoff",
        shape="event.delivery_status",
    )
    assert pickup_complete["event"]["customer_milestone"] == "on_the_way"
    assert dropoff["event"]["customer_milestone"] is None
    assert direct_dropoff["event"]["customer_milestone"] == "on_the_way"


def test_legacy_resource_enrichment_and_url_allowlist(monkeypatch):
    parsed = {
        "tracking_url": None,
        "external_id": "ORDER-1",
        "cancellation_reason": None,
        "undeliverable_reason": None,
        "undeliverable_action": None,
        "related_deliveries": None,
    }
    enriched = enrich_parsed_delivery(
        parsed,
        {
            "order_tracking_url": "https://tracking.example/legacy",
            "external_order_id": "WRONG-SHOULD-NOT-OVERRIDE",
            "undeliverable_reason": "customer_unavailable",
        },
    )
    assert enriched["tracking_url"] == "https://tracking.example/legacy"
    assert enriched["external_id"] == "ORDER-1"
    assert enriched["undeliverable_reason"] == "customer_unavailable"

    creds = UberDirectCredentials("customer", "client", "secret")
    with pytest.raises(UberDirectError, match="Unsafe"):
        fetch_delivery_resource(
            resource_href="https://attacker.example/v1/eats/deliveries/orders/1",
            creds=creds,
        )


def test_get_delivery_uses_known_id_and_legacy_resource_is_host_limited(monkeypatch):
    clear_token_cache()
    calls = []

    def fake_request(method, url, **kwargs):
        calls.append((method, url))
        if "oauth" in url:
            return {"access_token": "token", "expires_in": 3600}
        return {"id": "del/encoded", "status": "pickup"}

    monkeypatch.setattr(
        "restaurant.uber_direct.client._request_json",
        fake_request,
    )
    creds = UberDirectCredentials("customer", "client", "secret")
    fetched = fetch_delivery(delivery_id="del/encoded", creds=creds)
    legacy = fetch_delivery_resource(
        resource_href=(
            "https://api.uber.com/v1/eats/deliveries/orders/order-legacy"
        ),
        creds=creds,
    )
    assert fetched["status"] == "pickup"
    assert legacy["status"] == "pickup"
    assert calls[1] == (
        "GET",
        "https://api.uber.com/v1/customers/customer/deliveries/del%2Fencoded",
    )
    assert calls[2] == (
        "GET",
        "https://api.uber.com/v1/eats/deliveries/orders/order-legacy",
    )
