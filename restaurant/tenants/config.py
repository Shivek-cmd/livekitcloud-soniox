"""Tenant resolution — single default tenant for demo; multi-tenant routing in Phase 8f."""

from __future__ import annotations

from restaurant.tenants.store import Tenant, get_tenant, list_tenants


def get_default_tenant() -> Tenant:
    """Return the only configured tenant (Bizbull demo)."""
    tenants = list_tenants()
    if not tenants:
        raise RuntimeError(
            "No tenant configured. Run: python scripts/clover_init_tenant.py"
        )
    if len(tenants) == 1:
        return tenants[0]
    preferred = get_tenant("bizbull")
    if preferred:
        return preferred
    return tenants[0]
