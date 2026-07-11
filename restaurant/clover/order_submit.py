"""Submit Sierra carts to Clover via atomic orders API (Phase 8c)."""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from typing import Any

from restaurant.clover.client import CloverClient, CloverError
from restaurant import menu_provider
from restaurant.orders import CartItem, OrderCart
from restaurant.tenants.store import Tenant

logger = logging.getLogger("clover-order-submit")

_SPICE_ALIASES: dict[str, tuple[str, ...]] = {
    "extra spicy": ("extra spicy", "extra-spicy", "bahut teekha", "bahut spicy"),
    "medium": ("medium spicy", "medium", "med"),
    "mild": ("mild", "kam spicy", "light"),
    "spicy": ("spicy", "teekha", "hot"),
}


@dataclass(frozen=True)
class CloverSubmitResult:
    clover_order_id: str
    total_cents: int | None
    customer_id: str | None
    printed: bool
    checkout_validated: bool


class CloverOrderSubmitError(Exception):
    """Cart cannot be submitted to Clover."""


def clover_submit_enabled() -> bool:
    return os.getenv("CLOVER_SUBMIT_ORDERS", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def clover_print_enabled() -> bool:
    raw = os.getenv("CLOVER_PRINT_ORDERS", "1").strip().lower()
    return raw not in ("0", "false", "no", "off")


def client_from_tenant(tenant: Tenant) -> CloverClient:
    return CloverClient(
        base_url=tenant.clover_base_url,
        merchant_id=tenant.clover_merchant_id,
        token=tenant.clover_api_token,
    )


def _normalize_phone(phone: str) -> str:
    digits = re.sub(r"\D", "", phone or "")
    if len(digits) == 11 and digits.startswith("1"):
        return digits[1:]
    if len(digits) == 12 and digits.startswith("91"):
        return digits[2:]
    return digits


def _resolve_order_type_id(
    client: CloverClient,
    tenant: Tenant,
    cart: OrderCart,
) -> str:
    if cart.order_type == "delivery" and tenant.order_type_delivery_id:
        return tenant.order_type_delivery_id
    if cart.order_type == "pickup" and tenant.order_type_pickup_id:
        return tenant.order_type_pickup_id
    if tenant.order_type_pickup_id and cart.order_type != "delivery":
        return tenant.order_type_pickup_id

    types = client.fetch_all("order_types")
    if not types:
        raise CloverOrderSubmitError(
            "No Clover order types found — create pickup/delivery types in Dashboard "
            "or set CLOVER_ORDER_TYPE_PICKUP_ID in .env."
        )

    if cart.order_type == "delivery":
        for ot in types:
            label = (ot.get("label") or ot.get("name") or "").lower()
            if "deliver" in label:
                return ot["id"]

    for ot in types:
        label = (ot.get("label") or ot.get("name") or "").lower()
        if "pick" in label or "pickup" in label or "take" in label:
            return ot["id"]
    return types[0]["id"]


def _resolve_clover_item_id(item: CartItem) -> str:
    if item.clover_item_id:
        return item.clover_item_id
    hit = menu_provider.find_item(item.name)
    if hit and hit.get("clover_item_id"):
        return hit["clover_item_id"]
    raise CloverOrderSubmitError(
        f"Item '{item.name}' has no Clover inventory id — enable USE_CLOVER_MENU=1 "
        "and sync the menu cache."
    )


def _cached_item(clover_item_id: str):
    from restaurant.clover.menu import MenuCache
    from restaurant.tenants.config import get_default_tenant

    tenant = get_default_tenant()
    path = tenant.cache_path()
    if not path.is_file():
        return None
    cache = MenuCache.load(path)
    return cache.get_by_id(clover_item_id)


def _match_spice_modifier(note: str, clover_item_id: str) -> dict[str, Any] | None:
    if not note:
        return None
    cached = _cached_item(clover_item_id)
    if not cached:
        return None
    text = note.lower()
    for group in cached.modifier_groups:
        if group.name != "Spice Level":
            continue
        for label, aliases in _SPICE_ALIASES.items():
            if not any(a in text for a in aliases):
                continue
            for mod in group.modifiers:
                if mod.name.lower() == label or label in mod.name.lower():
                    return {
                        "modifier": {"id": mod.clover_modifier_id, "available": True},
                        "name": mod.name,
                        "amount": mod.price_cents,
                    }
        for mod in group.modifiers:
            if mod.name.lower() in text:
                return {
                    "modifier": {"id": mod.clover_modifier_id, "available": True},
                    "name": mod.name,
                    "amount": mod.price_cents,
                }
            for alias in mod.aliases:
                if alias.lower() in text:
                    return {
                        "modifier": {"id": mod.clover_modifier_id, "available": True},
                        "name": mod.name,
                        "amount": mod.price_cents,
                    }
    return None


def _line_item_payload(item: CartItem) -> dict[str, Any]:
    clover_id = _resolve_clover_item_id(item)
    payload: dict[str, Any] = {"item": {"id": clover_id}}
    mods: list[dict[str, Any]] = []
    spice = _match_spice_modifier(item.note, clover_id)
    if spice:
        mods.append(spice)
    if mods:
        payload["modifications"] = mods
    elif item.note:
        payload["note"] = item.note[:255]
    return payload


def build_order_cart_body(
    cart: OrderCart,
    *,
    tenant: Tenant,
    client: CloverClient,
    session_id: str | None = None,
    channel: str = "phone",
    allergy_note: str | None = None,
) -> dict[str, Any]:
    if not menu_provider.use_clover_menu():
        raise CloverOrderSubmitError(
            "USE_CLOVER_MENU must be enabled to submit orders to Clover."
        )

    line_items: list[dict[str, Any]] = []
    for item in cart.items:
        base = _line_item_payload(item)
        for _ in range(max(1, item.quantity)):
            line_items.append(dict(base))

    if not line_items:
        raise CloverOrderSubmitError("Cart has no line items.")

    order_type_id = _resolve_order_type_id(client, tenant, cart)
    note_parts = [
        "Sierra voice order",
        f"channel={channel}",
    ]
    if session_id:
        note_parts.append(f"session={session_id}")
    if cart.customer_name:
        note_parts.append(f"name={cart.customer_name}")
    if cart.customer_phone:
        note_parts.append(f"phone={cart.customer_phone}")
    if cart.order_type == "delivery" and cart.delivery_address:
        note_parts.append(f"addr={cart.delivery_address}")
    if allergy_note:
        note_parts.append(f"ALLERGY: {allergy_note}")

    body: dict[str, Any] = {
        "orderCart": {
            "lineItems": line_items,
            "orderType": {"id": order_type_id},
            "note": " | ".join(note_parts)[:500],
        }
    }
    return body


def upsert_customer(
    client: CloverClient,
    *,
    phone: str,
    name: str,
    address: str | None = None,
) -> str | None:
    """Create or update Clover customer by phone. Returns customer id."""
    digits = _normalize_phone(phone)
    if len(digits) != 10:
        return None

    first_name = (name or "Guest").strip()[:64] or "Guest"
    existing_id: str | None = None

    try:
        data = client.get(
            client.merchant_path(f"/customers?filter=phoneNumber={digits}&limit=20")
        )
        elements = data.get("elements", []) if isinstance(data, dict) else []
        if elements:
            existing_id = elements[0].get("id")
    except CloverError:
        logger.warning("Customer phone search failed — will create new customer")

    payload: dict[str, Any] = {
        "firstName": first_name,
        "phoneNumbers": [{"phoneNumber": digits}],
    }
    if address:
        payload["addresses"] = [{"address1": address[:255]}]

    try:
        if existing_id:
            client.post(client.merchant_path(f"/customers/{existing_id}"), payload)
            return existing_id
        created = client.post(client.merchant_path("/customers"), payload)
        if isinstance(created, dict):
            return created.get("id")
    except CloverError as e:
        logger.warning("Clover customer upsert failed: %s", e)
    return None


def attach_customer_to_order(
    client: CloverClient,
    order_id: str,
    customer_id: str,
) -> None:
    try:
        client.post(
            client.merchant_path(f"/orders/{order_id}"),
            {"customers": [{"id": customer_id}]},
        )
    except CloverError as e:
        logger.warning("Could not attach customer %s to order %s: %s", customer_id, order_id, e)


def request_kitchen_print(client: CloverClient, order_id: str) -> bool:
    if not clover_print_enabled():
        return False
    try:
        client.post(
            client.merchant_path("/print_event"),
            {"orderRef": {"id": order_id}},
        )
        return True
    except CloverError as e:
        logger.warning("Kitchen print failed for order %s: %s", order_id, e)
        return False


def _clover_error_message(err: CloverError) -> str:
    payload = err.payload
    if isinstance(payload, dict):
        msg = payload.get("message") or payload.get("error") or payload.get("details")
        if msg:
            return str(msg)
    return str(err)


def submit_cart_to_clover(
    cart: OrderCart,
    *,
    tenant: Tenant,
    session_id: str | None = None,
    channel: str = "phone",
    allergy_note: str | None = None,
) -> CloverSubmitResult:
    """Checkout validate + create atomic order + optional print."""
    client = client_from_tenant(tenant)
    body = build_order_cart_body(
        cart,
        tenant=tenant,
        client=client,
        session_id=session_id,
        channel=channel,
        allergy_note=allergy_note,
    )

    checkout_validated = False
    try:
        client.post(client.merchant_path("/atomic_order/checkouts"), body)
        checkout_validated = True
    except CloverError as e:
        raise CloverOrderSubmitError(
            f"Clover checkout validation failed: {_clover_error_message(e)}"
        ) from e

    try:
        order = client.post(client.merchant_path("/atomic_order/orders"), body)
    except CloverError as e:
        raise CloverOrderSubmitError(
            f"Clover order create failed: {_clover_error_message(e)}"
        ) from e

    if not isinstance(order, dict) or not order.get("id"):
        raise CloverOrderSubmitError("Clover returned no order id.")

    order_id = order["id"]
    total_cents = order.get("total")
    if isinstance(total_cents, str) and total_cents.isdigit():
        total_cents = int(total_cents)

    customer_id: str | None = None
    if cart.customer_phone and cart.customer_name:
        customer_id = upsert_customer(
            client,
            phone=cart.customer_phone,
            name=cart.customer_name,
            address=cart.delivery_address if cart.order_type == "delivery" else None,
        )
        if customer_id:
            attach_customer_to_order(client, order_id, customer_id)

    printed = request_kitchen_print(client, order_id)

    logger.info(
        "CLOVER_ORDER_SUBMITTED id=%s total_cents=%s customer=%s printed=%s",
        order_id,
        total_cents,
        customer_id,
        printed,
    )

    return CloverSubmitResult(
        clover_order_id=order_id,
        total_cents=total_cents if isinstance(total_cents, int) else None,
        customer_id=customer_id,
        printed=printed,
        checkout_validated=checkout_validated,
    )
