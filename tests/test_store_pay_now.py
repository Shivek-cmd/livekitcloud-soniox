"""P3 — pay-now store + HCO webhook signature / parse."""

from __future__ import annotations

import hashlib
import hmac
import json

from restaurant.clover.hco_webhook import (
    parse_hco_webhook_payload,
    verify_clover_signature,
)
from restaurant.store_pay_now_store import (
    get_by_checkout_session,
    get_by_order_id,
    public_payment_view,
    receipt_url_for_payment,
    record_payment_approved,
    record_pending_checkout,
)


def test_receipt_url_template(monkeypatch):
    monkeypatch.setenv(
        "CLOVER_RECEIPT_URL_TEMPLATE",
        "https://example.test/r/{payment_id}",
    )
    assert receipt_url_for_payment("PAY123") == "https://example.test/r/PAY123"


def test_record_pending_and_approved(tmp_path, monkeypatch):
    path = tmp_path / "pay.json"
    monkeypatch.setenv("STORE_PAY_NOW_STORE_PATH", str(path))

    record_pending_checkout(
        checkout_session_id="sess-1",
        order_id="ORD-9",
        customer_name="Alex",
        customer_phone="+15875551234",
        total=12.5,
        order_type="pickup",
    )
    pending = get_by_checkout_session("sess-1")
    assert pending is not None
    assert pending["status"] == "pending"
    assert pending["order_id"] == "ORD-9"

    paid = record_payment_approved(
        checkout_session_id="sess-1",
        payment_id="PAY-1",
        merchant_id="MID",
        message="Approved for 1250",
    )
    assert paid is not None
    assert paid["status"] == "paid"
    assert paid["payment_id"] == "PAY-1"
    assert paid["receipt_url"].endswith("PAY-1")
    assert get_by_order_id("ORD-9")["receipt_url"] == paid["receipt_url"]

    view = public_payment_view(paid)
    assert view is not None
    assert "webhook_raw" not in view
    assert view["receipt_url"] == paid["receipt_url"]


def test_parse_hco_payload_title_case():
    parsed = parse_hco_webhook_payload(
        {
            "Status": "APPROVED",
            "Type": "PAYMENT",
            "Id": "pay-abc",
            "Data": "sess-xyz",
            "MerchantId": "m1",
            "Message": "Approved for 100",
        }
    )
    assert parsed["status"] == "APPROVED"
    assert parsed["payment_id"] == "pay-abc"
    assert parsed["checkout_session_id"] == "sess-xyz"


def test_verify_signature_ok(monkeypatch):
    secret = "whsec_test"
    monkeypatch.setenv("CLOVER_HCO_WEBHOOK_SECRET", secret)
    body = b'{"Status":"APPROVED","Id":"p1","Data":"s1"}'
    ts = "1642599079"
    signed = f"{ts}.{body.decode()}".encode()
    digest = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
    header = f"t={ts},v1={digest}"
    assert verify_clover_signature(raw_body=body, signature_header=header) is True


def test_verify_signature_bad(monkeypatch):
    monkeypatch.setenv("CLOVER_HCO_WEBHOOK_SECRET", "whsec_test")
    monkeypatch.delenv("CLOVER_HCO_WEBHOOK_ALLOW_UNSIGNED", raising=False)
    body = b'{"Status":"APPROVED"}'
    assert (
        verify_clover_signature(
            raw_body=body, signature_header="t=1,v1=deadbeef"
        )
        is False
    )


def test_verify_unsigned_allowed(monkeypatch):
    monkeypatch.delenv("CLOVER_HCO_WEBHOOK_SECRET", raising=False)
    monkeypatch.setenv("CLOVER_HCO_WEBHOOK_ALLOW_UNSIGNED", "1")
    assert verify_clover_signature(raw_body=b"{}", signature_header=None) is True


def test_approved_marks_n8n_notified(tmp_path, monkeypatch):
    path = tmp_path / "pay.json"
    monkeypatch.setenv("STORE_PAY_NOW_STORE_PATH", str(path))
    from restaurant.store_pay_now_store import (
        get_by_checkout_session,
        mark_n8n_paid_notified,
        record_payment_approved,
        record_pending_checkout,
    )

    record_pending_checkout(
        checkout_session_id="sess-n8n",
        order_id="ORD-1",
        customer_phone="+15875551234",
        customer_name="Alex",
    )
    record_payment_approved(
        checkout_session_id="sess-n8n",
        payment_id="PAY-9",
    )
    mark_n8n_paid_notified("sess-n8n")
    rec = get_by_checkout_session("sess-n8n")
    assert rec is not None
    assert rec.get("n8n_paid_notified_at")


def test_place_records_pending(monkeypatch, tmp_path):
    """When HCO succeeds, pending mapping is stored for the webhook."""
    from restaurant import menu_provider
    from restaurant.clover.hosted_checkout import HostedCheckoutSession
    from restaurant.clover.menu import MenuCache
    from restaurant.clover.models import CachedMenuItem
    from restaurant.store_checkout import place_store_order
    from restaurant.store_pay_now_store import get_by_checkout_session
    import asyncio

    cache = MenuCache(
        [
            CachedMenuItem(
                clover_item_id="DRINK1",
                name="Sweet Lassi",
                speak_as="Sweet Lassi",
                voice_line="Sweet Lassi",
                speech_mode="english",
                price_cents=500,
                veg=True,
                available=True,
                category_id="",
                category_name="Mains",
                modifier_groups=[],
            )
        ],
        tenant_id="test",
        synced_at="now",
    )
    monkeypatch.setattr(menu_provider, "_cache", cache)
    monkeypatch.setattr(menu_provider, "_cache_loaded", True)
    monkeypatch.setenv("CLOVER_SUBMIT_ORDERS", "0")
    monkeypatch.setenv("N8N_SYNC_ENABLED", "0")
    monkeypatch.setenv("STORE_PAY_NOW_ENABLED", "1")
    monkeypatch.setenv("STORE_PAY_NOW_STORE_PATH", str(tmp_path / "pay.json"))

    monkeypatch.setattr(
        "restaurant.clover.hosted_checkout.create_hosted_checkout_session",
        lambda *_a, **_k: HostedCheckoutSession(
            href="https://checkout.example/x",
            checkout_session_id="sess-live",
        ),
    )

    class _Tenant:
        clover_merchant_id = "MID"
        clover_base_url = "https://apisandbox.dev.clover.com"

    monkeypatch.setattr(
        "restaurant.tenants.config.get_default_tenant",
        lambda: _Tenant(),
    )

    result = asyncio.run(
        place_store_order(
            {
                "items": [{"id": "DRINK1", "qty": 1, "modifiers": []}],
                "order_type": "pickup",
                "customer": {"name": "Alex", "phone": "5875551234"},
                "payment_preference": "now",
            }
        )
    )
    assert result.ok
    assert result.summary["checkout_session_id"] == "sess-live"
    pending = get_by_checkout_session("sess-live")
    assert pending is not None
    assert pending["order_id"] == result.summary["order_id"]
    assert pending["status"] == "pending"
