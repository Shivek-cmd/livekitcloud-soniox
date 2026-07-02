"""Tests for Clover atomic order submit (Phase 8c)."""

from unittest.mock import MagicMock, patch

import pytest

from restaurant.clover.order_submit import (
    CloverOrderSubmitError,
    build_order_cart_body,
    clover_submit_enabled,
    submit_cart_to_clover,
)
from restaurant.orders import OrderCart
from restaurant.tenants.store import Tenant


@pytest.fixture
def tenant() -> Tenant:
    return Tenant(
        tenant_id="bizbull",
        name="Test",
        clover_merchant_id="MID123",
        clover_base_url="https://apisandbox.dev.clover.com",
        clover_api_token="token",
        order_type_pickup_id="PICKUP_OT",
        order_type_delivery_id="DELIVERY_OT",
        phone_number=None,
        voice_labels_path="data/clover_voice_labels.json",
        menu_cache_path="data/menu_cache_bizbull.json",
        menu_cache_updated_at=None,
        delivery_charge=5.0,
        min_order_delivery=20.0,
        restaurant_name="Test",
        restaurant_name_en="Test",
    )


def test_clover_submit_enabled_env(monkeypatch):
    monkeypatch.delenv("CLOVER_SUBMIT_ORDERS", raising=False)
    assert clover_submit_enabled() is False
    monkeypatch.setenv("CLOVER_SUBMIT_ORDERS", "1")
    assert clover_submit_enabled() is True


@patch("restaurant.clover.order_submit.menu_provider.use_clover_menu", return_value=True)
@patch("restaurant.clover.order_submit._resolve_clover_item_id", return_value="ITEM123")
def test_build_order_cart_expands_quantity(mock_resolve, mock_use, tenant):
    cart = OrderCart()
    cart.order_type = "pickup"
    cart.customer_name = "Shivek"
    cart.customer_phone = "9413752688"
    cart.items.append(
        type(
            "CI",
            (),
            {
                "name": "Naan",
                "voice_line": "Naan",
                "price": 3.0,
                "quantity": 2,
                "note": "",
                "clover_item_id": "ITEM123",
                "speech_mode": "english",
            },
        )()
    )
    client = MagicMock()
    body = build_order_cart_body(cart, tenant=tenant, client=client, channel="web")
    assert len(body["orderCart"]["lineItems"]) == 2
    assert body["orderCart"]["orderType"]["id"] == "PICKUP_OT"
    assert "Sierra voice order" in body["orderCart"]["note"]


@patch("restaurant.clover.order_submit.menu_provider.use_clover_menu", return_value=True)
@patch("restaurant.clover.order_submit._resolve_clover_item_id", return_value="ITEM123")
@patch("restaurant.clover.order_submit._match_spice_modifier")
def test_build_order_cart_spice_modifier(mock_spice, mock_resolve, mock_use, tenant):
    mock_spice.return_value = {
        "modifier": {"id": "MOD1", "available": True},
        "name": "Medium",
        "amount": 0,
    }
    cart = OrderCart()
    cart.order_type = "pickup"
    cart.add_item(
        {
            "name": "Chicken Biryani",
            "voice_line": "Chicken Biryani",
            "price": 18.99,
            "clover_item_id": "ITEM123",
        },
        1,
        note="medium spicy",
    )
    client = MagicMock()
    body = build_order_cart_body(cart, tenant=tenant, client=client)
    li = body["orderCart"]["lineItems"][0]
    assert li["modifications"][0]["name"] == "Medium"


@patch("restaurant.clover.order_submit.request_kitchen_print", return_value=True)
@patch("restaurant.clover.order_submit.attach_customer_to_order")
@patch("restaurant.clover.order_submit.upsert_customer", return_value="CUST1")
@patch("restaurant.clover.order_submit.build_order_cart_body")
@patch("restaurant.clover.order_submit.client_from_tenant")
def test_submit_cart_success(
    mock_client_fn,
    mock_build,
    mock_upsert,
    mock_attach,
    mock_print,
    tenant,
):
    mock_client = MagicMock()
    mock_client_fn.return_value = mock_client
    mock_build.return_value = {"orderCart": {"lineItems": []}}
    mock_client.post.side_effect = [
        {"total": 2500},  # checkout
        {"id": "ORDER99", "total": 2500},  # create
    ]

    cart = OrderCart()
    cart.order_type = "pickup"
    cart.customer_name = "Shivek"
    cart.customer_phone = "9413752688"
    cart.add_item(
        {"name": "Kulfi", "voice_line": "Kulfi", "price": 6.99, "clover_item_id": "X"},
        1,
    )

    result = submit_cart_to_clover(cart, tenant=tenant, channel="phone")
    assert result.clover_order_id == "ORDER99"
    assert result.total_cents == 2500
    assert result.checkout_validated is True
    mock_print.assert_called_once()


@patch("restaurant.clover.order_submit.client_from_tenant")
@patch("restaurant.clover.order_submit.build_order_cart_body")
def test_submit_cart_checkout_failure(mock_build, mock_client_fn, tenant):
    from restaurant.clover.client import CloverError

    mock_client = MagicMock()
    mock_client_fn.return_value = mock_client
    mock_build.return_value = {"orderCart": {"lineItems": []}}
    mock_client.post.side_effect = CloverError(400, {"message": "item_does_not_exist"})

    cart = OrderCart()
    cart.order_type = "pickup"
    cart.customer_name = "Shivek"
    cart.customer_phone = "9413752688"
    cart.add_item(
        {"name": "Kulfi", "voice_line": "Kulfi", "price": 6.99, "clover_item_id": "X"},
        1,
    )

    with pytest.raises(CloverOrderSubmitError, match="checkout validation failed"):
        submit_cart_to_clover(cart, tenant=tenant)
