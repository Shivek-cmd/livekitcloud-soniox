"""Integration test — submit a sample cart to Clover sandbox."""

from __future__ import annotations

import argparse
import sys

from dotenv import load_dotenv

load_dotenv()

from restaurant.clover.order_submit import (
    CloverOrderSubmitError,
    clover_submit_enabled,
    submit_cart_to_clover,
)
from restaurant import menu_provider
from restaurant.orders import OrderCart
from restaurant.tenants.config import get_default_tenant


def _safe_print(text: str) -> None:
    sys.stdout.buffer.write((text + "\n").encode("utf-8", errors="replace"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Submit a test cart to Clover sandbox")
    parser.add_argument("--dry-run", action="store_true", help="Build cart body only, no API submit")
    args = parser.parse_args()

    if not menu_provider.use_clover_menu():
        _safe_print("Set USE_CLOVER_MENU=1 before submitting to Clover.")
        raise SystemExit(1)

    tenant = get_default_tenant()
    cart = OrderCart()
    cart.order_type = "pickup"
    cart.customer_name = "Sierra Test"
    cart.customer_phone = "5551234567"

    item = menu_provider.find_item("Chicken Biryani")
    if not item:
        _safe_print("Chicken Biryani not in menu cache.")
        raise SystemExit(1)
    cart.add_item(item, 1, note="medium spicy")

    if args.dry_run:
        from restaurant.clover.order_submit import build_order_cart_body, client_from_tenant

        client = client_from_tenant(tenant)
        body = build_order_cart_body(cart, tenant=tenant, client=client, channel="test")
        import json

        _safe_print(json.dumps(body, indent=2)[:3000])
        return

    if not clover_submit_enabled():
        _safe_print("Set CLOVER_SUBMIT_ORDERS=1 to submit.")
        raise SystemExit(1)

    try:
        result = submit_cart_to_clover(cart, tenant=tenant, channel="script")
    except CloverOrderSubmitError as e:
        _safe_print(f"Submit failed: {e}")
        raise SystemExit(1) from e

    _safe_print(f"Clover order id: {result.clover_order_id}")
    _safe_print(f"Total cents: {result.total_cents}")
    _safe_print(f"Customer id: {result.customer_id}")
    _safe_print(f"Kitchen print: {result.printed}")


if __name__ == "__main__":
    main()
