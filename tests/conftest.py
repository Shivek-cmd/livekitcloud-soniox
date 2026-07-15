"""Hermetic test suite fixtures (PR 070).

`restaurant/clover/client.py` runs `load_dotenv()` at import time, so
collecting ANY module that imports the Clover client puts `USE_CLOVER_MENU=1`
in the process env. The first `menu_provider._get_cache()` call after that
then pins the REAL production cache (`data/menu_cache_bizbull.json`) into
the module globals `_cache` / `_cache_loaded`, and nothing resets it — so
whichever test happens to run first (and whether it happens to touch the
menu provider) silently changes the behavior of every later test. This
autouse fixture makes every test start from a known, static-menu baseline.
"""

from __future__ import annotations

import pytest

from restaurant import menu_provider


@pytest.fixture(autouse=True)
def _no_real_menu_cache(monkeypatch):
    """Never let a test lazily load the production Clover cache.

    `_cache_loaded=True` + `_cache=None` short-circuits `_get_cache()` to
    the static menu fallback. Existing opt-in fixtures (e.g.
    tests/test_menu_match.py's `clover_cache`, tests/test_menu_browse.py's
    equivalent) override this via their own `monkeypatch.setattr` calls made
    later in the same test's fixture resolution, so they are unaffected.
    tests/test_menu_cache_load.py loads the real file directly via
    `MenuCache.load()`, bypassing these globals entirely — also unaffected.
    """
    monkeypatch.setattr(menu_provider, "_cache", None)
    monkeypatch.setattr(menu_provider, "_cache_loaded", True)
    monkeypatch.setenv("USE_CLOVER_MENU", "0")
