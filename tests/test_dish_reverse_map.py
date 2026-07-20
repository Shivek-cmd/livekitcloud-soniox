"""PR 085 (Gap 5): menu_provider.english_dish_reverse_map — the map feeding the
TTS DishNameFilter backstop. english-mode items map Gurmukhi speak_as → English
voice_line; deliberate gurmukhi-mode items are excluded so they stay Gurmukhi."""

from restaurant import menu_provider
from restaurant.clover.menu import MenuCache
from restaurant.clover.models import CachedMenuItem


def _item(iid, name, speak_as, voice_line, speech_mode):
    return CachedMenuItem(
        clover_item_id=iid,
        name=name,
        speak_as=speak_as,
        voice_line=voice_line,
        speech_mode=speech_mode,
        price_cents=1000,
        veg=False,
        available=True,
        category_id="",
        category_name="Test",
    )


def _cache() -> MenuCache:
    return MenuCache(
        [
            # english-mode: Gurmukhi speak_as only transliterates the English name
            _item("LAMB_BIRYANI", "Lamb Biryani", "ਲੈਮ ਬਿਰਿਆਨੀ", "Lamb Biryani", "english"),
            _item("BUTTER_CHICKEN", "Butter Chicken", "ਬਟਰ ਚਿਕਨ", "Butter Chicken", "english"),
            # gurmukhi-mode: deliberately spoken in Gurmukhi — must NOT be mapped
            _item("SAMOSA_CHAAT", "Samosa Chaat", "ਸਮੋਸਾ ਚਾਟ", "ਸਮੋਸਾ ਚਾਟ", "gurmukhi"),
            _item("KHEER", "Kheer", "ਖੀਰ", "ਖੀਰ", "gurmukhi"),
        ],
        tenant_id="test",
        synced_at="now",
    )


def test_reverse_map_english_mode_only(monkeypatch):
    monkeypatch.setattr(menu_provider, "_cache", _cache())
    monkeypatch.setattr(menu_provider, "_cache_loaded", True)

    m = menu_provider.english_dish_reverse_map()
    assert m["ਲੈਮ ਬਿਰਿਆਨੀ"] == "Lamb Biryani"
    assert m["ਬਟਰ ਚਿਕਨ"] == "Butter Chicken"
    # gurmukhi-mode dishes are never rewrite targets
    assert "ਸਮੋਸਾ ਚਾਟ" not in m
    assert "ਖੀਰ" not in m


def test_reverse_map_recomputes_when_cache_changes(monkeypatch):
    # identity-keyed cache: swapping the underlying cache object recomputes.
    monkeypatch.setattr(menu_provider, "_cache", _cache())
    monkeypatch.setattr(menu_provider, "_cache_loaded", True)
    first = menu_provider.english_dish_reverse_map()
    assert "ਲੈਮ ਬਿਰਿਆਨੀ" in first

    monkeypatch.setattr(menu_provider, "_cache", None)
    # static-menu fallback (conftest forces USE_CLOVER_MENU=0) → no biryani key
    second = menu_provider.english_dish_reverse_map()
    assert second is not first


def test_reverse_map_static_fallback(monkeypatch):
    # No Clover cache → best-effort map from the static menu's punjabi field.
    monkeypatch.setattr(menu_provider, "_cache", None)
    monkeypatch.setattr(menu_provider, "_cache_loaded", True)
    m = menu_provider.english_dish_reverse_map()
    # Static menu has Butter Chicken (ਬਟਰ ਚਿਕਨ) → English name.
    assert m.get("ਬਟਰ ਚਿਕਨ") == "Butter Chicken"
