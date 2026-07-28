"""Category and dish-family browse resolution (PR 056).

Maps vague caller terms ("mithai", "fish", "paneer dishes") to real menu
items for browse replies — never guesses a single dish on ambiguous input.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from restaurant.clover.match import normalize


class BrowseKind(str, Enum):
    CATEGORY = "category"
    FAMILY = "family"
    DISAMBIGUATION = "disambiguation"


@dataclass(frozen=True)
class BrowseTarget:
    kind: BrowseKind
    label: str
    category_name: str | None = None
    item_names: tuple[str, ...] = ()
    name_contains: str | None = None
    # The alias that won, so callers can tell a bare category term ("combo")
    # from a specific dish that merely contains one ("student combo").
    matched_alias: str = ""


# Clover category_name values in menu_cache_bizbull.json
_CATEGORY_SPECS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    (
        "desserts",
        "Desserts",
        (
            "dessert",
            "desserts",
            "desert",
            "mithai",
            "mitha",
            "sweet",
            "sweets",
            "halwa",
            "ਮਿੱਠਾ",
            "ਮਿੱਠੇ",
            "ਮਿਠਾਈ",
            "ਡੈਜ਼ਰਟ",
            "ਡੈਸਰਟ",
            # Soniox transcribes the same word with either vowel.
            "ਡਿਜ਼ਰਟ",
            "ਡਿਸਰਟ",
            "मिठाई",
            "मिठा",
            "मिठाई",
            "डेज़र्ट",
        ),
    ),
    (
        "drinks",
        "Drinks",
        (
            "drink",
            "drinks",
            "beverage",
            "beverages",
            "peena",
            "lassi",
            "shake",
            "ਸ਼ਰਬਤ",
            "पीना",
            "पेय",
        ),
    ),
    (
        "starters",
        "Starters & Snacks",
        (
            "starter",
            "starters",
            "snack",
            "snacks",
            "appetizer",
            "appetizers",
            "ਸ਼ੁਰੂਆਤ",
            "नाश्ता",
            "स्टार्टर",
        ),
    ),
    (
        "veg_mains",
        "Vegetarian Mains",
        (
            "veg main",
            "veg mains",
            "vegetarian",
            "vegetarian main",
            "sabzi",
            "ਸਬਜ਼ੀ",
            "सब्जी",
            "शाकाहारी",
        ),
    ),
    (
        "nonveg_mains",
        "Non-Veg Mains",
        (
            "non veg",
            "nonveg",
            "non veg main",
            "nonveg main",
            "mutton",
            "goat",
            "ਮੀਟ",
            "मांस",
        ),
    ),
    (
        "breads_rice",
        "Breads & Rice",
        (
            "bread",
            "breads",
            "rice",
            "chawal",
            "roti",
            "naan",
            "ਨਾਨ",
            "ਰੋਟੀ",
            "चावल",
            "रोटी",
        ),
    ),
    (
        "combos",
        "Combos & Platters",
        (
            "combo",
            "combos",
            "platter",
            "platters",
            "thali",
            "ਕੰਬੋ",
            "थाली",
        ),
    ),
    (
        "tandoor",
        "Tandoor & Grill",
        (
            "tandoor",
            "tikka",
            "kebab",
            "grill",
            "ਤੰਦੂਰ",
            "टिक्का",
        ),
    ),
    (
        "extras",
        "Extras & Sides",
        (
            "side",
            "sides",
            "extra",
            "extras",
            "raita",
            "papad",
            "ਸਾਈਡ",
            "साइड",
        ),
    ),
)

_FAMILY_SPECS: tuple[tuple[str, tuple[str, ...], tuple[str, ...] | None, str | None], ...] = (
    (
        "fish",
        ("fish", "machhi", "machi", "machhi", "ਮੱਛੀ", "ਫਿਸ਼", "मछी", "फिश"),
        ("Amritsari Fish Pakora", "Punjabi Fish Curry"),
        None,
    ),
    (
        "paneer",
        ("paneer", "ਪਨੀਰ", "पनीर"),
        None,
        "paneer",
    ),
    (
        "chicken",
        ("chicken", "murgh", "ਚਿਕਨ", "चिकन", "मुर्ग"),
        None,
        "chicken",
    ),
    # Without these, "naan" and "lassi" fall through to their whole CATEGORY
    # (Breads & Rice / Drinks) and the caller asking for naan gets offered
    # Saffron Rice.
    (
        "naan",
        ("naan", "nan", "ਨਾਨ", "नान"),
        None,
        "naan",
    ),
    (
        "lassi",
        ("lassi", "ਲੱਸੀ", "ਲਸੀ", "लस्सी"),
        None,
        "lassi",
    ),
)


def _alias_in_query(alias: str, query_norm: str) -> bool:
    a = normalize(alias)
    if not a or len(a) < 2:
        return False
    if query_norm == a:
        return True
    # Whole-token match inside longer phrases ("what paneer do you have").
    tokens = query_norm.split()
    if a in tokens:
        return True
    # Multi-word alias as substring ("veg main").
    if " " in a and a in query_norm:
        return True
    # Longer query is the alias ("desserts" in "desserts please").
    if len(a) >= 4 and a in query_norm:
        return True
    return False


def is_bare_browse_term(query: str, target: BrowseTarget | None) -> bool:
    """True when the query is *only* the category/family term ("combo",
    "thali", "rice") and names no dish beyond it.

    "student combo" and "rice pudding" are NOT bare — they carry a word the
    alias doesn't cover, so they name a specific dish and must resolve to it
    rather than degrade into a category listing.
    """
    if target is None or not target.matched_alias:
        return False
    from restaurant.clover.match import content_tokens

    leftover = set(content_tokens(query)) - set(content_tokens(target.matched_alias))
    return not leftover


def resolve_browse_target(query: str) -> BrowseTarget | None:
    """Map a browse query to a category, dish family, or None."""
    q = normalize(query or "")
    if not q:
        return None

    best: BrowseTarget | None = None
    best_len = 0
    for key, category_name, aliases in _CATEGORY_SPECS:
        for alias in aliases:
            if _alias_in_query(alias, q):
                alen = len(normalize(alias))
                if alen >= best_len:
                    best_len = alen
                    best = BrowseTarget(
                        kind=BrowseKind.CATEGORY,
                        label=key,
                        category_name=category_name,
                        matched_alias=alias,
                    )

    for key, aliases, item_names, name_contains in _FAMILY_SPECS:
        for alias in aliases:
            if _alias_in_query(alias, q):
                alen = len(normalize(alias))
                if alen >= best_len:
                    best_len = alen
                    best = BrowseTarget(
                        kind=BrowseKind.FAMILY,
                        label=key,
                        item_names=tuple(item_names or ()),
                        name_contains=name_contains,
                        matched_alias=alias,
                    )

    return best
