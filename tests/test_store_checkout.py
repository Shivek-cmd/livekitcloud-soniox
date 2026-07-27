"""S3 — Store checkout validate + reprice (no place)."""

from restaurant import menu_provider
from restaurant.clover.menu import MenuCache
from restaurant.clover.models import CachedMenuItem, CachedModifierGroup
from restaurant.menu import DELIVERY_CHARGE
from restaurant.store_checkout import validate_store_checkout


def _delivery_dropoff(**overrides):
    out = {
        "street": "123 Main St",
        "unit": None,
        "city": "Edmonton",
        "state": "AB",
        "postal": "T5J 0N3",
        "country": "CA",
    }
    out.update(overrides)
    return out


def _item(
    iid,
    name,
    *,
    price=1999,
    available=True,
    spice=False,
):
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
        available=available,
        category_id="",
        category_name="Mains",
        modifier_groups=groups,
    )


def _install_cache(monkeypatch):
    cache = MenuCache(
        [
            _item("DRINK1", "Sweet Lassi", price=500),
            _item("BC1", "Butter Chicken", price=1999, spice=True),
            _item("GONE", "Sold Out Special", available=False),
        ],
        tenant_id="test",
        synced_at="now",
    )
    monkeypatch.setattr(menu_provider, "_cache", cache)
    monkeypatch.setattr(menu_provider, "_cache_loaded", True)
    return cache


def test_validate_pickup_ok(monkeypatch):
    _install_cache(monkeypatch)
    result = validate_store_checkout(
        {
            "items": [{"id": "DRINK1", "qty": 2, "modifiers": []}],
            "order_type": "pickup",
            "customer": {"name": "Alex", "phone": "5875551234"},
        }
    )
    assert result.ok
    assert result.status == "validated"
    assert result.summary["subtotal"] == 10.0
    assert result.summary["delivery_charge"] == 0
    assert result.summary["total"] == 10.0
    assert result.summary["customer"]["phone"] == "+15875551234"
    assert result.summary["placed"] is False


def test_validate_delivery_adds_charge(monkeypatch):
    _install_cache(monkeypatch)
    result = validate_store_checkout(
        {
            "items": [{"id": "DRINK1", "qty": 1, "modifiers": []}],
            "order_type": "delivery",
            "customer": {"name": "Alex", "phone": "+15875551234"},
            "delivery_address": "123 Main St, Calgary",
        }
    )
    assert result.ok
    assert result.summary["delivery_charge"] == float(DELIVERY_CHARGE)
    assert result.summary["total"] == round(5.0 + float(DELIVERY_CHARGE), 2)


def test_validate_delivery_uses_uber_quote_when_enabled(monkeypatch, tmp_path):
    _install_cache(monkeypatch)
    monkeypatch.setenv("STORE_UBER_DIRECT_ENABLED", "1")
    monkeypatch.setenv("UBER_DIRECT_QUOTE_STORE_PATH", str(tmp_path / "quotes.json"))
    from restaurant.uber_direct.address import validate_structured_address
    from restaurant.uber_direct.quote_store import record_quote

    dropoff, blockers = validate_structured_address(**_delivery_dropoff())
    assert blockers == []
    assert dropoff is not None
    record_quote(
        quote_id="dqt_live",
        fee_cents=840,
        currency="CAD",
        expires_at="2099-01-01T00:00:00Z",
        dropoff_line="123 Main St, Edmonton, AB T5J 0N3, CA",
        dropoff=_delivery_dropoff(),
        dropoff_address=dropoff,
    )
    result = validate_store_checkout(
        {
            "items": [{"id": "DRINK1", "qty": 1, "modifiers": []}],
            "order_type": "delivery",
            "customer": {"name": "Alex", "phone": "+15875551234"},
            "delivery_address": "123 Main St, Edmonton, AB T5J 0N3, CA",
            "delivery_dropoff": _delivery_dropoff(
                street="  123   MAIN st ",
                state="ab",
                postal="t5j0n3",
            ),
            "uber_quote_id": "dqt_live",
        }
    )
    assert result.ok
    assert result.summary["delivery_charge"] == 8.4
    assert result.summary["uber_quote_applied"] is True
    assert result.summary["uber_quote_id"] == "dqt_live"
    assert result.summary["total"] == round(5.0 + 8.4, 2)
    assert (
        result.summary["delivery_address"]
        == "123 MAIN st, Edmonton, AB T5J 0N3, CA"
    )
    assert result.summary["delivery_dropoff"]["postal"] == "T5J 0N3"


