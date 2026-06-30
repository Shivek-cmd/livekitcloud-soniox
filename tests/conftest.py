"""Shared pytest fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MENU_CACHE = ROOT / "data" / "menu_cache_bizbull.json"


@pytest.fixture
def clover_menu(monkeypatch):
    """Load Bizbull menu cache for integration tests (skips if cache missing)."""
    if not MENU_CACHE.is_file():
        pytest.skip("data/menu_cache_bizbull.json required")

    from restaurant.clover.menu import MenuCache
    import restaurant.menu_provider as mp

    cache = MenuCache.load(MENU_CACHE)
    monkeypatch.setattr(mp, "_get_cache", lambda: cache)
    monkeypatch.setattr(mp, "_cache_loaded", True)
    monkeypatch.setattr(mp, "use_clover_menu", lambda: True)
    yield cache
    mp._cache = None
    mp._cache_loaded = False
