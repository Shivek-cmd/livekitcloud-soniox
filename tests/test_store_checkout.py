"""S3 — Store checkout validate + reprice (no place)."""

from restaurant import menu_provider
from restaurant.clover.menu import MenuCache
from restaurant.clover.models import CachedMenuItem, CachedModifierGroup
from restaurant.menu import DELIVERY_CHARGE
from restaurant.store_checkout import validate_store_checkout


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