def test_validate_delivery_rejects_missing_uber_quote(monkeypatch):
    _install_cache(monkeypatch)
    monkeypatch.setenv("STORE_UBER_DIRECT_ENABLED", "1")
    result = validate_store_checkout(
        {
            "items": [{"id": "DRINK1", "qty": 1, "modifiers": []}],
            "order_type": "delivery",
            "customer": {"name": "Alex", "phone": "+15875551234"},
            "delivery_dropoff": _delivery_dropoff(),
        }
    )
    assert not result.ok
    assert any("fresh uber delivery quote" in b.lower() for b in result.blockers)


def test_validate_delivery_rejects_address_changed_after_quote(
    monkeypatch, tmp_path
):
    _install_cache(monkeypatch)
    monkeypatch.setenv("STORE_UBER_DIRECT_ENABLED", "1")
    monkeypatch.setenv("UBER_DIRECT_QUOTE_STORE_PATH", str(tmp_path / "quotes.json"))
    from restaurant.uber_direct.address import validate_structured_address
    from restaurant.uber_direct.quote_store import record_quote

    quoted, blockers = validate_structured_address(**_delivery_dropoff())
    assert blockers == []
    assert quoted is not None
    record_quote(
        quote_id="dqt_address_a",
        fee_cents=840,
        currency="CAD",
        expires_at="2099-01-01T00:00:00Z",
        dropoff=_delivery_dropoff(),
        dropoff_address=quoted,
    )

    result = validate_store_checkout(
        {
            "items": [{"id": "DRINK1", "qty": 1, "modifiers": []}],
            "order_type": "delivery",
            "customer": {"name": "Alex", "phone": "+15875551234"},
            "delivery_dropoff": _delivery_dropoff(street="999 Other Ave"),
            "uber_quote_id": "dqt_address_a",
        }
    )
    assert not result.ok
    assert any("address changed" in b.lower() for b in result.blockers)


def test_validate_delivery_rejects_unverifiable_legacy_quote(monkeypatch, tmp_path):
    _install_cache(monkeypatch)
    monkeypatch.setenv("STORE_UBER_DIRECT_ENABLED", "1")
    monkeypatch.setenv("UBER_DIRECT_QUOTE_STORE_PATH", str(tmp_path / "quotes.json"))
    from restaurant.uber_direct.quote_store import record_quote

    record_quote(
        quote_id="dqt_no_binding",
        fee_cents=840,
        currency="CAD",
        expires_at="2099-01-01T00:00:00Z",
    )
    result = validate_store_checkout(
        {
            "items": [{"id": "DRINK1", "qty": 1, "modifiers": []}],
            "order_type": "delivery",
            "customer": {"name": "Alex", "phone": "+15875551234"},
            "delivery_dropoff": _delivery_dropoff(),
            "uber_quote_id": "dqt_no_binding",
        }
    )
    assert not result.ok
    assert any("cannot be verified" in b.lower() for b in result.blockers)


