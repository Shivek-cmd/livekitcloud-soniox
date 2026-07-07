"""PR 057 — item availability matching + ਕੋਲ/Chole false-positive fix."""

import pytest

from restaurant import menu_provider
from restaurant.clover.menu import MenuCache
from restaurant.clover.models import CachedMenuItem
from restaurant.conversation import (
    CustomerLanguage,
    format_availability_reply,
    is_availability_question,
    detect_intent,
)
from restaurant.menu_browse import resolve_browse_target


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
        _item("KHEER", "Kheer", "ਖੀਰ", "ਖੀਰ", ["kheer"], category="Desserts"),
        _item(
            "GULAB",
            "Gulab Jamun (2 pcs)",
            "ਗੁਲਾਬ ਜਾਮੁਨ",
            "ਗੁਲਾਬ ਜਾਮੁਨ",
            ["gulab jamun"],
            category="Desserts",
        ),
        _item(
            "CHOLE",
            "Chole (Chickpea Curry)",
            "ਛੋਲੇ",
            "ਛੋਲੇ",
            ["chole"],
            category="Vegetarian Mains",
        ),
    ]
    return MenuCache(items, tenant_id="test", synced_at="now")


@pytest.fixture
def avail_cache(monkeypatch):
    cache = _cache()
    monkeypatch.setattr(menu_provider, "_cache", cache)
    monkeypatch.setattr(menu_provider, "_cache_loaded", True)
    return cache


def test_kol_stopword_prevents_chole_false_match(avail_cache):
    q = "ਸਾਡੇ ਕੋਲ ਖੀਰ ਹੈਗੀ ਹੈ?"
    hit = menu_provider.find_item(q)
    resolved = menu_provider.resolve_item_dict_from_text(q)
    assert hit is None or hit["name"] != "Chole (Chickpea Curry)"
    assert resolved is not None
    assert resolved["name"] == "Kheer"


def test_extract_dish_query_kheer(avail_cache):
    assert menu_provider.extract_dish_query("ਸਾਡੇ ਕੋਲ ਖੀਰ ਹੈਗੀ ਹੈ?") == "Kheer"
    assert menu_provider.extract_dish_query("ਖੀਰ, ਖੀਰ ਹੈਗੀ ਹੈ, ਖੀਰ") == "Kheer"


def test_gulab_jamun_availability_phrase(avail_cache):
    q = "ਗੁਲਾਬ ਜਾਮੁਨ ਅਵੇਲੇਬਲ ਹੈ?"
    resolved = menu_provider.resolve_item_dict_from_text(q)
    assert resolved is not None
    assert resolved["name"] == "Gulab Jamun (2 pcs)"


def test_is_availability_question():
    assert is_availability_question("ਸਾਡੇ ਕੋਲ ਖੀਰ ਹੈਗੀ ਹੈ?") is True
    assert is_availability_question("ਗੁਲਾਬ ਜਾਮੁਨ ਅਵੇਲੇਬਲ ਹੈ?") is True
    assert is_availability_question("ਇੱਕ ਖੀਰ ਆਰਡਰ ਕਰਨੀ") is False


def test_availability_intent_detected():
    assert detect_intent("ਗੁਲਾਬ ਜਾਮੁਨ ਅਵੇਲੇਬਲ ਹੈ?") == "ask_availability"


def test_format_availability_reply_punjabi(avail_cache):
    item = menu_provider.find_item("Kheer")
    line = format_availability_reply(item, CustomerLanguage.PUNJABI)
    assert "ਖੀਰ" in line
    assert "available" in line


def test_desert_punjabi_alias():
    target = resolve_browse_target("ਡੈਜ਼ਰਟ")
    assert target is not None
    assert target.category_name == "Desserts"
