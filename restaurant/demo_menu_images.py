"""Demo dish photos for Store when Clover has no item image yet.

Uses free Unsplash / Pexels CDN URLs (demo/sandbox only). Exact dish-name
matches first (Bizbull menu), then longest keyword, then category. Each exact
mapping uses a unique URL so the Store does not show the same photo twice.

When the merchant uploads real photos in Clover Dashboard and menu sync picks
them up, those URLs win — see MenuCache.catalog().

Disable with STORE_DEMO_IMAGES=0.
"""

from __future__ import annotations

import os
import re

_U = "https://images.unsplash.com/{id}?auto=format&fit=crop&w=640&h=480&q=80"
_P = (
    "https://images.pexels.com/photos/{id}/pexels-photo-{id}.jpeg"
    "?auto=compress&cs=tinysrgb&w=640&h=480&fit=crop"
)


def _u(photo_id: str) -> str:
    return _U.format(id=photo_id)


def _p(photo_id: int) -> str:
    return _P.format(id=photo_id)


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\s]", " ", text.lower())).strip()


# Exact Bizbull menu names → unique photo URL (keys normalized at load).
_RAW_EXACT: dict[str, str] = {
    # Starters & Snacks
    "samosa chaat (2 pcs)": _u("photo-1601050690597-df0568f70950"),
    "paneer tikka": _p(12737656),
    "chicken tikka": _u("photo-1599487488170-d11ec9c172f0"),
    "amritsari fish pakora": _u("photo-1519708227418-c8fd9a32b7a2"),
    "veg spring rolls (6 pcs)": _u("photo-1529042410759-befb1204b468"),
    "mixed pakora platter": _p(5863613),
    "honey chilli gobi": _p(7353377),
    # Tandoor & Grill
    "tandoori chicken (half)": _u("photo-1631515243349-e0cb75fb8d3a"),
    "tandoori chicken (full)": _u("photo-1642821373181-696a54913e93"),
    "seekh kebab (4 pcs)": _u("photo-1603360946369-dc9bb6258143"),
    "tandoori lamb chops": _u("photo-1534422298391-e4f8c172dddb"),
    "tandoori shrimp": _u("photo-1467003909585-2f8a72700288"),
    # Vegetarian Mains
    "dal makhani": _u("photo-1546833999-b9f581a1996d"),
    "sarson da saag": _p(5560763),
    "palak paneer": _p(2474661),
    "chole (chickpea curry)": _u("photo-1585937421612-70a008356fbe"),
    "paneer butter masala": _u("photo-1631452180519-c014fe946bc7"),
    "malai kofta": _p(958545),
    "dal tadka": _p(2474658),
    "mushroom matar": _p(2679501),
    "baigan bharta": _p(1117862),
    # Non-Veg Mains
    "butter chicken": _u("photo-1588168333986-5078d3ae3976"),
    "chicken tikka masala": _u("photo-1567188040759-fb8a883dc6d8"),
    "lamb rogan josh": _u("photo-1565557623262-b51c2513a641"),
    "goat curry": _u("photo-1455619452474-d2be8b1e70cd"),
    "punjabi fish curry": _u("photo-1498654896293-37aacf113fd9"),
    "chicken biryani": _u("photo-1563379091339-03b21ab4a4f8"),
    "lamb biryani": _p(1624487),
    "butter prawn masala": _p(5836771),
    # Breads & Rice
    "butter naan": _u("photo-1626074353765-517a681e40be"),
    "garlic naan": _u("photo-1626777552726-4a6b54c97e46"),
    "tandoori roti": _p(9609844),
    "aloo paratha": _p(2474660),
    "bhatura (single)": _p(1117863),
    "plain rice": _u("photo-1516684669134-de6f7c473a2a"),
    "jeera rice": _p(1234535),
    "saffron rice": _p(1049626),
    # Combos & Platters
    "chole bhature combo": _p(8969237),
    "veg lunch thali combo": _u("photo-1742281258189-3b933879867a"),
    "non-veg lunch combo": _p(6287525),
    "student combo": _p(5410400),
    "couple combo (for 2)": _u("photo-1414235077428-338989a2e8c0"),
    "family veg platter (serves 4)": _u("photo-1476224203421-9ac39bcb3327"),
    "non-veg deluxe platter (serves 4)": _u("photo-1504674900247-0877df9cc836"),
    "office party tray (serves 8)": _u("photo-1517248135467-4c7edcad34c4"),
    # Drinks
    "sweet lassi": _u("photo-1572490122747-3968b75cc699"),
    "salted lassi": _p(376464),
    "mango lassi": _p(1199957),
    "masala chai": _u("photo-1571934811356-5cc061b6821f"),
    "mango shake": _u("photo-1553279768-865429fa0078"),
    "soft drink (can)": _p(533325),
    "nimbu pani": _p(725991),
    # Desserts
    "gulab jamun (2 pcs)": _u("photo-1571115177098-24ec42ed204d"),
    "kheer": _p(1099680),
    "gajar halwa": _p(1640777),
    "rasmalai (2 pcs)": _u("photo-1563805042-7684c019e1cb"),
    "mango kulfi": _p(4393021),
    # Extras & Sides
    "raita": _u("photo-1512621776951-a57141f2eefd"),
    "mixed pickle": _p(1059905),
    "papad (2 pcs)": _p(2097090),
    "extra gravy (side)": _p(3026808),
}