def test_validate_delivery_rejects_expired_quote(monkeypatch, tmp_path):
    _install_cache(monkeypatch)
    monkeypatch.setenv("STORE_UBER_DIRECT_ENABLED", "1")
    monkeypatch.setenv("UBER_DIRECT_QUOTE_STORE_PATH", str(tmp_path / "quotes.json"))
    from restaurant.uber_direct.address import validate_structured_address
    from restaurant.uber_direct.quote_store import record_quote

    quoted, blockers = validate_structured_address(**_delivery_dropoff())
    assert blockers == []
    assert quoted is not None
    record_quote(
        quote_id="dqt_expired",
        fee_cents=840,
        currency="CAD",
        expires_at="2020-01-01T00:00:00Z",
        dropoff=_delivery_dropoff(),
        dropoff_address=quoted,
    )
    result = validate_store_checkout(
        {
            "items": [{"id": "DRINK1", "qty": 1, "modifiers": []}],
            "order_type": "delivery",
            "customer": {"name": "Alex", "phone": "+15875551234"},
            "delivery_dropoff": _delivery_dropoff(),
            "uber_quote_id": "dqt_expired",
        }
    )
    assert not result.ok
    assert any("expired" in b.lower() for b in result.blockers)


def test_spice_required(monkeypatch):
    _install_cache(monkeypatch)
    result = validate_store_checkout(
        {
            "items": [{"id": "BC1", "qty": 1, "modifiers": []}],
            "order_type": "pickup",
            "customer": {"name": "Alex", "phone": "5875551234"},
        }
    )
    assert not result.ok
    assert any("spice" in b.lower() for b in result.blockers)


def test_spice_accepted(monkeypatch):
    _install_cache(monkeypatch)
    result = validate_store_checkout(
        {
            "items": [{"id": "BC1", "qty": 1, "modifiers": ["Medium"]}],
            "order_type": "pickup",
            "customer": {"name": "Alex", "phone": "5875551234"},
        }
    )
    assert result.ok
    assert result.summary["items"][0]["modifiers"] == ["Medium"]
    assert result.summary["items"][0]["unit_price"] == 19.99


def test_ignores_client_price(monkeypatch):
    _install_cache(monkeypatch)
    result = validate_store_checkout(
        {
            "items": [
                {
                    "id": "DRINK1",
                    "qty": 1,
                    "modifiers": [],
                    "unit_price": 0.01,
                }
            ],
            "order_type": "pickup",
            "customer": {"name": "Alex", "phone": "5875551234"},
        }
    )
    assert result.ok
    assert result.summary["items"][0]["unit_price"] == 5.0


def test_empty_cart_and_missing_fields(monkeypatch):
    _install_cache(monkeypatch)
    result = validate_store_checkout({"items": [], "order_type": "", "customer": {}})
    assert not result.ok
    joined = " ".join(result.blockers).lower()
    assert "empty" in joined
    assert "pickup" in joined or "delivery" in joined
    assert "name" in joined
    assert "phone" in joined


def test_delivery_needs_address(monkeypatch):
    _install_cache(monkeypatch)
    result = validate_store_checkout(
        {
            "items": [{"id": "DRINK1", "qty": 1, "modifiers": []}],
            "order_type": "delivery",
            "customer": {"name": "Alex", "phone": "5875551234"},
            "delivery_address": "",
        }
    )
    assert not result.ok
    assert any("address" in b.lower() for b in result.blockers)


def test_sold_out(monkeypatch):
    _install_cache(monkeypatch)
    result = validate_store_checkout(
        {
            "items": [{"id": "GONE", "qty": 1, "modifiers": []}],
            "order_type": "pickup",
            "customer": {"name": "Alex", "phone": "5875551234"},
        }
    )
    assert not result.ok
    assert any("sold out" in b.lower() for b in result.blockers)


def test_unknown_id(monkeypatch):
    _install_cache(monkeypatch)
    result = validate_store_checkout(
        {
            "items": [{"id": "NOPE", "qty": 1, "modifiers": []}],
            "order_type": "pickup",
            "customer": {"name": "Alex", "phone": "5875551234"},
        }
    )
    assert not result.ok
    assert any("unknown" in b.lower() for b in result.blockers)


