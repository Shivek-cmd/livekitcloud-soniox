"""
Sync Clover inventory into local menu cache for the default tenant.

Usage:
    python scripts/clover_sync_menu.py
    python scripts/clover_sync_menu.py --tenant-id bizbull
"""

from __future__ import annotations

import argparse
import sys

from dotenv import load_dotenv

load_dotenv()

from restaurant.clover.menu import MenuCache
from restaurant.tenants.config import get_default_tenant
from restaurant.tenants.store import get_tenant


def _safe_print(text: str) -> None:
    sys.stdout.buffer.write((text + "\n").encode("utf-8", errors="replace"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync Clover menu cache")
    parser.add_argument("--tenant-id", default=None, help="Tenant id (default: only tenant)")
    args = parser.parse_args()

    tenant = get_tenant(args.tenant_id) if args.tenant_id else get_default_tenant()
    if not tenant:
        raise SystemExit(f"Tenant not found: {args.tenant_id}. Run clover_init_tenant.py first.")

    _safe_print(f"Syncing menu for {tenant.name} ({tenant.tenant_id})...")
    cache = MenuCache.sync_from_clover(tenant)
    _safe_print(f"Done: {cache.item_count} items → {tenant.menu_cache_path}")
    _safe_print(f"Synced at: {cache.synced_at}")


if __name__ == "__main__":
    main()