_BY_EXACT: dict[str, str] = {}
_seen_exact_urls: set[str] = set()
for _label, _url in _RAW_EXACT.items():
    _key = _norm(_label)
    if _key in _BY_EXACT:
        raise RuntimeError(f"duplicate normalized dish key: {_key!r}")
    if _url in _seen_exact_urls:
        raise RuntimeError(f"duplicate exact image URL for {_label!r}")
    _seen_exact_urls.add(_url)
    _BY_EXACT[_key] = _url


# Longest-first keyword fallbacks for future menu items (URLs not used above).
_BY_KEYWORD: list[tuple[str, str]] = [
    ("chicken tikka masala", _u("photo-1565299624946-b28f40a0ae38")),
    ("butter chicken", _u("photo-1540189549336-e6e99c3679fe")),
    ("paneer butter", _u("photo-1482049016688-2d3e1b311543")),
    ("palak paneer", _u("photo-1567620905732-2d1ec7ab7445")),
    ("chicken biryani", _u("photo-1495521821757-a1efb6729352")),
    ("lamb biryani", _u("photo-1432139555190-58524dae6a55")),
    ("seekh kebab", _u("photo-1551782450-a2132b4ba21d")),
    ("tandoori chicken", _u("photo-1565958011703-44f9829ba187")),
    ("garlic naan", _u("photo-1484723091739-30a097e8f929")),
    ("butter naan", _u("photo-1498837167922-ddd27525d352")),
    ("gulab jamun", _u("photo-1504754524776-8f4f37790ca0")),
    ("mango lassi", _p(1351238)),
    ("masala chai", _p(1410235)),
    ("fish pakora", _p(3535383)),
    ("samosa", _u("photo-1589301760014-d929f3979dbc")),
    ("biryani", _p(461198)),
    ("tikka", _u("photo-1630383249896-424e482df921")),
    ("tandoori", _p(1640777)),  # reused only in keyword fallback path if exact miss
]

# Deduplicate keyword list: drop entries whose URL already appears in exact map
# or earlier keywords (keep first occurrence only).
def _unique_keywords(
    pairs: list[tuple[str, str]], reserved: set[str]
) -> list[tuple[str, str]]:
    seen = set(reserved)
    out: list[tuple[str, str]] = []
    for key, url in sorted(pairs, key=lambda kv: len(kv[0]), reverse=True):
        if url in seen:
            continue
        seen.add(url)
        out.append((key, url))
    return out


