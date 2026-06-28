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


def find_item_by_id(clover_item_id: str) -> dict | None:
    """Look up a menu item by its Clover id (used by web tap-to-add)."""
    cache = _get_cache()
    if not cache:
        return None
    hit = cache.get_by_id(clover_item_id)
    if not hit:
        return None
    if not hit.available:
        return {**hit.to_cart_dict(), "unavailable": True}
    return hit.to_cart_dict()


def required_modifier_groups(clover_item_id: str) -> list[str]:
    """Names of required (min_required>0) modifier groups for an item, e.g. ['Choose Curry']."""
    cache = _get_cache()
    if not cache:
        return []
    hit = cache.get_by_id(clover_item_id)
    if not hit:
        return []
    return [g.name for g in hit.modifier_groups if g.min_required and g.min_required > 0]


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


def search_menu(query: str, *, limit: int = 2) -> str:
    cache = _get_cache()
    if not cache:
        return "Menu search is only available with Clover menu enabled."
    hits = cache.search(query, limit=limit)
    if not hits:
        return f"No menu items found matching '{query}'."
    options: list[str] = []
    for item in hits:
        if not item.available:
            continue
        options.append(f'{item.name} → say "{item.voice_line}"')
    if not options:
        return f"Items matching '{query}' exist but are currently unavailable."
    if len(options) == 1:
        return (
            f"One match for '{query}': {options[0]}. "
            "Confirm briefly in one sentence, then ask quantity if needed."
        )
    joined = " | ".join(options[:2])
    return (
        f"Matches for '{query}' (mention at most TWO in ONE casual sentence — never a numbered list): "
        f"{joined}. "
        'Good: "ਹਾਂ ਜੀ, ਸਾਡੇ ਕੋਲ X ਤੇ Y ਹੈ — ਕਿਹੜਾ?" '
        'Bad: "1 X, 2 Y" or "first X, second Y" or reading bullet points aloud.'
    )


def catalog() -> dict | None:
    """Full menu catalog grouped by category for the web menu panel, or None if unavailable."""
    cache = _get_cache()
    if not cache:
        return None
    return cache.catalog()


def menu_source_label() -> str:
    return "clover_cache" if _get_cache() else "static_menu"
