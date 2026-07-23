"""P2 — Clover Hosted Checkout session builder + store pay-now wiring."""

from __future__ import annotations

import asyncio

from restaurant.clover.hosted_checkout import (
    HostedCheckoutError,
    HostedCheckoutSession,
    build_hosted_checkout_body,
    create_hosted_checkout_session,
)
from restaurant import menu_provider
from restaurant.clover.menu import MenuCache
from restaurant.clover.models import CachedMenuItem, CachedModifierGroup
from restaurant.store_checkout import place_store_order, validate_store_checkout


def _item(iid, name, *, price=500, spice=False):
    groups = []
    if spice:
        groups.append(
            CachedModifierGroup(
                clover_modifier_group_id="spice",
                name="Spice Level",
                min_required=1,
                max_allowed=1,
            )
        )
    return CachedMenuItem(
        clover_item_id=iid,
        name=name,
        speak_as=name,
        voice_line=name,
        speech_mode="english",
        price_cents=price,
        veg=True,
        available=True,
        category_id="",
        category_name="Mains",
        modifier_groups=groups,
    )


def _install_cache(monkeypatch):
    cache = MenuCache(
        [_item("DRINK1", "Sweet Lassi", price=500)],
        tenant_id="test",
        synced_at="now",
    )
    monkeypatch.setattr(menu_provider, "_cache", cache)
    monkeypatch.setattr(menu_provider, "_cache_loaded", True)


def test_build_body_cents_and_delivery():
    body = build_hosted_checkout_body(
        {
            "items": [
                {
                    "name": "Sweet Lassi",
                    "qty": 2,
                    "unit_price": 5.0,
                    "modifiers": [],
                }
            ],
            "customer": {"name": "Alex Singh", "phone": "+15875551234"},
            "delivery_charge": 5.0,
        },
        order_id="ABC123",
    )
    lines = body["shoppingCart"]["lineItems"]
    assert lines[0]["price"] == 500
    assert lines[0]["unitQty"] == 2
    assert "ABC123" in lines[0]["note"]
    assert lines[1]["name"] == "Delivery"
    assert lines[1]["price"] == 500
    assert body["customer"]["firstName"] == "Alex"
    assert body["customer"]["lastName"] == "Singh"
    assert body["customer"]["phoneNumber"] == "5875551234"


def test_build_body_empty_raises():
    try:
        build_hosted_checkout_body({"items": [], "customer": {"name": "A"}})
        assert False, "expected HostedCheckoutError"
    except HostedCheckoutError:
        pass


def test_create_session_parses_href(monkeypatch):
    monkeypatch.setenv("CLOVER_BASE_URL", "https://apisandbox.dev.clover.com")
    monkeypatch.setenv("CLOVER_MID", "TESTMID12345")
    monkeypatch.setenv("CLOVER_ECOM_PRIVATE_TOKEN", "ecom-secret")

    class _Resp:
        def read(self):
            return (
                b'{"href":"https://checkout.example/xyz",'
                b'"checkoutSessionId":"sess-1","expirationTime":1}'
            )

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def _urlopen(req, timeout=30):
        assert "invoicingcheckoutservice/v1/checkouts" in req.full_url
        # urllib may title-case headers; accept either form.
        headers = {k.lower(): v for k, v in req.headers.items()}
        assert headers.get("x-clover-merchant-id") == "TESTMID12345"
        assert "Bearer ecom-secret" in (headers.get("authorization") or "")
        return _Resp()

    monkeypatch.setattr(
        "restaurant.clover.hosted_checkout.urllib.request.urlopen", _urlopen
    )
    session = create_hosted_checkout_session(
        {
            "items": [{"name": "Lassi", "qty": 1, "unit_price": 5.0, "modifiers": []}],
            "customer": {"name": "Alex", "phone": "5875551234"},
            "delivery_charge": 0,
        },
        order_id="ORD1",
    )
    assert session.href == "https://checkout.example/xyz"
    assert session.checkout_session_id == "sess-1"


def test_place_pay_now_sets_checkout_url(monkeypatch):
    _install_cache(monkeypatch)
    monkeypatch.setenv("CLOVER_SUBMIT_ORDERS", "0")
    monkeypatch.setenv("N8N_SYNC_ENABLED", "0")
    monkeypatch.setenv("STORE_PAY_NOW_ENABLED", "1")

    def _fake_create(summary, **kwargs):
        assert summary["payment_preference"] == "now"
        return HostedCheckoutSession(
            href="https://checkout.example/pay",
            checkout_session_id="s1",
        )

    monkeypatch.setattr(
        "restaurant.clover.hosted_checkout.create_hosted_checkout_session",
        _fake_create,
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
    assert result.summary["checkout_url"] == "https://checkout.example/pay"
    assert result.summary["checkout_session_id"] == "s1"


def test_place_pay_now_disabled_no_url(monkeypatch):
    _install_cache(monkeypatch)
    monkeypatch.setenv("CLOVER_SUBMIT_ORDERS", "0")
    monkeypatch.setenv("N8N_SYNC_ENABLED", "0")
    monkeypatch.setenv("STORE_PAY_NOW_ENABLED", "0")

    called = {"n": 0}

    def _fake_create(*_a, **_k):
        called["n"] += 1
        raise AssertionError("should not create when disabled")

    monkeypatch.setattr(
        "restaurant.clover.hosted_checkout.create_hosted_checkout_session",
        _fake_create,
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
    assert result.summary["checkout_url"] is None
    assert called["n"] == 0


def test_place_pay_now_hco_failure_still_places(monkeypatch):
    _install_cache(monkeypatch)
    monkeypatch.setenv("CLOVER_SUBMIT_ORDERS", "0")
    monkeypatch.setenv("N8N_SYNC_ENABLED", "0")
    monkeypatch.setenv("STORE_PAY_NOW_ENABLED", "1")

    def _boom(*_a, **_k):
        raise HostedCheckoutError("sandbox down")

    monkeypatch.setattr(
        "restaurant.clover.hosted_checkout.create_hosted_checkout_session",
        _boom,
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
    assert result.summary["placed"] is True
    assert result.summary["checkout_url"] is None


def test_validate_still_null_checkout_url(monkeypatch):
    _install_cache(monkeypatch)
    result = validate_store_checkout(
        {
            "items": [{"id": "DRINK1", "qty": 1, "modifiers": []}],
            "order_type": "pickup",
            "customer": {"name": "Alex", "phone": "5875551234"},
            "payment_preference": "now",
        }
    )
    assert result.ok
    assert result.summary["checkout_url"] is None