def test_place_log_only_when_clover_off(monkeypatch):
    _install_cache(monkeypatch)
    monkeypatch.setenv("CLOVER_SUBMIT_ORDERS", "0")
    monkeypatch.setenv("N8N_SYNC_ENABLED", "0")
    import asyncio
    from restaurant.store_checkout import place_store_order

    result = asyncio.run(
        place_store_order(
            {
                "items": [{"id": "DRINK1", "qty": 1, "modifiers": []}],
                "order_type": "pickup",
                "customer": {"name": "Alex", "phone": "5875551234"},
            }
        )
    )
    assert result.ok
    assert result.status == "placed"
    assert result.summary["placed"] is True
    assert str(result.summary["order_id"]).startswith("LOG-")
    assert result.summary["clover_submitted"] is False
    assert result.summary["eta"]


def test_place_clover_failure_fail_closed(monkeypatch):
    _install_cache(monkeypatch)
    monkeypatch.setenv("CLOVER_SUBMIT_ORDERS", "1")
    monkeypatch.setenv("N8N_SYNC_ENABLED", "0")

    from restaurant.clover.order_submit import CloverOrderSubmitError
    from restaurant.tenants import config as tenant_config
    import asyncio
    from restaurant.store_checkout import place_store_order

    def _boom(*_a, **_k):
        raise CloverOrderSubmitError("checkout rejected")

    monkeypatch.setattr(tenant_config, "get_default_tenant", lambda: object())
    monkeypatch.setattr(
        "restaurant.clover.order_submit.submit_cart_to_clover",
        _boom,
    )

    result = asyncio.run(
        place_store_order(
            {
                "items": [{"id": "DRINK1", "qty": 1, "modifiers": []}],
                "order_type": "pickup",
                "customer": {"name": "Alex", "phone": "5875551234"},
            }
        )
    )
    assert not result.ok
    assert any("kitchen" in b.lower() for b in result.blockers)
    assert result.summary["placed"] is False


def test_place_notifies_n8n(monkeypatch):
    _install_cache(monkeypatch)
    monkeypatch.setenv("CLOVER_SUBMIT_ORDERS", "0")
    monkeypatch.setenv("N8N_SYNC_ENABLED", "1")
    calls: list[dict] = []

    async def _fake_notify(**kwargs):
        calls.append(kwargs)
        return True

    monkeypatch.setattr(
        "restaurant.integrations.n8n_webhook.notify_order_placed",
        _fake_notify,
    )
    import asyncio
    from restaurant.store_checkout import place_store_order

    result = asyncio.run(
        place_store_order(
            {
                "items": [{"id": "DRINK1", "qty": 1, "modifiers": []}],
                "order_type": "pickup",
                "customer": {"name": "Alex", "phone": "5875551234"},
            }
        )
    )
    assert result.ok
    assert len(calls) == 1
    assert calls[0]["channel"] == "web_store"
    assert calls[0]["customer_name"] == "Alex"


def test_payment_preference_defaults_to_later(monkeypatch):
    _install_cache(monkeypatch)
    result = validate_store_checkout(
        {
            "items": [{"id": "DRINK1", "qty": 1, "modifiers": []}],
            "order_type": "pickup",
            "customer": {"name": "Alex", "phone": "5875551234"},
        }
    )
    assert result.ok
    assert result.summary["payment_preference"] == "later"
    assert result.summary["checkout_url"] is None


def test_payment_preference_now_echoed(monkeypatch):
    _install_cache(monkeypatch)
    result = validate_store_checkout(
        {
            "items": [{"id": "DRINK1", "qty": 1, "modifiers": []}],
            "order_type": "delivery",
            "customer": {"name": "Alex", "phone": "5875551234"},
            "delivery_address": "123 Main St, Calgary",
            "payment_preference": "now",
        }
    )
    assert result.ok
    assert result.summary["payment_preference"] == "now"
    assert result.summary["checkout_url"] is None


def test_payment_preference_alias_pay_later(monkeypatch):
    _install_cache(monkeypatch)
    result = validate_store_checkout(
        {
            "items": [{"id": "DRINK1", "qty": 1, "modifiers": []}],
            "order_type": "pickup",
            "customer": {"name": "Alex", "phone": "5875551234"},
            "payment_preference": "pay-later",
        }
    )
    assert result.ok
    assert result.summary["payment_preference"] == "later"


