"""Web Store checkout — validate (S3) + place via Clover/n8n (S4).

Browser is untrusted for prices and availability. This module reloads the
menu cache, rebuilds the priced summary, and optionally submits to Clover
then notifies n8n (fail-open for CRM).
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from typing import Any

from restaurant.agent.gates import SPICE_LEVELS
from restaurant.customer_info import is_valid_customer_name
from restaurant.integrations.n8n_webhook import phone_to_e164
from restaurant.menu import DELIVERY_CHARGE
from restaurant import menu_provider
from restaurant.orders import CartItem, OrderCart

logger = logging.getLogger("store-checkout")

STORE_CHANNEL = "web_store"

# Canonical values echoed in summary / accepted on the wire.
PAYMENT_PREFERENCE_LATER = "later"
PAYMENT_PREFERENCE_NOW = "now"
_PAYMENT_PREFERENCE_ALIASES = {
    "later": PAYMENT_PREFERENCE_LATER,
    "pay_later": PAYMENT_PREFERENCE_LATER,
    "pay-later": PAYMENT_PREFERENCE_LATER,
    "now": PAYMENT_PREFERENCE_NOW,
    "pay_now": PAYMENT_PREFERENCE_NOW,
    "pay-now": PAYMENT_PREFERENCE_NOW,
}


def parse_payment_preference(payload: dict[str, Any]) -> tuple[str | None, str | None]:
    """Return (preference, blocker). Missing/blank → later. Invalid → blocker."""
    raw = payload.get("payment_preference")
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return PAYMENT_PREFERENCE_LATER, None
    key = str(raw).strip().lower().replace(" ", "_")
    pref = _PAYMENT_PREFERENCE_ALIASES.get(key)
    if pref is None:
        return None, "Choose pay later or pay now."
    return pref, None


@dataclass
class StoreCheckoutResult:
    ok: bool
    status: str = "validated"  # validated | invalid | placed
    blockers: list[str] = field(default_factory=list)
    summary: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"ok": self.ok, "status": self.status}
        if self.blockers:
            out["blockers"] = self.blockers
        if self.summary is not None:
            out["summary"] = self.summary
        return out


def _extract_spice(modifiers: list[Any] | None) -> str | None:
    # Longer labels first so "extra spicy" does not become "Spicy".
    ordered = sorted(SPICE_LEVELS, key=lambda s: -len(s))
    for raw in modifiers or []:
        if not isinstance(raw, str):
            continue
        key = raw.strip().lower().replace("-", " ")
        for level in ordered:
            level_key = level.lower()
            if (
                key == level_key
                or key.startswith(level_key + " ")
                or key.endswith(" " + level_key)
            ):
                return level
            if level_key in key and level == "Extra Spicy":
                return level
        for level in ordered:
            if key == level.lower():
                return level
    return None


def _item_requires_spice(clover_item_id: str) -> bool:
    return menu_provider.item_has_spice_by_id(clover_item_id)


def validate_store_checkout(payload: dict[str, Any]) -> StoreCheckoutResult:
    """Validate + reprice a Store checkout request. Never places an order."""
    blockers: list[str] = []

    if menu_provider.catalog() is None:
        return StoreCheckoutResult(
            ok=False,
            status="invalid",
            blockers=["Menu is not available. Try again in a moment."],
        )

    raw_items = payload.get("items")
    if not isinstance(raw_items, list) or not raw_items:
        blockers.append("Cart is empty.")

    order_type = (payload.get("order_type") or "").strip().lower()
    if order_type not in ("pickup", "delivery"):
        blockers.append("Choose pickup or delivery.")

    customer = payload.get("customer") or {}
    if not isinstance(customer, dict):
        customer = {}
    name = (customer.get("name") or "").strip()
    phone_raw = (customer.get("phone") or "").strip()
    if not name or not is_valid_customer_name(name):
        blockers.append("Enter a valid name.")
    phone = phone_to_e164(phone_raw)
    digits = "".join(c for c in phone if c.isdigit())
    if len(digits) < 10:
        blockers.append("Enter a valid phone number.")

    delivery_address = (payload.get("delivery_address") or "").strip()
    if order_type == "delivery" and len(delivery_address) < 5:
        blockers.append("Delivery address is required.")

    note = (payload.get("note") or "").strip()

    payment_preference, pay_blocker = parse_payment_preference(payload)
    if pay_blocker:
        blockers.append(pay_blocker)

    priced_lines: list[dict[str, Any]] = []
    if isinstance(raw_items, list):
        for idx, raw in enumerate(raw_items):
            if not isinstance(raw, dict):
                blockers.append(f"Item {idx + 1} is invalid.")
                continue
            item_id = str(raw.get("id") or "").strip()
            try:
                qty = int(raw.get("qty") or 0)
            except (TypeError, ValueError):
                qty = 0
            modifiers = (
                raw.get("modifiers") if isinstance(raw.get("modifiers"), list) else []
            )

            if not item_id:
                blockers.append(f"Item {idx + 1} is missing an id.")
                continue
            if qty < 1:
                blockers.append(f"Item {idx + 1} needs a quantity of at least 1.")
                continue

            hit = menu_provider.find_item_by_id(item_id)
            if not hit:
                blockers.append(f"Unknown menu item ({item_id}).")
                continue
            if hit.get("unavailable"):
                blockers.append(f"{hit.get('name', 'Item')} is sold out.")
                continue

            spice = _extract_spice(modifiers)
            if _item_requires_spice(item_id) and not spice:
                blockers.append(
                    f"{hit['name']} needs a spice level "
                    f"({', '.join(SPICE_LEVELS)})."
                )
                continue
            if spice and spice not in SPICE_LEVELS:
                blockers.append(f"Invalid spice level for {hit['name']}.")
                continue

            unit = float(hit.get("price") or 0)
            line_mods = [spice] if spice else []
            priced_lines.append(
                {
                    "id": item_id,
                    "name": hit["name"],
                    "voice_line": hit.get("voice_line") or hit["name"],
                    "qty": qty,
                    "unit_price": round(unit, 2),
                    "line_total": round(unit * qty, 2),
                    "modifiers": line_mods,
                }
            )

    if blockers:
        return StoreCheckoutResult(ok=False, status="invalid", blockers=blockers)

    subtotal = round(sum(l["line_total"] for l in priced_lines), 2)
    delivery_charge = float(DELIVERY_CHARGE) if order_type == "delivery" else 0.0
    total = round(subtotal + delivery_charge, 2)

    summary = {
        "items": priced_lines,
        "order_type": order_type,
        "customer": {"name": name, "phone": phone},
        "delivery_address": delivery_address if order_type == "delivery" else None,
        "note": note or None,
        "payment_preference": payment_preference or PAYMENT_PREFERENCE_LATER,
        # P2 will set checkout_url when preference is "now".
        "checkout_url": None,
        "subtotal": subtotal,
        "delivery_charge": round(delivery_charge, 2),
        "total": total,
        "placed": False,
        "order_id": None,
        "eta": None,
        "clover_submitted": False,
    }
    return StoreCheckoutResult(ok=True, status="validated", summary=summary)


def _summary_to_cart(summary: dict[str, Any]) -> OrderCart:
    cart = OrderCart()
    for line in summary["items"]:
        mods = line.get("modifiers") or []
        note = ", ".join(str(m).lower() for m in mods) if mods else ""
        cart.items.append(
            CartItem(
                name=line["name"],
                voice_line=line.get("voice_line") or line["name"],
                price=float(line["unit_price"]),
                quantity=int(line["qty"]),
                note=note,
                clover_item_id=line["id"],
            )
        )
    cart.order_type = summary["order_type"]
    cart.customer_name = summary["customer"]["name"]
    cart.customer_phone = summary["customer"]["phone"]
    cart.delivery_address = summary.get("delivery_address")
    return cart


async def place_store_order(payload: dict[str, Any]) -> StoreCheckoutResult:
    """Validate, then place (Clover if enabled) + n8n notify (fail-open)."""
    validated = validate_store_checkout(payload)
    if not validated.ok or not validated.summary:
        return validated

    summary = dict(validated.summary)
    cart = _summary_to_cart(summary)
    session_id = f"web-store-{uuid.uuid4().hex[:12]}"
    eta = "30-40 min" if cart.order_type == "delivery" else "20-25 min"
    clover_order_id: str | None = None

    from restaurant.clover.order_submit import (
        CloverOrderSubmitError,
        clover_submit_enabled,
        submit_cart_to_clover,
    )

    if clover_submit_enabled():
        from restaurant.tenants.config import get_default_tenant

        try:
            result = await asyncio.to_thread(
                submit_cart_to_clover,
                cart,
                tenant=get_default_tenant(),
                session_id=session_id,
                channel=STORE_CHANNEL,
                allergy_note=summary.get("note"),
            )
            clover_order_id = result.clover_order_id
        except CloverOrderSubmitError as e:
            logger.error("Store Clover submit failed: %s", e)
            return StoreCheckoutResult(
                ok=False,
                status="invalid",
                blockers=[f"Could not place order with the kitchen: {e}"],
                summary=summary,
            )
        except Exception:
            logger.exception("Store Clover submit unexpected error")
            return StoreCheckoutResult(
                ok=False,
                status="invalid",
                blockers=[
                    "Could not reach the restaurant POS. Please try again in a moment."
                ],
                summary=summary,
            )
    else:
        # Log-only place (same idea as voice when CLOVER_SUBMIT_ORDERS is off).
        clover_order_id = f"LOG-{session_id}"
        logger.info(
            "STORE_ORDER_PLACED_LOG_ONLY session=%s total=%s items=%s",
            session_id,
            summary["total"],
            len(summary["items"]),
        )

    summary["placed"] = True
    summary["order_id"] = clover_order_id
    summary["eta"] = eta
    summary["clover_submitted"] = bool(
        clover_order_id and not str(clover_order_id).startswith("LOG-")
    )
    summary["session_id"] = session_id

    # Pay now → Hosted Checkout link (fail-open: order already placed).
    if summary.get("payment_preference") == PAYMENT_PREFERENCE_NOW:
        from restaurant.clover.hosted_checkout import (
            HostedCheckoutError,
            create_hosted_checkout_session,
            store_pay_now_enabled,
        )

        if not store_pay_now_enabled():
            logger.info(
                "STORE_PAY_NOW skipped — STORE_PAY_NOW_ENABLED off order_id=%s",
                clover_order_id,
            )
        else:
            try:
                from restaurant.tenants.config import get_default_tenant

                tenant = get_default_tenant()
                session = await asyncio.to_thread(
                    create_hosted_checkout_session,
                    summary,
                    order_id=clover_order_id,
                    merchant_id=tenant.clover_merchant_id,
                    base_url=tenant.clover_base_url,
                    token=None,  # env Ecommerce token (or API token fallback)
                )
                summary["checkout_url"] = session.href
                summary["checkout_session_id"] = session.checkout_session_id
                logger.info(
                    "STORE_PAY_NOW checkout_url order_id=%s session=%s",
                    clover_order_id,
                    session.checkout_session_id,
                )
            except HostedCheckoutError as e:
                logger.warning(
                    "STORE_PAY_NOW HCO failed order_id=%s err=%s — order still placed",
                    clover_order_id,
                    e,
                )
            except Exception:
                logger.exception(
                    "STORE_PAY_NOW unexpected error order_id=%s — order still placed",
                    clover_order_id,
                )

    try:
        from restaurant.integrations.n8n_webhook import notify_order_placed

        await notify_order_placed(
            channel=STORE_CHANNEL,
            customer_name=summary["customer"]["name"],
            customer_phone=summary["customer"]["phone"],
            order_type=summary["order_type"],
            items=[
                {
                    "name": line["name"],
                    "qty": line["qty"],
                    "price": line["unit_price"],
                    "note": ", ".join(line.get("modifiers") or []),
                }
                for line in summary["items"]
            ],
            subtotal=summary["subtotal"],
            total=summary["total"],
            address=summary.get("delivery_address"),
            allergy_note=summary.get("note"),
            clover_order_id=clover_order_id if summary["clover_submitted"] else None,
            clover_submitted=summary["clover_submitted"],
            session_id=session_id,
            eta=eta,
        )
    except Exception:
        logger.exception("n8n store order.placed notify raised — ignored")

    logger.info(
        "STORE_ORDER_PLACED order_id=%s clover=%s total=%s pay=%s checkout=%s",
        clover_order_id,
        summary["clover_submitted"],
        summary["total"],
        summary.get("payment_preference"),
        bool(summary.get("checkout_url")),
    )
    return StoreCheckoutResult(ok=True, status="placed", summary=summary)
