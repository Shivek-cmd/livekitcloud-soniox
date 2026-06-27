"""Menu lookup facade — Clover cache when USE_CLOVER_MENU=1, else static menu.py."""

from __future__ import annotations

import logging
import os

from restaurant.menu import find_item as static_find_item

logger = logging.getLogger("menu-provider")

_cache = None
_cache_loaded = False


def use_clover_menu() -> bool:
    return os.getenv("USE_CLOVER_MENU", "").strip().lower() in ("1", "true", "yes")


def _get_cache():
    global _cache, _cache_loaded
    if _cache_loaded:
        return _cache
    _cache_loaded = True
    if not use_clover_menu():
        return None
    try:
        from restaurant.clover.menu import MenuCache
        from restaurant.tenants.config import get_default_tenant

        tenant = get_default_tenant()
        path = tenant.cache_path()
        if not path.is_file():
            logger.warning("Menu cache missing at %s — falling back to static menu", path)
            return None
        _cache = MenuCache.load(path)
        logger.info(
            "Loaded Clover menu cache: %d items (synced %s)",
            _cache.item_count,
            _cache.synced_at,
        )
    except Exception:
        logger.exception("Failed to load Clover menu cache — falling back to static menu")
        _cache = None
    return _cache


def find_item(name: str) -> dict | None:
    cache = _get_cache()
    if cache:
        hit = cache.find_item(name)
        if hit:
            if not hit.available:
                return {**hit.to_cart_dict(), "unavailable": True}
            return hit.to_cart_dict()
        return None
    item = static_find_item(name)
    return item


def check_item(name: str) -> str:
    cache = _get_cache()
    if cache:
        hit = cache.find_item(name)
        if not hit:
            return f"'{name}' is not on our menu."
        return hit.describe()
    item = static_find_item(name)
    if not item:
        return f"'{name}' is not on our menu."
    veg = "Vegetarian" if item["veg"] else "Non-vegetarian"
    return (
        f"{item['name']} ({item['punjabi']}) — {veg}\n"
        f"Price (INTERNAL — do NOT say unless customer asks): ${item['price']}"
    )


def search_menu(query: str, *, limit: int = 8) -> str:
    cache = _get_cache()
    if not cache:
        return "Menu search is only available with Clover menu enabled."
    hits = cache.search(query, limit=limit)
    if not hits:
        return f"No menu items found matching '{query}'."
    lines = [f"Found {len(hits)} item(s) for '{query}':"]
    for item in hits:
        tag = "V" if item.veg else "NV"
        avail = "" if item.available else " [unavailable]"
        lines.append(
            f'  - {item.name} (say aloud: "{item.voice_line}", {item.speech_mode}) ({tag}){avail}'
        )
        if item.modifier_groups:
            lines.append(f"    Options: {', '.join(g.name for g in item.modifier_groups)}")
    lines.append(
        "Use voice_line for dish names. Do NOT mention prices unless the customer asks."
    )
    return "\n".join(lines)


def menu_source_label() -> str:
    return "clover_cache" if _get_cache() else "static_menu"