def test_payment_preference_invalid(monkeypatch):
    _install_cache(monkeypatch)
    result = validate_store_checkout(
        {
            "items": [{"id": "DRINK1", "qty": 1, "modifiers": []}],
            "order_type": "pickup",
            "customer": {"name": "Alex", "phone": "5875551234"},
            "payment_preference": "bitcoin",
        }
    )
    assert not result.ok
    assert any("pay" in b.lower() for b in result.blockers)


def test_place_keeps_payment_preference(monkeypatch):
    _install_cache(monkeypatch)
    monkeypatch.setenv("CLOVER_SUBMIT_ORDERS", "0")
    monkeypatch.setenv("N8N_SYNC_ENABLED", "0")
    monkeypatch.setenv("STORE_PAY_NOW_ENABLED", "0")
    import asyncio
    from restaurant.store_checkout import place_store_order

    result = asyncio.run(
        place_store_order(
            {
                "items": [{"id": "DRINK1", "qty": 1, "modifiers": []}],
                "order_type": "pickup",
                "customer": {"name": "Alex", "phone": "5875551234"},
                "payment_preference": "later",
            }
        )
    )
    assert result.ok
    assert result.summary["payment_preference"] == "later"
    assert result.status == "placed"


def test_place_checkout_key_replays_without_second_kitchen_order(
    monkeypatch, tmp_path
):
    _install_cache(monkeypatch)
    monkeypatch.setenv("N8N_SYNC_ENABLED", "0")
    monkeypatch.setenv(
        "STORE_CHECKOUT_IDEMPOTENCY_PATH", str(tmp_path / "checkout.json")
    )
    import asyncio
    from restaurant.store_checkout import place_store_order

    calls = {"n": 0}

    async def fake_submit(_summary, *, session_id):
        calls["n"] += 1
        return "ORDER-IDEMPOTENT", []

    monkeypatch.setattr("restaurant.store_checkout._submit_kitchen", fake_submit)
    payload = {
        "items": [{"id": "DRINK1", "qty": 1, "modifiers": []}],
        "order_type": "pickup",
        "customer": {"name": "Alex", "phone": "5875551234"},
        "payment_preference": "later",
        "checkout_key": "checkout_replay_123456",
    }
    first = asyncio.run(place_store_order(payload))
    second = asyncio.run(place_store_order(payload))
    assert first.ok and second.ok
    assert first.summary == second.summary
    assert first.summary["order_id"] == "ORDER-IDEMPOTENT"
    assert calls["n"] == 1


def test_place_checkout_key_rejects_different_order(monkeypatch, tmp_path):
    _install_cache(monkeypatch)
    monkeypatch.setenv("N8N_SYNC_ENABLED", "0")
    monkeypatch.setenv(
        "STORE_CHECKOUT_IDEMPOTENCY_PATH", str(tmp_path / "checkout.json")
    )
    import asyncio
    from restaurant.store_checkout import place_store_order

    calls = {"n": 0}

    async def fake_submit(_summary, *, session_id):
        calls["n"] += 1
        return "ORDER-ONE", []

    monkeypatch.setattr("restaurant.store_checkout._submit_kitchen", fake_submit)
    base = {
        "items": [{"id": "DRINK1", "qty": 1, "modifiers": []}],
        "order_type": "pickup",
        "customer": {"name": "Alex", "phone": "5875551234"},
        "checkout_key": "checkout_conflict_12345",
    }
    first = asyncio.run(place_store_order(base))
    changed = {
        **base,
        "items": [{"id": "DRINK1", "qty": 2, "modifiers": []}],
    }
    second = asyncio.run(place_store_order(changed))
    assert first.ok
    assert not second.ok
    assert any("different order details" in b.lower() for b in second.blockers)
    assert calls["n"] == 1


