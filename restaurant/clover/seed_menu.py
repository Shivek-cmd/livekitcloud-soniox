"""
Bizbull Restaurant — production-style Indian-Canadian Clover seed catalog.

Prices are CAD dollars (converted to cents at seed time). Voice labels (speak_as,
aliases) are written to data/clover_voice_labels.json by clover_sandbox_seed.py — not
stored in Clover.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModifierOption:
    key: str
    name: str
    price: float = 0.0
    speak_as: str | None = None
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class ModifierGroupSpec:
    key: str
    name: str
    min_required: int = 0
    max_allowed: int = 1
    modifiers: tuple[ModifierOption, ...] = ()


@dataclass(frozen=True)
class MenuItemSpec:
    key: str
    name: str
    price: float
    category_key: str
    speak_as: str
    aliases: tuple[str, ...]
    veg: bool
    modifier_group_keys: tuple[str, ...] = ()
    description: str = ""


@dataclass(frozen=True)
class CategorySpec:
    key: str
    name: str
    sort_order: int


RESTAURANT_LABEL = "Bizbull Restaurant"

CATEGORIES: tuple[CategorySpec, ...] = (
    CategorySpec("starters", "Starters & Snacks", 1),
    CategorySpec("tandoor", "Tandoor & Grill", 2),
    CategorySpec("veg_mains", "Vegetarian Mains", 3),
    CategorySpec("nonveg_mains", "Non-Veg Mains", 4),
    CategorySpec("breads_rice", "Breads & Rice", 5),
    CategorySpec("combos", "Combos & Platters", 6),
    CategorySpec("drinks", "Drinks", 7),
    CategorySpec("desserts", "Desserts", 8),
    CategorySpec("extras", "Extras & Sides", 9),
)

MODIFIER_GROUPS: tuple[ModifierGroupSpec, ...] = (
    ModifierGroupSpec(
        "spice_level",
        "Spice Level",
        min_required=0,
        max_allowed=1,
        modifiers=(
            ModifierOption("mild", "Mild", aliases=("mild", "kam spicy")),
            ModifierOption("medium", "Medium", aliases=("medium", "medium spicy")),
            ModifierOption("spicy", "Spicy", aliases=("spicy", "teekha")),
            ModifierOption("extra_spicy", "Extra Spicy", aliases=("extra spicy", "bahut teekha")),
        ),
    ),
    ModifierGroupSpec(
        "bread_choice",
        "Bread Choice",
        min_required=0,
        max_allowed=1,
        modifiers=(
            ModifierOption("plain_naan", "Plain Naan", aliases=("plain naan",)),
            ModifierOption("butter_naan", "Butter Naan", 0.50, aliases=("butter naan",)),
            ModifierOption("garlic_naan", "Garlic Naan", 1.00, aliases=("garlic naan",)),
            ModifierOption("tandoori_roti", "Tandoori Roti", aliases=("roti", "tandoori roti")),
        ),
    ),
    ModifierGroupSpec(
        "rice_side",
        "Rice Side",
        min_required=0,
        max_allowed=1,
        modifiers=(
            ModifierOption("plain_rice", "Plain Rice", aliases=("plain rice", "chawal")),
            ModifierOption("jeera_rice", "Jeera Rice", 1.50, aliases=("jeera rice",)),
            ModifierOption("saffron_rice", "Saffron Rice", 2.00, aliases=("saffron rice",)),
        ),
    ),
    ModifierGroupSpec(
        "lassi_size",
        "Lassi Size",
        min_required=1,
        max_allowed=1,
        modifiers=(
            ModifierOption("regular", "Regular", aliases=("regular", "small")),
            ModifierOption("large", "Large", 1.00, aliases=("large", "bada")),
        ),
    ),
    ModifierGroupSpec(
        "combo_drink",
        "Combo Drink",
        min_required=1,
        max_allowed=1,
        modifiers=(
            ModifierOption("sweet_lassi", "Sweet Lassi", aliases=("sweet lassi", "lassi")),
            ModifierOption("salted_lassi", "Salted Lassi", aliases=("salted lassi", "namkeen lassi")),
            ModifierOption("mango_lassi", "Mango Lassi", 1.00, aliases=("mango lassi",)),
            ModifierOption("masala_chai", "Masala Chai", 0.50, aliases=("chai", "masala chai")),
            ModifierOption("soft_drink", "Soft Drink", aliases=("pop", "coke", "pepsi")),
        ),
    ),
    ModifierGroupSpec(
        "add_extras",
        "Add Extras",
        min_required=0,
        max_allowed=4,
        modifiers=(
            ModifierOption("extra_raita", "Extra Raita", 2.00, speak_as="ਐਕਸਟਰਾ ਰਾਇਤਾ", aliases=("extra raita",)),
            ModifierOption("extra_pickle", "Extra Pickle", 1.00, aliases=("extra pickle", "achar")),
            ModifierOption("extra_papad", "Extra Papad", 1.50, aliases=("extra papad", "papad")),
            ModifierOption("green_chutney", "Green Chutney", 1.00, aliases=("green chutney", "hari chutney")),
            ModifierOption("extra_gravy", "Extra Gravy", 2.50, aliases=("extra gravy", "extra sauce")),
        ),
    ),
    ModifierGroupSpec(
        "protein_size",
        "Protein Size",
        min_required=0,
        max_allowed=1,
        modifiers=(
            ModifierOption("regular", "Regular Portion", aliases=("regular",)),
            ModifierOption("large", "Large Portion", 4.00, aliases=("large portion", "extra meat")),
        ),
    ),
    ModifierGroupSpec(
        "bhatura_count",
        "Bhatura Count",
        min_required=0,
        max_allowed=1,
        modifiers=(
            ModifierOption("two", "2 Bhature (standard)", aliases=("2 bhature", "two bhature")),
            ModifierOption("three", "3 Bhature", 2.00, aliases=("3 bhature", "extra bhatura")),
        ),
    ),
    ModifierGroupSpec(
        "combo_curry_pick",
        "Choose Curry",
        min_required=1,
        max_allowed=1,
        modifiers=(
            ModifierOption("dal_makhani", "Dal Makhani", aliases=("dal makhani",)),
            ModifierOption("palak_paneer", "Palak Paneer", aliases=("palak paneer",)),
            ModifierOption("chole", "Chole", aliases=("chole",)),
            ModifierOption("paneer_butter", "Paneer Butter Masala", 1.00, aliases=("paneer butter",)),
        ),
    ),
    ModifierGroupSpec(
        "combo_nonveg_curry",
        "Choose Non-Veg Curry",
        min_required=1,
        max_allowed=1,
        modifiers=(
            ModifierOption("butter_chicken", "Butter Chicken", aliases=("butter chicken",)),
            ModifierOption("chicken_tikka_masala", "Chicken Tikka Masala", aliases=("tikka masala",)),
            ModifierOption("lamb_rogan", "Lamb Rogan Josh", 2.00, aliases=("rogan josh", "lamb")),
            ModifierOption("goat_curry", "Goat Curry", 2.50, aliases=("goat curry", "mutton")),
        ),
    ),
)

MENU_ITEMS: tuple[MenuItemSpec, ...] = (
    # --- Starters ---
    MenuItemSpec(
        "samosa_chaat", "Samosa Chaat (2 pcs)", 8.99, "starters",
        "ਸਮੋਸਾ ਚਾਟ", ("samosa chaat", "samosa"), True,
        ("spice_level", "add_extras"),
        "Crushed samosas with chutneys, yogurt, and sev.",
    ),
    MenuItemSpec(
        "paneer_tikka", "Paneer Tikka", 16.99, "starters",
        "ਪਨੀਰ ਟਿੱਕਾ", ("paneer tikka", "tikka paneer"), True,
        ("spice_level", "add_extras"),
    ),
    MenuItemSpec(
        "chicken_tikka", "Chicken Tikka", 18.99, "starters",
        "ਚਿਕਨ ਟਿੱਕਾ", ("chicken tikka",), False,
        ("spice_level", "add_extras"),
    ),
    MenuItemSpec(
        "fish_pakora", "Amritsari Fish Pakora", 14.99, "starters",
        "ਅੰਮ੍ਰਿਤਸਰੀ ਮੱਛੀ ਪਕੋੜਾ", ("fish pakora", "amritsari fish"), False,
        ("spice_level",),
    ),
    MenuItemSpec(
        "veg_spring_rolls", "Veg Spring Rolls (6 pcs)", 9.99, "starters",
        "ਵੈਜ ਸਪ੍ਰਿੰਗ ਰੋਲ", ("spring rolls", "veg rolls"), True,
        ("spice_level",),
    ),
    MenuItemSpec(
        "pakora_platter", "Mixed Pakora Platter", 12.99, "starters",
        "ਮਿਕਸ ਪਕੋੜਾ ਪਲੇਟਰ", ("pakora platter", "pakora", "mix pakora platter", "mixed pakora"), True,
        ("spice_level", "add_extras"),
    ),
    MenuItemSpec(
        "honey_chilli_cauliflower", "Honey Chilli Gobi", 13.99, "starters",
        "ਹਨੀ ਚਿਲੀ ਗੋਭੀ", ("honey chilli gobi", "gobi manchurian"), True,
        ("spice_level",),
    ),
    # --- Tandoor ---
    MenuItemSpec(
        "tandoori_chicken_half", "Tandoori Chicken (Half)", 19.99, "tandoor",
        "ਤੰਦੂਰੀ ਚਿਕਨ (ਅੱਧਾ)", ("tandoori chicken half", "half chicken"), False,
        ("spice_level", "add_extras"),
    ),
    MenuItemSpec(
        "tandoori_chicken_full", "Tandoori Chicken (Full)", 32.99, "tandoor",
        "ਤੰਦੂਰੀ ਚਿਕਨ (ਪੂਰਾ)", ("tandoori chicken full", "full chicken"), False,
        ("spice_level", "add_extras"),
    ),
    MenuItemSpec(
        "seekh_kebab", "Seekh Kebab (4 pcs)", 17.99, "tandoor",
        "ਸੀਖ ਕਬਾਬ", ("seekh kebab", "sheek kebab"), False,
        ("spice_level",),
    ),
    MenuItemSpec(
        "lamb_chops", "Tandoori Lamb Chops", 28.99, "tandoor",
        "ਤੰਦੂਰੀ ਲੈਮ ਚਾਪ", ("lamb chops", "chops"), False,
        ("spice_level",),
    ),
    MenuItemSpec(
        "tandoori_shrimp", "Tandoori Shrimp", 21.99, "tandoor",
        "ਤੰਦੂਰੀ ਝੀਂਗਾ", ("tandoori shrimp", "jhinga"), False,
        ("spice_level",),
    ),
    # --- Veg mains ---
    MenuItemSpec(
        "dal_makhani", "Dal Makhani", 15.99, "veg_mains",
        "ਦਾਲ ਮੱਖਣੀ", ("dal makhani", "black dal"), True,
        ("spice_level", "bread_choice", "rice_side", "add_extras"),
    ),
    MenuItemSpec(
        "sarson_saag", "Sarson da Saag", 16.99, "veg_mains",
        "ਸਰ੍ਹੋਂ ਦਾ ਸਾਗ", ("sarson saag", "saag"), True,
        ("spice_level", "bread_choice", "add_extras"),
    ),
    MenuItemSpec(
        "palak_paneer", "Palak Paneer", 16.99, "veg_mains",
        "ਪਾਲਕ ਪਨੀਰ", ("palak paneer", "saag paneer"), True,
        ("spice_level", "bread_choice", "rice_side", "add_extras"),
    ),
    MenuItemSpec(
        "chole", "Chole (Chickpea Curry)", 13.99, "veg_mains",
        "ਛੋਲੇ", ("chole", "chana masala"), True,
        ("spice_level", "bread_choice", "add_extras"),
    ),
    MenuItemSpec(
        "paneer_butter_masala", "Paneer Butter Masala", 17.99, "veg_mains",
        "ਪਨੀਰ ਬਟਰ ਮਸਾਲਾ", ("paneer butter", "paneer butter masala"), True,
        ("spice_level", "bread_choice", "rice_side"),
    ),
    MenuItemSpec(
        "malai_kofta", "Malai Kofta", 16.99, "veg_mains",
        "ਮਲਾਈ ਕੋਫ਼ਤਾ", ("malai kofta",), True,
        ("spice_level", "bread_choice", "rice_side"),
    ),
    MenuItemSpec(
        "dal_tadka", "Dal Tadka", 13.99, "veg_mains",
        "ਦਾਲ ਤੜਕਾ", ("dal tadka", "yellow dal"), True,
        ("spice_level", "bread_choice", "rice_side"),
    ),
    MenuItemSpec(
        "mushroom_matar", "Mushroom Matar", 15.99, "veg_mains",
        "ਮਸ਼ਰੂਮ ਮਟਰ", ("mushroom matar",), True,
        ("spice_level", "bread_choice", "rice_side"),
    ),
    MenuItemSpec(
        "baigan_bharta", "Baigan Bharta", 15.49, "veg_mains",
        "ਬੈਂਗਣ ਭਰਤਾ", ("baigan bharta", "eggplant bharta"), True,
        ("spice_level", "bread_choice"),
    ),
    # --- Non-veg mains ---
    MenuItemSpec(
        "butter_chicken", "Butter Chicken", 19.99, "nonveg_mains",
        "ਬਟਰ ਚਿਕਨ", ("butter chicken", "murgh makhani"), False,
        ("spice_level", "bread_choice", "rice_side", "protein_size", "add_extras"),
    ),
    MenuItemSpec(
        "chicken_tikka_masala", "Chicken Tikka Masala", 19.99, "nonveg_mains",
        "ਚਿਕਨ ਟਿੱਕਾ ਮਸਾਲਾ", ("chicken tikka masala", "tikka masala"), False,
        ("spice_level", "bread_choice", "rice_side", "protein_size"),
    ),
    MenuItemSpec(
        "lamb_rogan_josh", "Lamb Rogan Josh", 24.99, "nonveg_mains",
        "ਲੈਮ ਰੋਗਨ ਜੋਸ਼", ("lamb rogan josh", "rogan josh"), False,
        ("spice_level", "bread_choice", "rice_side", "protein_size"),
    ),
    MenuItemSpec(
        "goat_curry", "Goat Curry", 25.99, "nonveg_mains",
        "ਬਕਰੇ ਦਾ ਮਸਾਲਾ", ("goat curry", "mutton curry", "bakra", "bakre da masala"), False,
        ("spice_level", "bread_choice", "rice_side", "protein_size"),
    ),
    MenuItemSpec(
        "fish_curry", "Punjabi Fish Curry", 21.99, "nonveg_mains",
        "ਪੰਜਾਬੀ ਮੱਛੀ ਕਰੀ", ("fish curry", "machhi curry", "machhi"), False,
        ("spice_level", "rice_side"),
    ),
    MenuItemSpec(
        "chicken_biryani", "Chicken Biryani", 18.99, "nonveg_mains",
        "ਚਿਕਨ ਬਿਰਿਆਨੀ", ("chicken biryani", "biryani"), False,
        ("spice_level", "add_extras", "protein_size"),
    ),
    MenuItemSpec(
        "lamb_biryani", "Lamb Biryani", 22.99, "nonveg_mains",
        "ਲੈਮ ਬਿਰਿਆਨੀ", ("lamb biryani",), False,
        ("spice_level", "add_extras"),
    ),
    MenuItemSpec(
        "butter_prawn_masala", "Butter Prawn Masala", 23.99, "nonveg_mains",
        "ਬਟਰ ਪ੍ਰੌਨ ਮਸਾਲਾ", ("butter prawn", "prawn masala"), False,
        ("spice_level", "rice_side"),
    ),
    # --- Breads & rice ---
    MenuItemSpec("butter_naan", "Butter Naan", 3.99, "breads_rice", "ਬਟਰ ਨਾਨ", ("butter naan", "naan"), True),
    MenuItemSpec("garlic_naan", "Garlic Naan", 4.99, "breads_rice", "ਗਾਰਲਿਕ ਨਾਨ", ("garlic naan",), True),
    MenuItemSpec("tandoori_roti", "Tandoori Roti", 2.99, "breads_rice", "ਤੰਦੂਰੀ ਰੋਟੀ", ("tandoori roti", "roti"), True),
    MenuItemSpec("aloo_paratha", "Aloo Paratha", 5.99, "breads_rice", "ਆਲੂ ਪਰਾਠਾ", ("aloo paratha", "paratha"), True, ("spice_level",)),
    MenuItemSpec("bhatura_single", "Bhatura (single)", 3.99, "breads_rice", "ਭਟੂਰਾ", ("bhatura", "bhature"), True),
    MenuItemSpec("plain_rice", "Plain Rice", 4.99, "breads_rice", "ਸਾਦਾ ਚਾਵਲ", ("plain rice", "rice", "sada chawal"), True),
    MenuItemSpec("jeera_rice", "Jeera Rice", 5.99, "breads_rice", "ਜੀਰਾ ਚਾਵਲ", ("jeera rice",), True),
    MenuItemSpec("saffron_rice", "Saffron Rice", 6.99, "breads_rice", "ਕੇਸਰ ਚਾਵਲ", ("saffron rice", "kesar chawal"), True),
    # --- Combos & platters ---
    MenuItemSpec(
        "chole_bhature_combo", "Chole Bhature Combo", 15.99, "combos",
        "ਛੋਲੇ ਭਟੂਰੇ ਕੌਂਬੋ", ("chole bhature combo", "chole bhature", "bhatura combo"), True,
        ("spice_level", "bhatura_count", "add_extras"),
        "Chole + bhature + pickle. Classic Punjabi combo.",
    ),
    MenuItemSpec(
        "lunch_thali_combo", "Veg Lunch Thali Combo", 18.99, "combos",
        "ਵੈਜ ਲੰਚ ਥਾਲੀ", ("lunch thali", "veg thali", "thali combo"), True,
        ("combo_curry_pick", "spice_level", "combo_drink", "add_extras"),
        "1 veg curry + dal tadka + rice + 2 roti + raita + drink.",
    ),
    MenuItemSpec(
        "nonveg_lunch_combo", "Non-Veg Lunch Combo", 21.99, "combos",
        "ਨਾਨ-ਵੈਜ ਲੰਚ ਕੌਂਬੋ", ("non veg lunch", "lunch combo"), False,
        ("combo_nonveg_curry", "spice_level", "combo_drink"),
        "1 non-veg curry + jeera rice + butter naan + drink.",
    ),
    MenuItemSpec(
        "student_combo", "Student Combo", 13.99, "combos",
        "ਸਟੂਡੈਂਟ ਕੌਂਬੋ", ("student combo", "cheap combo"), True,
        ("combo_curry_pick", "spice_level", "combo_drink"),
        "1 curry + 2 roti + drink. Weekday special.",
    ),
    MenuItemSpec(
        "couple_combo", "Couple Combo (for 2)", 39.99, "combos",
        "ਕਪਲ ਕੌਂਬੋ", ("couple combo", "combo for two"), False,
        ("combo_nonveg_curry", "spice_level", "combo_drink", "add_extras"),
        "2 mains + 2 naan + 2 drinks + dessert sampler.",
    ),
    MenuItemSpec(
        "family_veg_platter", "Family Veg Platter (serves 4)", 54.99, "combos",
        "ਫੈਮਿਲੀ ਵੈਜ ਪਲੇਟਰ", ("family veg platter", "veg platter"), True,
        ("spice_level", "add_extras"),
        "2 starters + 2 veg mains + rice + 4 naan + raita + papad.",
    ),
    MenuItemSpec(
        "nonveg_deluxe_platter", "Non-Veg Deluxe Platter (serves 4)", 64.99, "combos",
        "ਨਾਨ-ਵੈਜ ਡੀਲਕਸ ਪਲੇਟਰ", ("non veg platter", "deluxe platter"), False,
        ("spice_level", "add_extras"),
        "2 starters + butter chicken + lamb curry + biryani + 4 naan + gulab jamun.",
    ),
    MenuItemSpec(
        "office_party_tray", "Office Party Tray (serves 8)", 119.99, "combos",
        "ਆਫਿਸ ਪਾਰਟੀ ਟਰੇ", ("party tray", "office tray", "catering tray"), False,
        ("spice_level",),
        "Mixed starters + 3 mains + rice + naan basket + raita + dessert.",
    ),
    # --- Drinks ---
    MenuItemSpec("sweet_lassi", "Sweet Lassi", 5.99, "drinks", "ਮਿੱਠੀ ਲੱਸੀ", ("sweet lassi", "lassi", "mitthi lassi"), True, ("lassi_size",)),
    MenuItemSpec("salted_lassi", "Salted Lassi", 5.49, "drinks", "ਨਮਕੀਨ ਲੱਸੀ", ("salted lassi", "namkeen lassi"), True, ("lassi_size",)),
    MenuItemSpec("mango_lassi", "Mango Lassi", 6.99, "drinks", "ਅੰਬ ਲੱਸੀ", ("mango lassi",), True, ("lassi_size",)),
    MenuItemSpec("masala_chai", "Masala Chai", 3.99, "drinks", "ਮਸਾਲਾ ਚਾਹ", ("masala chai", "chai"), True),
    MenuItemSpec("mango_shake", "Mango Shake", 6.49, "drinks", "ਅੰਬ ਸ਼ੇਕ", ("mango shake",), True),
    MenuItemSpec("soft_drink", "Soft Drink (can)", 2.49, "drinks", "ਸਾਫਟ ਡਰਿੰਕ", ("soft drink", "pop", "coke"), True),
    MenuItemSpec("nimbu_pani", "Nimbu Pani", 4.49, "drinks", "ਨਿੰਬੂ ਪਾਣੀ", ("nimbu pani", "lemonade", "shikanji", "shikanjvi"), True),
    # --- Desserts ---
    MenuItemSpec("gulab_jamun", "Gulab Jamun (2 pcs)", 5.99, "desserts", "ਗੁਲਾਬ ਜਾਮੁਨ", ("gulab jamun",), True),
    MenuItemSpec("kheer", "Kheer", 5.99, "desserts", "ਖੀਰ", ("kheer", "rice pudding"), True),
    MenuItemSpec("gajar_halwa", "Gajar Halwa", 7.99, "desserts", "ਗਾਜਰ ਦਾ ਹਲਵਾ", ("gajar halwa", "carrot halwa"), True),
    MenuItemSpec("rasmalai", "Rasmalai (2 pcs)", 6.99, "desserts", "ਰਸਮਲਾਈ", ("rasmalai",), True),
    MenuItemSpec("kulfi", "Mango Kulfi", 5.49, "desserts", "ਅੰਬ ਕੁਲਫੀ", ("kulfi", "mango kulfi"), True),
    # --- Extras ---
    MenuItemSpec("raita", "Raita", 3.99, "extras", "ਰਾਇਤਾ", ("raita",), True),
    MenuItemSpec("mixed_pickle", "Mixed Pickle", 2.99, "extras", "ਮਿਕਸ ਅਚਾਰ", ("pickle", "achar", "mixed pickle"), True),
    MenuItemSpec("papad", "Papad (2 pcs)", 2.49, "extras", "ਪਪੜ", ("papad", "papadum"), True),
    MenuItemSpec("extra_gravy_side", "Extra Gravy (side)", 2.99, "extras", "ਐਕਸਟਰਾ ਗ੍ਰੇਵੀ", ("extra gravy",), True),
)


def dollars_to_cents(amount: float) -> int:
    return int(round(amount * 100))


def category_by_key() -> dict[str, CategorySpec]:
    return {c.key: c for c in CATEGORIES}


def modifier_group_by_key() -> dict[str, ModifierGroupSpec]:
    return {g.key: g for g in MODIFIER_GROUPS}


def menu_item_by_key() -> dict[str, MenuItemSpec]:
    return {i.key: i for i in MENU_ITEMS}
