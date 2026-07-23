"""Tests for restaurant.integrations.n8n_webhook."""

from __future__ import annotations

import asyncio
import json
from io import BytesIO
from urllib.error import HTTPError, URLError

import pytest

from restaurant.integrations import n8n_webhook as n8n


def run(coro):
    return asyncio.run(coro)


def test_disabled_by_default(monkeypatch):
    monkeypatch.delenv("N8N_SYNC_ENABLED", raising=False)
    assert n8n.n8n_sync_enabled() is False


def test_enabled_env(monkeypatch):
    monkeypatch.setenv("N8N_SYNC_ENABLED", "1")
    assert n8n.n8n_sync_enabled() is True


def test_phone_e164_nanp():
    assert n8n.phone_to_e164("7805551234") == "+17805551234"
    assert n8n.phone_to_e164("+1 (780) 555-1234") == "+17805551234"


def test_phone_e164_india():
    assert n8n.phone_to_e164("+919413752688") == "+919413752688"
    assert n8n.phone_to_e164("919413752688") == "+919413752688"


def test_envelope_shape():
    env = n8n.build_order_placed_envelope(
        channel="phone",
        customer_name="Aman Singh",
        customer_phone="7805551234",
        order_type="pickup",
        items=[{"name": "Garlic Naan", "qty": 2, "price": 3.5}],
        total=7.0,
        clover_order_id="CLV1",
        clover_submitted=True,
        session_id="sess-1",
        event_id="evt-1",
    )
    assert env["schema_version"] == 1
    assert env["event"] == "order.placed"
    assert env["event_id"] == "evt-1"
    assert env["tenant_id"] == "bizbull"
    assert env["customer"]["phone_e164"] == "+17805551234"
    assert env["order"]["clover_submitted"] is True
    assert env["order"]["status"] == "placed"
    assert env["order"]["items"][0]["name"] == "Garlic Naan"


def test_notify_skipped_when_disabled(monkeypatch):
    monkeypatch.setenv("N8N_SYNC_ENABLED", "0")
    monkeypatch.setenv("N8N_WEBHOOK_ORDERS_URL", "https://example.com/hook")

    def _boom(*a, **k):
        raise AssertionError("must not POST when disabled")

    monkeypatch.setattr(n8n, "_post_json_sync", _boom)
    ok = run(
        n8n.notify_order_placed(
            channel="phone",
            customer_name="Aman",
            customer_phone="7805551234",
            order_type="pickup",
            items=[],
        )
    )
    assert ok is False


def test_notify_posts_envelope(monkeypatch):
    monkeypatch.setenv("N8N_SYNC_ENABLED", "1")
    monkeypatch.setenv("N8N_WEBHOOK_ORDERS_URL", "https://n8n.example/webhook/sierra-ghl-sync")
    monkeypatch.setenv("N8N_WEBHOOK_SECRET", "s3cret")
    seen = {}

    def _fake_post(url, payload, *, secret, timeout):
        seen["url"] = url
        seen["payload"] = payload
        seen["secret"] = secret
        seen["timeout"] = timeout
        return 200

    monkeypatch.setattr(n8n, "_post_json_sync", _fake_post)
    ok = run(
        n8n.notify_order_placed(
            channel="web",
            customer_name="Aman Singh",
            customer_phone="7805551234",
            order_type="delivery",
            items=[{"name": "Butter Chicken", "qty": 1, "price": 16.99}],
            total=16.99,
            clover_order_id="CLV99",
            clover_submitted=True,
            session_id="room-1",
        )
    )
    assert ok is True
    assert seen["url"].endswith("/sierra-ghl-sync")
    assert seen["secret"] == "s3cret"
    assert seen["payload"]["event"] == "order.placed"
    assert seen["payload"]["channel"] == "web"
    assert seen["payload"]["customer"]["phone_e164"] == "+17805551234"
    assert seen["payload"]["order"]["clover_order_id"] == "CLV99"