def test_pay_later_dispatch_failure_emits_staff_alert(monkeypatch, tmp_path):
    _install_cache(monkeypatch)
    monkeypatch.setenv("STORE_UBER_DIRECT_ENABLED", "1")
    monkeypatch.setenv("UBER_DIRECT_QUOTE_STORE_PATH", str(tmp_path / "quotes.json"))
    monkeypatch.setenv(
        "STORE_CHECKOUT_IDEMPOTENCY_PATH", str(tmp_path / "checkout.json")
    )
    import asyncio
    from restaurant.store_checkout import place_store_order
    from restaurant.uber_direct.address import validate_structured_address
    from restaurant.uber_direct.quote_store import record_quote

    quoted, blockers = validate_structured_address(**_delivery_dropoff())
    assert blockers == []
    assert quoted is not None
    record_quote(
        quote_id="dqt_alert",
        fee_cents=840,
        currency="CAD",
        expires_at="2099-01-01T00:00:00Z",
        dropoff_address=quoted,
    )

    async def fake_submit(_summary, *, session_id):
        return "ORDER-ALERT", []

    def fake_dispatch(summary):
        summary.update(
            {
                "uber_dispatch_state": "dispatch_required",
                "uber_dispatch_required": True,
                "uber_dispatch_reason": "uber_create_outcome_unknown",
                "uber_dispatch_uncertain": True,
                "uber_dispatch_attempts": 1,
            }
        )
        return {
            "ok": False,
            "dispatch_state": "dispatch_required",
            "reused": False,
        }

    alerts = []
    placed_events = []

    async def fake_alert(**kwargs):
        alerts.append(kwargs)
        return True

    async def fake_placed(**kwargs):
        placed_events.append(kwargs)
        return True

    monkeypatch.setattr("restaurant.store_checkout._submit_kitchen", fake_submit)
    monkeypatch.setattr(
        "restaurant.uber_direct.service.dispatch_store_delivery", fake_dispatch
    )
    monkeypatch.setattr(
        "restaurant.integrations.n8n_webhook.notify_delivery_dispatch_required",
        fake_alert,
    )
    monkeypatch.setattr(
        "restaurant.integrations.n8n_webhook.notify_order_placed", fake_placed
    )
    result = asyncio.run(
        place_store_order(
            {
                "items": [{"id": "DRINK1", "qty": 1, "modifiers": []}],
                "order_type": "delivery",
                "customer": {"name": "Alex", "phone": "5875551234"},
                "delivery_dropoff": _delivery_dropoff(),
                "uber_quote_id": "dqt_alert",
                "payment_preference": "later",
                "checkout_key": "checkout_alert_123456",
            }
        )
    )
    assert result.ok
    assert result.summary["placed"] is True
    assert result.summary["uber_dispatch_required"] is True
    assert len(alerts) == 1
    assert alerts[0]["order_key"] == "ORDER-ALERT"
    assert alerts[0]["uncertain_outcome"] is True
    assert placed_events[0]["delivery_fulfillment_status"] == "dispatch_required"


