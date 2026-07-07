"""Stage 2/3 tests: resolver against the REAL menu, and the proposal parser.

The resolver test uses the actual shipped cache (data/menu_cache_bizbull.json)
so it reflects the real restaurant, including the two fish dishes that caused
the live bug.
"""

import os
from pathlib import Path

import pytest

from restaurant.engine.core import Ambiguous, NotFound, Resolved
from restaurant.engine.extractor import parse_proposal
from restaurant.engine.resolver import CloverResolver

CACHE_PATH = Path("data/menu_cache_bizbull.json")


@pytest.fixture(scope="module")
def resolver():
    from restaurant.clover.menu import MenuCache

    if not CACHE_PATH.is_file():
        pytest.skip("real menu cache not present")
    return CloverResolver(MenuCache.load(CACHE_PATH))


# ---- resolver against the real menu --------------------------------------- #
def test_ambiguous_fish_is_ambiguous(resolver):
    res = resolver.resolve("fish")
    assert isinstance(res, Ambiguous)
    names = {d.name for d in res.options}
    assert names == {"Punjabi Fish Curry", "Amritsari Fish Pakora"}


def test_gurmukhi_fish_is_ambiguous(resolver):
    res = resolver.resolve("ਮੱਛੀ")
    assert isinstance(res, Ambiguous)
    assert len(res.options) == 2


def test_specific_dish_resolves(resolver):
    res = resolver.resolve("fish curry")
    assert isinstance(res, Resolved)
    assert res.dish.name == "Punjabi Fish Curry"
    assert res.dish.price > 0


def test_nonsense_is_not_found(resolver):
    assert isinstance(resolver.resolve("unicorn burger deluxe"), NotFound)


def test_spice_flag_detected(resolver):
    res = resolver.resolve("fish curry")
    assert isinstance(res, Resolved)
    assert res.dish.has_spice is True   # Fish Curry has a Spice Level group


# ---- proposal parser (defensive) ------------------------------------------ #
def test_parse_clean_json():
    p = parse_proposal('{"adds":[{"query":"fish curry","quantity":1}]}')
    assert len(p.adds) == 1
    assert p.adds[0].query == "fish curry" and p.adds[0].quantity == 1


def test_parse_strips_markdown_fence_and_prose():
    raw = 'Sure!\n```json\n{"yes": true, "order_type": "pickup"}\n```'
    p = parse_proposal(raw)
    assert p.yes is True and p.order_type == "pickup"


def test_parse_null_quantity_is_preserved_not_defaulted():
    p = parse_proposal('{"adds":[{"query":"naan","quantity":null}]}')
    assert p.adds[0].quantity is None   # engine will ASK, never invent


def test_parse_correction_needs_quantity():
    p = parse_proposal('{"corrections":[{"query":"naan","quantity":2}]}')
    assert p.corrections == [("naan", 2)]


def test_parse_garbage_is_safe():
    p = parse_proposal("this is not json at all")
    assert p.understood is False
    assert p.adds == [] and p.corrections == []


def test_parse_bad_order_type_ignored():
    p = parse_proposal('{"order_type":"maybe"}')
    assert p.order_type is None


def test_parse_phone_digits_only():
    p = parse_proposal('{"phone":"(941) 375-2688"}')
    assert p.phone == "9413752688"
