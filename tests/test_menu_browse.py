"""PR 056 — category and dish-family menu browse."""

import pytest

from restaurant import menu_provider
from restaurant.clover.menu import MenuCache
from restaurant.clover.models import CachedMenuItem
from restaurant.conversation import (
    extract_browse_query,
    format_browse_reply,
    is_category_browse_query,
    CustomerLanguage,
)
from restaurant.menu_browse import resolve_browse_target, BrowseKind


def _item(iid, name, speak_as, voice_line, aliases, *, category="Test", price=1000):
    return CachedMenuItem(
        clover_item_id=iid,
        name=name,
        speak_as=speak_as,
        voice_line=voice_line,
        speech_mode="gurmukhi",
        price_cents=price,
        veg=True,
        available=True,
        category_id="",
        category_name=category,
        aliases=aliases,
    )


def _cache(items=None) -> MenuCache:
    items = items or [
        _item(
            "GULAB",
            "Gulab Jamun (2 pcs)",
            "ਗੁਲਾਬ ਜਾਮੁਨ",
            "ਗੁਲਾਬ ਜਾਮੁਨ",
            ["gulab jamun"],
            category="Desserts",
        ),
        _item(
            "GAJAR",
            "Gajar Halwa",
            "ਗਾਜਰ ਦਾ ਹਲਵਾ",
            "ਗਾਜਰ ਦਾ ਹਲਵਾ",
            ["gajar halwa"],
            category="Desserts",
        ),
        _item(
            "KHEER",
            "Kheer",
            "ਖੀਰ",
            "ਖੀਰ",
            ["kheer"],
            category="Desserts",
        ),
        _item(
            "SWEET_LASSI",
            "Sweet Lassi",
            "ਮਿੱਠੀ ਲੱਸੀ",
            "Sweet Lassi",
            ["sweet lassi"],
            category="Drinks",
        ),
        _item(
            "FISH_CURRY",
            "Punjabi Fish Curry",
            "ਪੰਜਾਬੀ ਮੱਛੀ ਕਰੀ",
            "ਪੰਜਾਬੀ ਮੱਛੀ ਕਰੀ",
            ["fish curry"],
            category="Non-Veg Mains",
        ),
        _item(
            "FISH_PAKORA",
            "Amritsari Fish Pakora",
            "ਅੰਮ੍ਰਿਤਸਰੀ ਮੱਛੀ ਪਕੋੜਾ",
            "Fish Pakora",
            ["fish pakora"],
            category="Starters & Snacks",
        ),
        _item(
            "PANEER_1",
            "Palak Paneer",
            "ਪਾਲਕ ਪਨੀਰ",
            "ਪਾਲਕ ਪਨੀਰ",
            ["palak paneer"],
            category="Vegetarian Mains",
        ),
        _item(
            "PANEER_2",
            "Paneer Butter Masala",
            "ਪਨੀਰ ਬਟਰ ਮਸਾਲਾ",
            "ਪਨੀਰ ਬਟਰ ਮਸਾਲਾ",
            ["paneer butter masala"],
            category="Vegetarian Mains",
        ),
    ]
    return MenuCache(items, tenant_id="test", synced_at="now")


@pytest.fixture
def browse_cache(monkeypatch):
    cache = _cache()
    monkeypatch.setattr(menu_provider, "_cache", cache)
    monkeypatch.setattr(menu_provider, "_cache_loaded", True)
    return cache


def test_resolve_mithai_to_desserts_category():
    target = resolve_browse_target("mithai")
    assert target is not None
    assert target.kind == BrowseKind.CATEGORY
    assert target.category_name == "Desserts"


def test_resolve_fish_family():
    target = resolve_browse_target("machhi")
    assert target is not None
    assert target.kind == BrowseKind.FAMILY
    assert target.label == "fish"


def test_browse_mithai_returns_desserts_not_empty(browse_cache):
    topic, options = menu_provider.browse_menu_options("mithai")
    assert topic == "desserts"
    names = {o["name"] for o in options}
    assert "Gulab Jamun (2 pcs)" in names
    assert "Gajar Halwa" in names


def test_browse_sweet_returns_desserts_not_sweet_lassi(browse_cache):
    topic, options = menu_provider.browse_menu_options("sweet")
    names = {o["name"] for o in options}
    assert "Sweet Lassi" not in names
    assert "Gulab Jamun (2 pcs)" in names or "Gajar Halwa" in names


def test_browse_fish_returns_both_dishes(browse_cache):
    topic, options = menu_provider.browse_menu_options("fish")
    names = {o["name"] for o in options}
    assert names == {"Punjabi Fish Curry", "Amritsari Fish Pakora"}


def test_browse_paneer_family(browse_cache):
    topic, options = menu_provider.browse_menu_options("paneer")
    names = {o["name"] for o in options}
    assert "Palak Paneer" in names
    assert "Paneer Butter Masala" in names


def test_browse_tool_format_caps_spoken_items(browse_cache):
    result = menu_provider.browse_menu("desserts")
    assert "Gajar Halwa" in result
    assert "mention at most TWO" in result


def test_extract_browse_query_strips_question_words():
    assert extract_browse_query("what desserts do you have") == "desserts"
    assert extract_browse_query("mithai kya hai") == "mithai"


def test_is_category_browse_question_not_add_order():
    assert is_category_browse_query("what fish do you have") is True
    assert is_category_browse_query("mithai kya hai") is True
    assert is_category_browse_query("fish") is True
    assert is_category_browse_query("ਹਾਂ ਜੀ, ਮੈਨੂੰ ਇੱਕ ਫਿਸ਼ ਆਰਡਰ ਕਰਨੀ ਸੀ ਜੀ") is False
    assert is_category_browse_query("ਇੱਕ ਫਿਸ਼ ਚਾਹੀਦੀ") is False


def test_format_browse_reply_two_items_punjabi():
    options = [
        {"name": "A", "voice_line": "ਡਿਸ਼ ਏ"},
        {"name": "B", "voice_line": "ਡਿਸ਼ ਬੀ"},
    ]
    line = format_browse_reply(options, CustomerLanguage.PUNJABI)
    assert "ਡਿਸ਼ ਏ" in line
    assert "ਡਿਸ਼ ਬੀ" in line
    assert "ਕਿਹੜਾ" in line
