"""
Bootstrap the Bizbull demo tenant from .env (run once after CLOVER_* are set).

Usage:
    python scripts/clover_init_tenant.py
"""

from __future__ import annotations

import sys

from dotenv import load_dotenv

load_dotenv()

from restaurant.tenants.store import bootstrap_bizbull_from_env


def _safe_print(text: str) -> None:
    sys.stdout.buffer.write((text + "\n").encode("utf-8", errors="replace"))


def main() -> None:
    tenant = bootstrap_bizbull_from_env()
    _safe_print(f"Tenant ready: {tenant.name} ({tenant.tenant_id})")
    _safe_print(f"  Clover MID: {tenant.clover_merchant_id}")
    _safe_print(f"  Menu cache: {tenant.menu_cache_path}")
    _safe_print(f"  Voice labels: {tenant.voice_labels_path}")
    if tenant.order_type_pickup_id:
        _safe_print(f"  Pickup order type: {tenant.order_type_pickup_id}")
    if tenant.order_type_delivery_id:
        _safe_print(f"  Delivery order type: {tenant.order_type_delivery_id}")
    _safe_print("\nNext: python scripts/clover_sync_menu.py")


if __name__ == "__main__":
    main()
