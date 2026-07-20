"""PR 086 (Gap 6) — grounded get_recommendations: menu items with veg/non-veg.

The LLM has zero menu content in context; recommendations may only come from
this tool. Selection must be deterministic (mains first, cache order within a
category) and every returned dish must be a real, available menu item.
"""

import pytest

from restaurant import menu_provider
from restaurant.clover.menu import MenuCache
from restaurant.clover.models import CachedMenuItem
from restaurant.menu_provider import (
    _format_recommendations_tool_result,
    get_recommendations,
    recommendation_options,
)


def _item(iid, name, voice_line, *, veg, category, available=True):
    return CachedMenuItem(
        clover_item_id=iid,
        name=name,
        speak_as=voice_line,
        voice_line=voice_line,
        speech_mode="english",
        price_cents=1000,
        veg=veg,
        available=available,
        category_id="",
        category_name=category,
        aliases=[],
    )


def _cache() -> MenuCache:
    # Cache order deliberately scrambled vs. the recommendation priority so the
    # tests prove the mains-first ordering, not insertion order.
    items = [
        _item("KHEER", "Kheer", "Kheer", veg=True, category="Desserts"),
        _item("PANEER_TIKKA", "Paneer Tikka", "Paneer Tikka", veg=True, category="Tandoor & Grill"),
        _item("CHICKEN_TIKKA", "Chicken Tikka", "Chicken Tikka", veg=False, category="Tandoor & Grill"),
        _item("DAL_MAKHANI", "Dal Makhani", "Dal Makhani", veg=True, category="Vegetarian Mains"),
        _item("CHOLE", "Chole Bhature", "Chole Bhature", veg=True, category="Vegetarian Mains"),
        _item("LAMB_BIRYANI", "Lamb Biryani", "Lamb Biryani", veg=False, category="Non-Veg Mains"),
        _item("GOAT_CURRY", "Goat Curry", "Goat Curry", veg=False, category="Non-Veg Mains", available=False),
        _item("BUTTER_CHICKEN", "Butter Chicken", "Butter Chicken", veg=False, category="Non-Veg Mains"),
        _item("MANGO_LASSI", "Mango Lassi", "Mango Lassi", veg=True, category="Drinks"),
    ]
    return MenuCache(items, tenant_id="test", synced_at="now")


@pytest.fixture
def clover_cache(monkeypatch):
    cache = _cache()
    monkeypatch.setattr(menu_provider, "_cache", cache)
    monkeypatch.setattr(menu_provider, "_cache_loaded", True)
    return cache


@pytest.fixture
def static_menu(monkeypatch):
    monkeypatch.setattr(menu_provider, "_cache", None)
    monkeypatch.setattr(menu_provider, "_cache_loaded", True)


# ── recommendation_options ────────────────────────────────────────────────────

def test_veg_preference_excludes_non_veg(clover_cache):
    options = recommendation_options("veg")
    assert options, "veg options expected"
    assert all(o["veg"] for o in options)
    # Vegetarian Mains first (cache order within), then Tandoor & Grill.
    assert [o["name"] for o in options][:3] == ["Dal Makhani", "Chole Bhature", "Paneer Tikka"]


def test_non_veg_preference_excludes_veg_and_unavailable(clover_cache):
    options = recommendation_options("non-veg")
    names = [o["name"] for o in options]
    assert names[:2] == ["Lamb Biryani", "Butter Chicken"]  # Non-Veg Mains first
    assert "Goat Curry" not in names  # unavailable
    assert all(not o["veg"] for o in options)


def test_any_preference_returns_both(clover_cache):
    options = recommendation_options("any")
    names = [o["name"] for o in options]
    assert "Dal Makhani" in names and "Lamb Biryani" in names


def test_preference_normalization(clover_cache):
    assert recommendation_options("vegetarian") == recommendation_options("veg")
    assert recommendation_options("non veg") == recommendation_options("non-veg")
    assert recommendation_options("nonveg") == recommendation_options("non-veg")
    assert recommendation_options("") == recommendation_options("any")


def test_category_filter(clover_cache):
    options = recommendation_options("any", "dessert")
    assert [o["name"] for o in options] == ["Kheer"]
    tandoor = recommendation_options("veg", "tandoor")
    assert [o["name"] for o in tandoor] == ["Paneer Tikka"]


def test_category_substring_fallback(clover_cache):
    # "mains" is not a browse alias — falls back to category_name substring,
    # matching both mains categories; veg mains still sort first.
    options = recommendation_options("any", "mains")
    assert [o["name"] for o in options] == [
        "Dal Makhani",
        "Chole Bhature",
        "Lamb Biryani",
        "Butter Chicken",
    ]


def test_limit_honored(clover_cache):
    assert len(recommendation_options("any", limit=2)) == 2
    assert len(recommendation_options("any", limit=4)) == 4


def test_options_carry_voice_line_and_veg(clover_cache):
    options = recommendation_options("veg", limit=1)
    assert options == [{"name": "Dal Makhani", "voice_line": "Dal Makhani", "veg": True}]


# ── formatter ─────────────────────────────────────────────────────────────────

def test_formatter_spoken_two_plus_extras(clover_cache):
    result = get_recommendations("non-veg")
    assert "at most TWO" in result
    assert "never a list" in result
    assert '(non-veg)' in result
    assert 'Lamb Biryani → say "Lamb Biryani" (non-veg)' in result
    # Third match (Chicken Tikka) is carried as an extra, not a spoken line.
    assert "+1 more — offer if they want more" in result
    assert "Chicken Tikka" in result


def test_formatter_veg_tags(clover_cache):
    result = get_recommendations("veg")
    assert '(veg)' in result and "(non-veg)" not in result


def test_formatter_empty(clover_cache):
    result = get_recommendations("veg", "nonexistent category xyz")
    assert result == "No matching items — offer to search the menu instead."


def test_formatter_no_extras_tail_when_two_or_fewer():
    options = [
        {"name": "Kheer", "voice_line": "Kheer", "veg": True},
        {"name": "Gulab Jamun", "voice_line": "Gulab Jamun", "veg": True},
    ]
    result = _format_recommendations_tool_result(options)
    assert "more — offer" not in result
    assert "at most TWO" in result


# ── static-menu fallback ──────────────────────────────────────────────────────

def test_static_fallback_veg_filter(static_menu):
    options = recommendation_options("veg")
    assert options, "static fallback should yield veg items"
    assert all(o["veg"] for o in options)
    assert all(o["voice_line"] == o["name"] for o in options)


def test_static_fallback_non_veg(static_menu):
    options = recommendation_options("non-veg")
    assert options and all(not o["veg"] for o in options)


def test_static_fallback_category(static_menu):
    options = recommendation_options("any", "dessert")
    assert options
    from restaurant.menu import MENU

    dessert_names = {i["name"] for i in MENU["desserts"]["items"]}
    assert all(o["name"] in dessert_names for o in options)