def test_pay_now_awaits_payment_before_kitchen(monkeypatch, tmp_path):
    _install_cache(monkeypatch)
    monkeypatch.setenv("CLOVER_SUBMIT_ORDERS", "0")
    monkeypatch.setenv("N8N_SYNC_ENABLED", "0")
    monkeypatch.setenv("STORE_PAY_NOW_ENABLED", "1")
    monkeypatch.setenv("STORE_PAY_NOW_STORE_PATH", str(tmp_path / "pay.json"))
    monkeypatch.setenv(
        "STORE_CHECKOUT_IDEMPOTENCY_PATH", str(tmp_path / "checkout.json")
    )
    import asyncio
    from restaurant.clover.hosted_checkout import HostedCheckoutSession
    from restaurant.store_checkout import place_store_order
    from restaurant.store_pay_now_store import get_by_checkout_session

    hco_calls = {"n": 0}

    def fake_hco(*_a, **_k):
        hco_calls["n"] += 1
        return HostedCheckoutSession(
            href="https://checkout.example/x",
            checkout_session_id="sess-pay",
        )

    monkeypatch.setattr(
        "restaurant.clover.hosted_checkout.create_hosted_checkout_session",
        fake_hco,
    )

    class _Tenant:
        clover_merchant_id = "MID"
        clover_base_url = "https://apisandbox.dev.clover.com"

    monkeypatch.setattr(
        "restaurant.tenants.config.get_default_tenant",
        lambda: _Tenant(),
    )

    n8n_calls: list = []

    async def _fake_notify(**kwargs):
        n8n_calls.append(kwargs)
        return True

    monkeypatch.setattr(
        "restaurant.integrations.n8n_webhook.notify_order_placed",
        _fake_notify,
    )

    payload = {
        "items": [{"id": "DRINK1", "qty": 1, "modifiers": []}],
        "order_type": "pickup",
        "customer": {"name": "Alex", "phone": "5875551234"},
        "payment_preference": "now",
        "checkout_key": "checkout_pay_now_12345",
    }
    result = asyncio.run(place_store_order(payload))
    replay = asyncio.run(place_store_order(payload))
    assert result.ok
    assert result.status == "awaiting_payment"
    assert result.summary["placed"] is False
    assert result.summary["order_id"] is None
    assert result.summary["checkout_url"] == "https://checkout.example/x"
    assert replay.summary == result.summary
    assert hco_calls["n"] == 1
    assert n8n_calls == []
    pending = get_by_checkout_session("sess-pay")
    assert pending is not None
    assert pending["order_id"] is None
    assert isinstance(pending.get("place_summary"), dict)


def test_pay_now_preserves_bound_delivery_dropoff(monkeypatch, tmp_path):
    _install_cache(monkeypatch)
    monkeypatch.setenv("CLOVER_SUBMIT_ORDERS", "0")
    monkeypatch.setenv("N8N_SYNC_ENABLED", "0")
    monkeypatch.setenv("STORE_PAY_NOW_ENABLED", "1")
    monkeypatch.setenv("STORE_UBER_DIRECT_ENABLED", "1")
    monkeypatch.setenv("STORE_PAY_NOW_STORE_PATH", str(tmp_path / "pay.json"))
    monkeypatch.setenv("UBER_DIRECT_QUOTE_STORE_PATH", str(tmp_path / "quotes.json"))
    import asyncio
    from restaurant.clover.hosted_checkout import HostedCheckoutSession
    from restaurant.store_checkout import place_store_order
    from restaurant.store_pay_now_store import get_by_checkout_session
    from restaurant.uber_direct.address import validate_structured_address
    from restaurant.uber_direct.quote_store import record_quote

    quoted, blockers = validate_structured_address(**_delivery_dropoff())
    assert blockers == []
    assert quoted is not None
    record_quote(
        quote_id="dqt_pay_now",
        fee_cents=840,
        currency="CAD",
        expires_at="2099-01-01T00:00:00Z",
        dropoff=_delivery_dropoff(),
        dropoff_address=quoted,
    )
    monkeypatch.setattr(
        "restaurant.clover.hosted_checkout.create_hosted_checkout_session",
        lambda *_a, **_k: HostedCheckoutSession(
            href="https://checkout.example/delivery",
            checkout_session_id="sess-pay-delivery",
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
                "order_type": "delivery",
                "customer": {"name": "Alex", "phone": "5875551234"},
                "delivery_dropoff": _delivery_dropoff(),
                "uber_quote_id": "dqt_pay_now",
                "payment_preference": "now",
            }
        )
    )
    assert result.ok
    assert result.status == "awaiting_payment"
    pending = get_by_checkout_session("sess-pay-delivery")
    assert pending is not None
    place_summary = pending["place_summary"]
    assert place_summary["uber_quote_id"] == "dqt_pay_now"
    assert place_summary["delivery_dropoff"]["street"] == "123 Main St"
    assert (
        place_summary["delivery_address"]
        == "123 Main St, Edmonton, AB T5J 0N3, CA"
    )


