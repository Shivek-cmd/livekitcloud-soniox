"""PR 056 — category and dish-family menu browse."""

import pytest

from restaurant import menu_provider
from restaurant.clover.menu import MenuCache
from restaurant.clover.models import CachedMenuItem
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


# The old browse-intent helpers (extract_browse_query, is_category_browse_query,
# format_browse_reply) died with conversation.py — the LLM now decides when to
# browse and phrases the reply; browse_menu's tool text is checked above.


# ── named-dish pinning ───────────────────────────────────────────────────────
# Live-call bug: asking "do you have gajar halwa?" answered "no, but we have
# Mango Kulfi and Rasmalai". The query matched the Desserts CATEGORY, the dish
# itself landed outside the two options we speak, and the model read that
# omission as unavailability — while add_item resolved the same dish fine.


def test_specific_dish_outranks_its_own_category(browse_cache):
    _topic, options = menu_provider.browse_menu_options("gajar halwa")
    assert options[0]["name"] == "Gajar Halwa"
    assert options[0]["named"] is True


def test_specific_dish_pinned_via_alias(browse_cache):
    _topic, options = menu_provider.browse_menu_options("carrot halwa")
    assert options[0]["name"] == "Gajar Halwa"


def test_specific_dish_pinned_from_gurmukhi_availability_question(browse_cache):
    _topic, options = menu_provider.browse_menu_options("ਗਾਜਰ ਹਲਵਾ ਹੈਗਾ?")
    assert options[0]["name"] == "Gajar Halwa"


def test_named_dish_tool_result_says_yes(browse_cache):
    result = menu_provider.browse_menu("gajar halwa")
    assert result.startswith("YES")
    assert "Gajar Halwa" in result
    assert "never deny it" in result or "Confirm we have it" in result


def test_bare_category_term_still_browses(browse_cache):
    # "dessert" names no dish — it must stay a category browse, not collapse
    # onto whichever single item happens to score highest.
    result = menu_provider.browse_menu("dessert")
    assert not result.startswith("YES")
    assert "mention at most TWO" in result


def test_browse_miss_is_not_an_absolute_negative(browse_cache):
    result = menu_provider.browse_menu("zzzznotadish")
    assert "No menu items found" in result  # analytics event keys off this
    assert "NOT proof" in result
    assert "check_menu_item" in result


def test_hidden_extras_are_named_for_the_model(browse_cache):
    # The model must never conclude a truncated item is absent.
    result = menu_provider.browse_menu("desserts")
    assert "Kheer" in result


def test_search_and_check_agree_on_every_dish(browse_cache):
    """The invariant behind the bug: the two lookups must never disagree."""
    for item in browse_cache._items:
        check = menu_provider.check_item(item.name)
        assert "is not on our menu" not in check, item.name
        browse = menu_provider.browse_menu(item.name)
        assert "No menu items found" not in browse, item.name
        assert item.name in browse, item.name


def test_naan_and_lassi_resolve_to_their_own_family():
    # These fell through to the whole Breads & Rice / Drinks category, so
    # asking for naan offered Saffron Rice.
    for term in ("naan", "ਨਾਨ", "lassi", "ਲੱਸੀ"):
        target = resolve_browse_target(term)
        assert target is not None, term
        assert target.kind == BrowseKind.FAMILY, term
