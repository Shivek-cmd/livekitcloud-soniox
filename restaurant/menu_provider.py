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
        scored = cache.find_item_scored(name)
        if scored:
            hit, confidence = scored
            out = {**hit.to_cart_dict(), "match_confidence": confidence}
            if not hit.available:
                out["unavailable"] = True
            return out
        return None
    item = static_find_item(name)
    return item


def browse_menu_options(query: str, *, limit: int = 6) -> tuple[str, list[dict]]:
    """Resolve browse query to (topic_label, [{name, voice_line}, ...])."""
    from restaurant.menu_browse import BrowseKind, resolve_browse_target

    cache = _get_cache()
    if not cache:
        return query, []

    target = resolve_browse_target(query)
    hits: list = []

    if target is not None:
        if target.kind == BrowseKind.CATEGORY and target.category_name:
            hits = cache.list_by_category(target.category_name, limit=limit)
        elif target.item_names:
            for name in target.item_names:
                item = cache.find_item(name)
                if item and item.available:
                    hits.append(item)
        elif target.name_contains:
            hits = cache.items_by_name_contains(target.name_contains, limit=limit)

        label = target.label
        if hits:
            return label, [{"name": h.name, "voice_line": h.voice_line} for h in hits]

    disamb = disambiguation_options(query, limit=limit)
    if len(disamb) >= 2:
        return query, disamb

    search_hits = cache.search(query, limit=limit)
    available = [h for h in search_hits if h.available]
    if available:
        return query, [{"name": h.name, "voice_line": h.voice_line} for h in available]

    return query, []


def _format_browse_tool_result(query: str, options: list[dict], *, spoken_limit: int = 2) -> str:
    if not options:
        return f"No menu items found matching '{query}'."
    spoken = options[:spoken_limit]
    lines = [f'{o["name"]} → say "{o["voice_line"]}"' for o in spoken]
    joined = " | ".join(lines)
    extra = len(options) - len(spoken)
    tail = f" (+{extra} more — INTERNAL, offer if they want more)" if extra > 0 else ""
    if len(spoken) == 1:
        return (
            f"One match for '{query}': {joined}. "
            "Confirm briefly in one sentence, then ask quantity if needed."
            f"{tail}"
        )
    return (
        f"Browse result for '{query}' (mention at most TWO in ONE casual sentence — "
        f"never a numbered list): {joined}. "
        'Good: "ਹਾਂ ਜੀ, ਸਾਡੇ ਕੋਲ X ਤੇ Y ਹੈ — ਕਿਹੜਾ?" '
        'Bad: "1 X, 2 Y" or "first X, second Y". Ask which they would like.'
        f"{tail}"
    )


def browse_menu(query: str, *, limit: int = 2) -> str:
    """Category/family-aware menu browse for tools and code-owned replies."""
    _topic, options = browse_menu_options(query, limit=max(limit, 6))
    return _format_browse_tool_result(query, options, spoken_limit=limit)


def disambiguation_options(name: str, *, limit: int = 3) -> list[dict]:
    """Available menu items a vague term could mean, when the strict matcher
    abstained. Used to ASK the caller which dish instead of guessing (e.g.
    "fish" -> Punjabi Fish Curry, Amritsari Fish Pakora) or dead-ending on
    "not on our menu" when the dish clearly exists.
    """
    cache = _get_cache()
    if not cache:
        return []
    out: list[dict] = []
    for hit in cache.search(name, limit=limit * 2):
        if not hit.available:
            continue
        out.append({"name": hit.name, "voice_line": hit.voice_line})
        if len(out) >= limit:
            break
    return out


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
    return browse_menu(query, limit=limit)


def catalog() -> dict | None:
    """Full menu catalog grouped by category for the web menu panel, or None if unavailable."""
    cache = _get_cache()
    if not cache:
        return None
    return cache.catalog()


def menu_source_label() -> str:
    return "clover_cache" if _get_cache() else "static_menu"


def item_has_spice_level(name: str) -> bool:
    """True if this menu item has a Spice Level modifier group."""
    cache = _get_cache()
    if cache:
        hit = cache.find_item(name)
        if hit:
            return any(g.name == "Spice Level" for g in hit.modifier_groups)
        return False
    item = static_find_item(name)
    return bool(item and item.get("spice_level"))


def resolve_item_in_text(text: str) -> dict | None:
    """Best-effort menu item match from free-form caller text."""
    t = (text or "").strip()
    if not t:
        return None
    direct = find_item(t)
    if direct and not direct.get("unavailable"):
        return direct
    cache = _get_cache()
    if cache:
        hits = cache.search(t, limit=1)
        if hits and hits[0].available:
            # substring search is weak evidence — confidence capped below the
            # auto-add gate so this path can never speak a code-owned confirm
            return {**hits[0].to_cart_dict(), "match_confidence": 0.5}
    # Try longest token runs (3+ chars) for dish names in mixed sentences
    import re

    for chunk in re.findall(r"[A-Za-z\u0900-\u097F\u0A00-\u0A7F]{4,}", t):
        hit = find_item(chunk)
        if hit and not hit.get("unavailable"):
            return hit
    return None


def item_price_dollars(name: str) -> float | None:
    item = find_item(name)
    if not item:
        return None
    if "price" in item:
        return float(item["price"])
    if "price_cents" in item:
        return item["price_cents"] / 100.0
    return None