def test_notify_http_error_fail_open(monkeypatch):
    monkeypatch.setenv("N8N_SYNC_ENABLED", "1")
    monkeypatch.setenv("N8N_WEBHOOK_ORDERS_URL", "https://n8n.example/hook")

    def _fail(*a, **k):
        raise HTTPError("https://x", 500, "err", hdrs=None, fp=BytesIO(b""))

    monkeypatch.setattr(n8n, "_post_json_sync", _fail)
    ok = run(
        n8n.notify_order_placed(
            channel="phone",
            customer_name="Aman",
            customer_phone="7805551234",
            order_type="pickup",
            items=[],
        )
    )
    assert ok is False


def test_notify_network_error_fail_open(monkeypatch):
    monkeypatch.setenv("N8N_SYNC_ENABLED", "1")
    monkeypatch.setenv("N8N_WEBHOOK_ORDERS_URL", "https://n8n.example/hook")

    def _fail(*a, **k):
        raise URLError("timed out")

    monkeypatch.setattr(n8n, "_post_json_sync", _fail)
    ok = run(
        n8n.notify_order_placed(
            channel="phone",
            customer_name="Aman",
            customer_phone="7805551234",
            order_type="pickup",
            items=[],
        )
    )
    assert ok is False


def test_post_json_sync_builds_request(monkeypatch):
    captured = {}

    class _Resp:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def _urlopen(req, timeout=None):
        captured["url"] = req.full_url
        captured["method"] = req.get_method()
        captured["body"] = json.loads(req.data.decode("utf-8"))
        captured["headers"] = dict(req.headers)
        captured["timeout"] = timeout
        return _Resp()

    monkeypatch.setattr(n8n.urllib.request, "urlopen", _urlopen)
    status = n8n._post_json_sync(
        "https://n8n.example/hook",
        {"event": "order.placed"},
        secret="tok",
        timeout=2.5,
    )
    assert status == 200
    assert captured["method"] == "POST"
    assert captured["body"]["event"] == "order.placed"
    assert captured["headers"].get("X-webhook-secret") == "tok" or captured[
        "headers"
    ].get("X-Webhook-Secret") == "tok"
    assert captured["timeout"] == 2.5

def test_order_paid_envelope_shape():
    env = n8n.build_order_paid_envelope(
        channel="web_store",
        customer_name="Alex",
        customer_phone="5875551234",
        order_type="pickup",
        clover_order_id="ORD1",
        payment_id="PAY1",
        receipt_url="https://www.clover.com/r/PAY1",
        checkout_session_id="sess-1",
        total=12.5,
    )
    assert env["event"] == "order.paid"
    assert env["event_id"] == "order.paid:PAY1"
    assert env["order"]["status"] == "paid"
    assert env["order"]["receipt_url"] == "https://www.clover.com/r/PAY1"
    assert env["customer"]["phone_e164"] == "+15875551234"


def test_notify_order_paid_posts(monkeypatch):
    monkeypatch.setenv("N8N_SYNC_ENABLED", "1")
    monkeypatch.setenv("N8N_WEBHOOK_ORDERS_URL", "https://n8n.example/hook")
    captured = {}

    class _Resp:
        status = 202

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def _urlopen(req, timeout=None):
        captured["body"] = json.loads(req.data.decode("utf-8"))
        return _Resp()

    monkeypatch.setattr(n8n.urllib.request, "urlopen", _urlopen)
    ok = run(
        n8n.notify_order_paid(
            channel="web_store",
            customer_name="Alex",
            customer_phone="5875551234",
            clover_order_id="ORD1",
            payment_id="PAY1",
            receipt_url="https://www.clover.com/r/PAY1",
            checkout_session_id="sess-1",
        )
    )
    assert ok is True
    assert captured["body"]["event"] == "order.paid"
    assert captured["body"]["order"]["receipt_url"].endswith("PAY1")


def test_notify_order_paid_skips_without_receipt(monkeypatch):
    monkeypatch.setenv("N8N_SYNC_ENABLED", "1")
    monkeypatch.setenv("N8N_WEBHOOK_ORDERS_URL", "https://n8n.example/hook")
    ok = run(
        n8n.notify_order_paid(
            channel="web_store",
            customer_name="Alex",
            customer_phone="5875551234",
            payment_id="PAY1",
            receipt_url=None,
        )
    )
    assert ok is False
