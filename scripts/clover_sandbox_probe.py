"""
Clover sandbox smoke test — read menu, optional checkout/create order.

Usage:
    uv run python scripts/clover_sandbox_probe.py
    uv run python scripts/clover_sandbox_probe.py --checkout
    uv run python scripts/clover_sandbox_probe.py --checkout --create-order
"""

from __future__ import annotations

import argparse
import json
import sys

from restaurant.clover.client import CloverClient, CloverError


def _safe_print(text: str) -> None:
    sys.stdout.buffer.write((text + "\n").encode("utf-8", errors="replace"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Clover sandbox API probe")
    parser.add_argument("--checkout", action="store_true", help="Run atomic_order/checkouts")
    parser.add_argument("--create-order", action="store_true", help="Run atomic_order/orders (implies checkout body)")
    args = parser.parse_args()

    client = CloverClient.from_env()
    info = client.get(client.merchant_path(""))
    _safe_print(f"Merchant: {info.get('name')} ({info.get('id')})")

    items = client.fetch_all("items")
    _safe_print(f"Items: {len(items)}")
    for item in items[:10]:
        _safe_print(f"  {item.get('id')} | {item.get('name')} | ${(item.get('price') or 0) / 100:.2f}")
    if len(items) > 10:
        _safe_print(f"  ... and {len(items) - 10} more")

    order_types = client.fetch_all("order_types")
    _safe_print(f"Order types: {len(order_types)}")
    for ot in order_types:
        _safe_print(f"  {ot.get('id')} | {ot.get('label') or ot.get('name') or 'unnamed'}")

    if not items:
        _safe_print("\nNo items — run: python scripts/clover_sandbox_seed.py --confirm")
        return

    if not (args.checkout or args.create_order):
        return

    item_id = items[0]["id"]
    order_type_id = order_types[0]["id"] if order_types else None
    if not order_type_id:
        _safe_print("\nNo order types — create pickup/delivery types in Clover Dashboard first.")
        return

    body = {
        "orderCart": {
            "lineItems": [{"item": {"id": item_id}}],
            "orderType": {"id": order_type_id},
        }
    }

    if args.checkout or args.create_order:
        _safe_print("\n--- atomic_order/checkouts ---")
        try:
            checkout = client.post(client.merchant_path("/atomic_order/checkouts"), body)
            _safe_print(json.dumps(checkout, indent=2)[:2000])
        except CloverError as e:
            _safe_print(f"Checkout failed: {e}")
            return

    if args.create_order:
        _safe_print("\n--- atomic_order/orders ---")
        try:
            order = client.post(client.merchant_path("/atomic_order/orders"), body)
            _safe_print(json.dumps(order, indent=2)[:2000])
            oid = order.get("id") if isinstance(order, dict) else None
            if oid:
                _safe_print(f"\nCreated order id: {oid}")
        except CloverError as e:
            _safe_print(f"Create order failed: {e}")


if __name__ == "__main__":
    main()