_RESERVED_URLS = set(_BY_EXACT.values())
_BY_KEYWORD = _unique_keywords(_BY_KEYWORD, _RESERVED_URLS)

_BY_CATEGORY: list[tuple[str, str]] = _unique_keywords(
    [
        ("dessert", _u("photo-1563805042-7684c019e1cb")),
        ("drink", _p(376464)),
        ("beverage", _p(533325)),
        ("bread", _u("photo-1626074353765-517a681e40be")),
        ("tandoor", _u("photo-1599487488170-d11ec9c172f0")),
        ("starter", _u("photo-1601050690597-df0568f70950")),
        ("snack", _p(7625052)),
        ("combo", _p(6544371)),
        ("platter", _u("photo-1476224203421-9ac39bcb3327")),
        ("rice", _u("photo-1516684669134-de6f7c473a2a")),
        ("veg", _p(2474661)),
        ("non", _u("photo-1588168333986-5078d3ae3976")),
        ("main", _u("photo-1585937421612-70a008356fbe")),
        ("side", _u("photo-1512621776951-a57141f2eefd")),
        ("extra", _p(3026808)),
    ],
    _RESERVED_URLS | {u for _, u in _BY_KEYWORD},
)

# Unused verified pool for deterministic unique fallback (never all the same).
_FALLBACK_POOL: list[str] = [
    u
    for u in [
        _u("photo-1540189549336-e6e99c3679fe"),
        _u("photo-1482049016688-2d3e1b311543"),
        _u("photo-1567620905732-2d1ec7ab7445"),
        _u("photo-1495521821757-a1efb6729352"),
        _u("photo-1432139555190-58524dae6a55"),
        _u("photo-1551782450-a2132b4ba21d"),
        _u("photo-1565958011703-44f9829ba187"),
        _u("photo-1484723091739-30a097e8f929"),
        _u("photo-1498837167922-ddd27525d352"),
        _u("photo-1504754524776-8f4f37790ca0"),
        _p(1351238),
        _p(1410235),
        _p(3535383),
        _p(461198),
    ]
    if u not in _RESERVED_URLS
]

_DEFAULT = _u("photo-1504674900247-0877df9cc836")


def demo_images_enabled() -> bool:
    return os.getenv("STORE_DEMO_IMAGES", "1").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def resolve_demo_image_url(*, name: str, category_name: str = "") -> str:
    """Exact dish name → keyword → category → hashed unique fallback."""
    exact = _norm(name)
    if exact in _BY_EXACT:
        return _BY_EXACT[exact]

    blob = _norm(f"{name} {category_name}")
    for keyword, url in _BY_KEYWORD:
        if keyword in blob:
            return url

    cat = _norm(category_name)
    for keyword, url in _BY_CATEGORY:
        if keyword in cat:
            return url

    if _FALLBACK_POOL:
        return _FALLBACK_POOL[hash(exact) % len(_FALLBACK_POOL)]
    return _DEFAULT


def extract_clover_image_url(raw: dict) -> str | None:
    """Best-effort image URL from a Clover inventory item payload (if present)."""
    for key in ("imageUrl", "image_url", "imageHref"):
        val = raw.get(key)
        if isinstance(val, str) and val.startswith(("http://", "https://")):
            return val.strip()

    image = raw.get("image")
    if isinstance(image, str) and image.startswith(("http://", "https://")):
        return image.strip()
    if isinstance(image, dict):
        for key in ("url", "href", "src", "imageUrl"):
            val = image.get(key)
            if isinstance(val, str) and val.startswith(("http://", "https://")):
                return val.strip()

    images = raw.get("images")
    if isinstance(images, list):
        for entry in images:
            if isinstance(entry, str) and entry.startswith(("http://", "https://")):
                return entry.strip()
            if isinstance(entry, dict):
                for key in ("url", "href", "src"):
                    val = entry.get(key)
                    if isinstance(val, str) and val.startswith(("http://", "https://")):
                        return val.strip()
    return None
