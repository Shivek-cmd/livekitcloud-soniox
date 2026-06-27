"""
Wipe sandbox orders and inventory items for a fresh Phase 8a start.

DESTRUCTIVE — sandbox test merchants only.

Usage:
    uv run python scripts/clover_sandbox_cleanup.py --dry-run
    uv run python scripts/clover_sandbox_cleanup.py --confirm
"""

from __future__ import annotations

import argparse
import sys
import urllib.parse

from restaurant.clover.client import CloverClient, CloverError


def _safe_print(text: str) -> None:
    sys.stdout.buffer.write((text + "\n").encode("utf-8", errors="replace"))


def delete_orders(client: CloverClient, *, dry_run: bool) -> tuple[int, int]:
    orders = client.fetch_all("orders")
    _safe_print(f"Orders found: {len(orders)}")
    ok = 0
    for order in orders:
        oid = order["id"]
        if dry_run:
            _safe_print(f"  [dry-run] would delete order {oid} state={order.get('state')}")
            ok += 1
            continue
        try:
            client.delete(client.merchant_path(f"/orders/{oid}"))
            ok += 1
            _safe_print(f"  deleted order {oid}")
        except CloverError as e:
            _safe_print(f"  FAILED order {oid}: {e}")
    return ok, len(orders)


def delete_items(client: CloverClient, *, dry_run: bool, batch_size: int = 20) -> tuple[int, int]:
    items = client.fetch_all("items")
    _safe_print(f"Items found: {len(items)}")
    ids = [item["id"] for item in items]
    ok = 0
    for i in range(0, len(ids), batch_size):
        chunk = ids[i : i + batch_size]
        if dry_run:
            _safe_print(f"  [dry-run] would delete {len(chunk)} items")
            ok += len(chunk)
            continue
        q = urllib.parse.urlencode({"itemIds": ",".join(chunk)}, safe=",")
        try:
            client.delete(client.merchant_path(f"/items?{q}"))
            ok += len(chunk)
            _safe_print(f"  deleted {len(chunk)} items (batch {i // batch_size + 1})")
        except CloverError:
            for iid in chunk:
                try:
                    client.delete(client.merchant_path(f"/items/{iid}"))
                    ok += 1
                except CloverError as e:
                    _safe_print(f"  FAILED item {iid}: {e}")
    return ok, len(ids)


def main() -> None:
    parser = argparse.ArgumentParser(description="Delete all Clover sandbox orders and items")
    parser.add_argument("--confirm", action="store_true", help="Actually delete (required)")
    parser.add_argument("--dry-run", action="store_true", help="List counts only, no deletes")
    args = parser.parse_args()

    if not args.confirm and not args.dry_run:
        raise SystemExit("Pass --dry-run to preview or --confirm to delete.")

    client = CloverClient.from_env()
    info = client.get(client.merchant_path(""))
    _safe_print(f"Merchant: {info.get('name')} ({info.get('id')})")
    _safe_print(f"Base URL: {client.base_url}")

    o_ok, o_total = delete_orders(client, dry_run=args.dry_run)
    i_ok, i_total = delete_items(client, dry_run=args.dry_run)

    _safe_print(f"\nOrders: {o_ok}/{o_total}")
    _safe_print(f"Items:  {i_ok}/{i_total}")

    if not args.dry_run:
        remaining_orders = len(client.fetch_all("orders"))
        remaining_items = len(client.fetch_all("items"))
        _safe_print(f"Remaining: {remaining_items} items, {remaining_orders} orders")


if __name__ == "__main__":
    main()
