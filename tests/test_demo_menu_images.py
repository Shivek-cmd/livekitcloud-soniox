"""Demo menu images + catalog image_url for Store."""

from restaurant.clover.menu import MenuCache
from restaurant.clover.models import CachedMenuItem
from restaurant.demo_menu_images import (
    extract_clover_image_url,
    resolve_demo_image_url,
)


def _item(name: str, *, category: str = "Mains", image_url: str | None = None) -> CachedMenuItem:
    return CachedMenuItem(
        clover_item_id=name[:8].upper(),
        name=name,
        speak_as=name,
        voice_line=name,
        speech_mode="english",
        price_cents=1299,
        veg=True,
        available=True,
        category_id="",
        category_name=category,
        image_url=image_url,
    )


def test_resolve_demo_prefers_dish_keyword():
    url = resolve_demo_image_url(name="Butter Chicken", category_name="Curries")
    assert "unsplash.com" in url or "pexels.com" in url
    dessert = resolve_demo_image_url(
        name="Gulab Jamun (2 pcs)", category_name="Desserts"
    )
    assert dessert != url


def test_bizbull_menu_exact_images_are_unique():
    from pathlib import Path
    import json

    data = json.loads(Path("data/menu_cache_bizbull.json").read_text(encoding="utf-8"))
    urls = [
        resolve_demo_image_url(
            name=it["name"], category_name=it.get("category_name", "")
        )
        for it in data["items"]
    ]
    assert len(urls) == len(set(urls))


def test_extract_clover_image_url_shapes():
    assert extract_clover_image_url({"imageUrl": "https://cdn.example/a.jpg"}) == (
        "https://cdn.example/a.jpg"
    )
    assert extract_clover_image_url({"image": {"href": "https://cdn.example/b.jpg"}}) == (
        "https://cdn.example/b.jpg"
    )
    assert extract_clover_image_url({}) is None


def test_catalog_fills_demo_when_missing(monkeypatch):
    monkeypatch.delenv("STORE_DEMO_IMAGES", raising=False)
    cache = MenuCache(
        [_item("Chicken Biryani", category="Rice")],
        tenant_id="bizbull",
        synced_at="now",
    )
    cat = cache.catalog()["categories"][0]["items"][0]
    assert cat["image_url"]
    assert "unsplash.com" in cat["image_url"] or "pexels.com" in cat["image_url"]


def test_catalog_prefers_clover_image_over_demo(monkeypatch):
    monkeypatch.setenv("STORE_DEMO_IMAGES", "1")
    clover = "https://clover.example/item.png"
    cache = MenuCache(
        [_item("Butter Chicken", image_url=clover)],
        tenant_id="bizbull",
        synced_at="now",
    )
    cat = cache.catalog()["categories"][0]["items"][0]
    assert cat["image_url"] == clover


def test_catalog_can_disable_demo_fill(monkeypatch):
    monkeypatch.setenv("STORE_DEMO_IMAGES", "0")
    cache = MenuCache(
        [_item("Butter Chicken")],
        tenant_id="bizbull",
        synced_at="now",
    )
    cat = cache.catalog()["categories"][0]["items"][0]
    assert cat["image_url"] is None
