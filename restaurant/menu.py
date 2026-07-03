RESTAURANT_NAME = "ਬਿਜ਼ਬਲ ਰੈਸਟੋਰੈਂਟ"
RESTAURANT_NAME_EN = "Bizbull Restaurant"
OPENING_HOURS = "ਸੋਮਵਾਰ ਤੋਂ ਐਤਵਾਰ, ਸਵੇਰੇ 11 ਵਜੇ ਤੋਂ ਰਾਤ 11 ਵਜੇ ਤੱਕ"
DELIVERY_CHARGE = 5
MIN_ORDER_DELIVERY = 20

MENU = {
    "starters": {
        "label": "ਸਟਾਰਟਰ",
        "items": [
            {"name": "Paneer Tikka",      "punjabi": "ਪਨੀਰ ਟਿੱਕਾ",          "price": 16, "veg": True},
            {"name": "Chicken Tikka",     "punjabi": "ਚਿਕਨ ਟਿੱਕਾ",          "price": 18, "veg": False},
            {"name": "Amritsari Fish",    "punjabi": "ਅੰਮ੍ਰਿਤਸਰੀ ਮੱਛੀ",     "price": 19, "veg": False},
            {"name": "Veg Platter",       "punjabi": "ਵੈਜ਼ ਪਲੇਟਰ",           "price": 20, "veg": True},
        ],
    },
    "mains": {
        "label": "ਮੇਨ ਕੋਰਸ",
        "items": [
            {"name": "Dal Makhani",       "punjabi": "ਦਾਲ ਮੱਖਣੀ",           "price": 15, "veg": True},
            {"name": "Sarson da Saag",    "punjabi": "ਸਰ੍ਹੋਂ ਦਾ ਸਾਗ",        "price": 16, "veg": True},
            {"name": "Palak Paneer",      "punjabi": "ਪਾਲਕ ਪਨੀਰ",           "price": 16, "veg": True},
            {"name": "Butter Chicken",    "punjabi": "ਬਟਰ ਚਿਕਨ",            "price": 19, "veg": False},
            {"name": "Mutton Rogan Josh", "punjabi": "ਮਟਨ ਰੋਗਨ ਜੋਸ਼",       "price": 25, "veg": False},
            {"name": "Chole Bhature",     "punjabi": "ਛੋਲੇ ਭਟੂਰੇ",           "price": 14, "veg": True},
            {"name": "Rajma Chawal",      "punjabi": "ਰਾਜਮਾ ਚਾਵਲ",          "price": 14, "veg": True},
        ],
    },
    "breads": {
        "label": "ਰੋਟੀਆਂ",
        "items": [
            {"name": "Butter Naan",       "punjabi": "ਬਟਰ ਨਾਨ",             "price": 4,  "veg": True},
            {"name": "Tandoori Roti",     "punjabi": "ਤੰਦੂਰੀ ਰੋਟੀ",         "price": 3,  "veg": True},
            {"name": "Makki di Roti",     "punjabi": "ਮੱਕੀ ਦੀ ਰੋਟੀ",        "price": 4,  "veg": True},
            {"name": "Aloo Paratha",      "punjabi": "ਆਲੂ ਪਰਾਠਾ",           "price": 6,  "veg": True},
        ],
    },
    "drinks": {
        "label": "ਪੀਣ ਵਾਲੀਆਂ ਚੀਜ਼ਾਂ",
        "items": [
            {"name": "Sweet Lassi",       "punjabi": "ਮਿੱਠੀ ਲੱਸੀ",          "price": 6,  "veg": True},
            {"name": "Salted Lassi",      "punjabi": "ਨਮਕੀਨ ਲੱਸੀ",          "price": 5,  "veg": True},
            {"name": "Mango Lassi",       "punjabi": "ਅੰਬ ਲੱਸੀ",            "price": 7,  "veg": True},
            {"name": "Masala Chai",       "punjabi": "ਮਸਾਲਾ ਚਾਹ",           "price": 4,  "veg": True},
        ],
    },
    "desserts": {
        "label": "ਮਿਠਾਈਆਂ",
        "items": [
            {"name": "Gulab Jamun",       "punjabi": "ਗੁਲਾਬ ਜਾਮੁਨ",         "price": 6,  "veg": True},
            {"name": "Kheer",             "punjabi": "ਖੀਰ",                  "price": 6,  "veg": True},
            {"name": "Rasmalai",          "punjabi": "ਰਸਮਲਾਈ",              "price": 7,  "veg": True},
            {"name": "Gajar Halwa",       "punjabi": "ਗਾਜਰ ਦਾ ਹਲਵਾ",        "price": 7,  "veg": True},
        ],
    },
}


def find_item(name: str) -> dict | None:
    """Static-menu fallback matcher (USE_CLOVER_MENU=0 only).

    Matches both directions: a short alias inside a longer canonical name
    ("naan" in "Butter Naan") and a canonical name embedded in a longer
    caller sentence ("Butter Naan" in "ਨਹੀਂ ਨਹੀਂ, ਬਟਰ ਨਾਨ ਕਰੋ"). Length
    guards avoid 2-3 char item names/labels matching unrelated substrings.
    """
    name_lower = name.lower().strip()
    for category, data in MENU.items():
        for item in data["items"]:
            item_name = item["name"].lower()
            item_punjabi = item["punjabi"]
            if (
                name_lower in item_name
                or name_lower in item_punjabi
                or (len(item_name) >= 4 and item_name in name_lower)
                or (len(item_punjabi) >= 4 and item_punjabi in name_lower)
            ):
                return {**item, "category": category}
    return None


def get_menu_text() -> str:
    lines = []
    for category, data in MENU.items():
        lines.append(f"[{data['label']}]")
        for item in data["items"]:
            tag = "(V)" if item["veg"] else "(NV)"
            lines.append(f"  {item['name']} / {item['punjabi']} — ${item['price']} {tag}")
        lines.append("")
    return "\n".join(lines)
