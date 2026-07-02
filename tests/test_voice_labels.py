"""PR 033 — voice lines speak the customer's word; slang aliases resolve.

These tests run against the real data/clover_voice_labels.json so any future
data edit that reintroduces translated voice lines or breaks matching fails CI.
"""

import json
from pathlib import Path

import pytest

from restaurant.clover.menu import MenuCache
from restaurant.clover.models import CachedMenuItem

LABELS_PATH = Path(__file__).resolve().parent.parent / "data" / "clover_voice_labels.json"


def _cache_from_labels() -> MenuCache:
    data = json.loads(LABELS_PATH.read_text(encoding="utf-8"))
    items = [
        CachedMenuItem(
            clover_item_id=e["clover_item_id"],
            name=e["clover_name"],
            speak_as=e.get("speak_as") or e["clover_name"],
            voice_line=e["voice_line"],
            speech_mode=e["speech_mode"],
            price_cents=e.get("price_cents") or 0,
            veg=bool(e.get("veg", True)),
            available=True,
            category_id="",
            category_name=e.get("category_key", ""),
            aliases=list(e.get("aliases") or []),
        )
        for e in data["items"]
    ]
    return MenuCache(items, tenant_id="labels", synced_at="test")


@pytest.fixture(scope="module")
def cache() -> MenuCache:
    return _cache_from_labels()


def _find(cache: MenuCache, query: str) -> str | None:
    hit = cache.find_item(query)
    return hit.name if hit else None


# ---------------------------------------------------------------------------
# Full-menu self-audit: every label resolves back to its own item


def test_every_label_resolves_to_itself(cache):
    wrong: list[str] = []
    for item in cache._items:
        for q in {item.name, item.speak_as, item.voice_line, *item.aliases}:
            if not q or not q.strip():
                continue
            hit = cache.find_item(q)
            if hit is None or hit.clover_item_id != item.clover_item_id:
                got = hit.name if hit else "ABSTAIN"
                wrong.append(f"{q!r} -> {got} (expected {item.name})")
    assert not wrong, "\n".join(wrong)


# ---------------------------------------------------------------------------
# PR 033 voice line fixes — Sierra speaks the customer's word


def test_no_translated_voice_lines(cache):
    """The 7 owner-approved fixes: menu-card names, no Kesar/Mishrit/Bakre."""
    expected = {
        "Saffron Rice": ("Saffron Rice", "english"),
        "Plain Rice": ("Plain Rice", "english"),
        "Jeera Rice": ("Jeera Rice", "english"),
        "Goat Curry": ("Goat Curry", "english"),
        "Punjabi Fish Curry": ("Punjabi Fish Curry", "english"),
        "Mixed Pakora Platter": ("ਮਿਕਸ ਪਕੋੜਾ ਪਲੇਟਰ", "gurmukhi"),
        "Mixed Pickle": ("ਮਿਕਸ ਅਚਾਰ", "gurmukhi"),
        "Tandoori Chicken (Half)": ("Half Tandoori Chicken", "english"),
        "Tandoori Chicken (Full)": ("Full Tandoori Chicken", "english"),
    }
    by_name = {i.name: i for i in cache._items}
    for name, (voice_line, mode) in expected.items():
        item = by_name[name]
        assert item.voice_line == voice_line, f"{name}: {item.voice_line!r}"
        assert item.speech_mode == mode
    # the translated word must be gone from every voice line
    assert not any("ਮਿਸ਼ਰਿਤ" in i.voice_line for i in cache._items)


def test_no_two_items_share_a_voice_line(cache):
    """Every spoken line must identify exactly one item (Half/Full bug)."""
    from restaurant.clover.match import normalize

    seen: dict[str, str] = {}
    for item in cache._items:
        line = normalize(item.voice_line)
        assert line not in seen, f"{item.name} and {seen[line]} both say {item.voice_line!r}"
        seen[line] = item.name


def test_deliberately_kept_punjabi(cache):
    """Owner-reviewed keeps: natural Punjabi stays Punjabi."""
    by_name = {i.name: i for i in cache._items}
    assert by_name["Sweet Lassi"].voice_line == "ਮਿੱਠੀ ਲੱਸੀ"
    assert by_name["Salted Lassi"].voice_line == "ਨਮਕੀਨ ਲੱਸੀ"
    assert by_name["Chole Bhature Combo"].speech_mode == "gurmukhi"


# ---------------------------------------------------------------------------
# Slang / old-word aliases still resolve to the right item


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("shikanji", "Nimbu Pani"),
        ("shikanjvi", "Nimbu Pani"),
        ("ਸ਼ਿਕੰਜੀ", "Nimbu Pani"),  # cross-script via phonetic key
        ("kesar chawal", "Saffron Rice"),
        ("ਕੇਸਰ ਚਾਵਲ", "Saffron Rice"),  # old spoken form still matches (speak_as)
        ("sada chawal", "Plain Rice"),
        ("bakre da masala", "Goat Curry"),
        ("bakra", "Goat Curry"),
        ("ਬਕਰੇ ਦਾ ਮਸਾਲਾ", "Goat Curry"),
        ("mitthi lassi", "Sweet Lassi"),
        ("namkeen lassi", "Salted Lassi"),
        ("machhi", "Punjabi Fish Curry"),
        ("mix pakora platter", "Mixed Pakora Platter"),
        ("ਮਿਕਸ ਪਕੌੜਾ ਪਲੈਟਰ", "Mixed Pakora Platter"),  # live-bug STT spelling
        ("ਮਿਸ਼ਰਿਤ ਪਕੋੜਾ ਪਲੇਟਰ", "Mixed Pakora Platter"),  # old voice line
    ],
)
def test_alias_resolves(cache, query, expected):
    assert _find(cache, query) == expected
