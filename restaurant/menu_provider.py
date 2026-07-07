"""Menu lookup facade — Clover cache when USE_CLOVER_MENU=1, else static menu.py."""

from __future__ import annotations

import logging
import os
import re

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


_DISH_TOKEN_RE = re.compile(r"[A-Za-z\u0900-\u097F\u0A00-\u0A7F]+")

_AVAIL_QUERY_PREFIX_RE = re.compile(
    r"^(?:"
    r"do you have|have you got|is there|is\s+.+\s+available|"
    r"ਸਾਡੇ ਕੋਲ|ਸਾਡੇਕੋਲ|ਆਪਣੇ ਕੋਲ|ਹੋਰ|hor|"
    r"ਕੀ\s*.+\s*ਹੈ|kya\s+.+\s*hai"
    r")\s*",
    re.I,
)

_AVAIL_QUERY_SUFFIX_RE = re.compile(
    r"\s*(?:"
    r"available|availability|ਅਵੇਲੇਬਲ|"
    r"hai gi|haigi|ਹੈਗੀ|ਹੈਗੀ ਹੈ|"
    r"hai\??|hain\??|ਹੈ\??|ਹਨ\??|"
    r"kya hai|ਕੀ ਹੈ"
    r")\s*$",
    re.I,
)


def _strip_availability_phrases(text: str) -> str:
    t = (text or "").strip()
    for _ in range(3):
        prev = t
        t = _AVAIL_QUERY_PREFIX_RE.sub("", t).strip(" ,.?")
        t = _AVAIL_QUERY_SUFFIX_RE.sub("", t).strip(" ,.?")
        if t == prev:
            break
    return t


def _item_candidates_from_text(text: str) -> list[str]:
    raw = (text or "").strip()
    stripped = _strip_availability_phrases(raw)
    tokens = _DISH_TOKEN_RE.findall(raw)
    candidates: list[str] = []
    if stripped and len(stripped) >= 2:
        candidates.append(stripped)
    for i in range(len(tokens)):
        for j in range(i + 1, min(i + 4, len(tokens) + 1)):
            phrase = " ".join(tokens[i:j])
            if len(phrase) >= 2:
                candidates.append(phrase)
    seen: set[str] = set()
    out: list[str] = []
    for cand in sorted(candidates, key=len, reverse=True):
        key = cand.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(cand)
    return out


def extract_dish_query(text: str) -> str | None:
    """Best dish-name slice from a free-form caller utterance."""
    cache = _get_cache()
    best: tuple[dict, float] | None = None

    for candidate in _item_candidates_from_text(text):
        if cache:
            scored = cache.find_item_scored(candidate)
            if not scored:
                continue
            hit, confidence = scored
            if hit.available:
                item = {**hit.to_cart_dict(), "match_confidence": confidence}
            else:
                item = {**hit.to_cart_dict(), "unavailable": True, "match_confidence": confidence}
            if best is None or confidence > best[1]:
                best = (item, confidence)
        else:
            item = static_find_item(candidate)
            if item and (best is None or 1.0 > best[1]):
                best = ({**item, "match_confidence": 1.0}, 1.0)

    if best and best[1] >= 0.55:
        return best[0]["name"]
    return None


def resolve_item_dict_from_text(text: str) -> dict | None:
    """Best menu item dict from free-form caller text (chunk-first for questions)."""
    from restaurant.conversation import is_availability_question

    t = (text or "").strip()
    if not t:
        return None

    if is_availability_question(t):
        name = extract_dish_query(t)
        return find_item(name) if name else None

    from restaurant.clover.match import content_tokens

    if len(content_tokens(t)) > 2:
        name = extract_dish_query(t)
        if name:
            return find_item(name)

    direct = find_item(t)
    if direct and not direct.get("unavailable"):
        return direct

    name = extract_dish_query(t)
    if name:
        hit = find_item(name)
        if hit and not hit.get("unavailable"):
            return hit

    cache = _get_cache()
    if cache:
        hits = cache.search(t, limit=1)
        if hits and hits[0].available:
            return {**hits[0].to_cart_dict(), "match_confidence": 0.5}
    return None


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
    resolved = extract_dish_query(name) or name
    cache = _get_cache()
    if cache:
        hit = cache.find_item(resolved)
        if not hit:
            return f"'{name}' is not on our menu."
        return hit.describe()
    item = static_find_item(resolved)
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
    return resolve_item_dict_from_text(text)


def item_price_dollars(name: str) -> float | None:
    item = find_item(name)
    if not item:
        return None
    if "price" in item:
        return float(item["price"])
    if "price_cents" in item:
        return item["price_cents"] / 100.0
    return None