def test_pay_now_approved_fulfills_kitchen_and_dispatch_once(monkeypatch, tmp_path):
    monkeypatch.setenv("STORE_PAY_NOW_STORE_PATH", str(tmp_path / "pay.json"))
    from restaurant.store_checkout import fulfill_store_order_after_payment
    from restaurant.store_pay_now_store import (
        get_by_checkout_session,
        record_payment_approved,
        record_pending_checkout,
    )
    import asyncio

    checkout_session_id = "sess-approved-delivery"
    place_summary = {
        "items": [{"id": "DRINK1", "name": "Sweet Lassi", "qty": 1}],
        "order_type": "delivery",
        "customer": {"name": "Alex", "phone": "+15875551234"},
        "delivery_dropoff": _delivery_dropoff(),
        "delivery_address": "123 Main St, Edmonton, AB T5J 0N3, CA",
        "uber_quote_id": "dqt-approved-delivery",
        "payment_preference": "now",
        "total": 13.4,
    }
    record_pending_checkout(
        checkout_session_id=checkout_session_id,
        order_id=None,
        customer_name="Alex",
        customer_phone="+15875551234",
        total=13.4,
        order_type="delivery",
        session_id="web-store-approved",
        place_summary=place_summary,
    )
    record_payment_approved(
        checkout_session_id=checkout_session_id,
        payment_id="PAY-APPROVED",
        clover_payment_order_id="HCO-ORDER-APPROVED",
    )

    calls = {"kitchen": 0, "dispatch": 0, "dispatch_notify": 0, "placed": 0}

    async def fake_submit(summary, *, session_id):
        calls["kitchen"] += 1
        assert summary["uber_quote_id"] == "dqt-approved-delivery"
        assert session_id == "web-store-approved"
        return "CLOVER-ORDER-APPROVED", []

    def fake_dispatch(summary):
        calls["dispatch"] += 1
        assert summary["delivery_dropoff"]["street"] == "123 Main St"
        summary["uber_delivery_id"] = "del-approved"
        summary["uber_tracking_url"] = "https://tracking.example/del-approved"
        return {
            "ok": True,
            "delivery_id": "del-approved",
            "tracking_url": summary["uber_tracking_url"],
            "reused": False,
        }

    async def fake_dispatch_notify(*_args, **_kwargs):
        calls["dispatch_notify"] += 1

    async def fake_order_placed(*_args, **_kwargs):
        calls["placed"] += 1

    monkeypatch.setattr("restaurant.store_checkout._submit_kitchen", fake_submit)
    monkeypatch.setattr(
        "restaurant.uber_direct.service.dispatch_store_delivery",
        fake_dispatch,
    )
    monkeypatch.setattr(
        "restaurant.store_checkout._notify_delivery_dispatch_outcome",
        fake_dispatch_notify,
    )
    monkeypatch.setattr(
        "restaurant.store_checkout._notify_order_placed",
        fake_order_placed,
    )

    first = asyncio.run(fulfill_store_order_after_payment(checkout_session_id))
    replay = asyncio.run(fulfill_store_order_after_payment(checkout_session_id))

    assert first is not None and replay is not None
    assert first["order_id"] == replay["order_id"] == "CLOVER-ORDER-APPROVED"
    assert calls == {
        "kitchen": 1,
        "dispatch": 1,
        "dispatch_notify": 1,
        "placed": 1,
    }
    stored = get_by_checkout_session(checkout_session_id)
    assert stored is not None
    assert stored["place_summary"]["uber_delivery_id"] == "del-approved"


def test_pay_now_disabled_fails_closed(monkeypatch):
    _install_cache(monkeypatch)
    monkeypatch.setenv("STORE_PAY_NOW_ENABLED", "0")
    import asyncio
    from restaurant.store_checkout import place_store_order

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
    assert not result.ok
    assert any("pay now" in b.lower() or "online" in b.lower() for b in result.blockers)
