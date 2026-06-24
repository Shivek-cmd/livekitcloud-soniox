RESTAURANT_NAME = "ਪੰਜਾਬ ਦਾ ਢਾਬਾ"
RESTAURANT_NAME_EN = "Punjab Da Dhaba"
OPENING_HOURS = "ਸੋਮਵਾਰ ਤੋਂ ਐਤਵਾਰ, ਸਵੇਰੇ 11 ਵਜੇ ਤੋਂ ਰਾਤ 11 ਵਜੇ ਤੱਕ"
DELIVERY_CHARGE = 50
MIN_ORDER_DELIVERY = 200

MENU = {
    "starters": {
        "label": "ਸਟਾਰਟਰ",
        "items": [
            {"name": "Paneer Tikka",      "punjabi": "ਪਨੀਰ ਟਿੱਕਾ",          "price": 280, "veg": True},
            {"name": "Chicken Tikka",     "punjabi": "ਚਿਕਨ ਟਿੱਕਾ",          "price": 320, "veg": False},
            {"name": "Amritsari Fish",    "punjabi": "ਅੰਮ੍ਰਿਤਸਰੀ ਮੱਛੀ",     "price": 340, "veg": False},
            {"name": "Veg Platter",       "punjabi": "ਵੈਜ਼ ਪਲੇਟਰ",           "price": 350, "veg": True},
        ],
    },
    "mains": {
        "label": "ਮੇਨ ਕੋਰਸ",
        "items": [
            {"name": "Dal Makhani",       "punjabi": "ਦਾਲ ਮੱਖਣੀ",           "price": 220, "veg": True},
            {"name": "Sarson da Saag",    "punjabi": "ਸਰ੍ਹੋਂ ਦਾ ਸਾਗ",        "price": 240, "veg": True},
            {"name": "Palak Paneer",      "punjabi": "ਪਾਲਕ ਪਨੀਰ",           "price": 260, "veg": True},
            {"name": "Butter Chicken",    "punjabi": "ਬਟਰ ਚਿਕਨ",            "price": 320, "veg": False},
            {"name": "Mutton Rogan Josh", "punjabi": "ਮਟਨ ਰੋਗਨ ਜੋਸ਼",       "price": 420, "veg": False},
            {"name": "Chole Bhature",     "punjabi": "ਛੋਲੇ ਭਟੂਰੇ",           "price": 160, "veg": True},
            {"name": "Rajma Chawal",      "punjabi": "ਰਾਜਮਾ ਚਾਵਲ",          "price": 180, "veg": True},
        ],
    },
    "breads": {
        "label": "ਰੋਟੀਆਂ",
        "items": [
            {"name": "Butter Naan",       "punjabi": "ਬਟਰ ਨਾਨ",             "price": 50,  "veg": True},
            {"name": "Tandoori Roti",     "punjabi": "ਤੰਦੂਰੀ ਰੋਟੀ",         "price": 30,  "veg": True},
            {"name": "Makki di Roti",     "punjabi": "ਮੱਕੀ ਦੀ ਰੋਟੀ",        "price": 40,  "veg": True},
            {"name": "Aloo Paratha",      "punjabi": "ਆਲੂ ਪਰਾਠਾ",           "price": 80,  "veg": True},
        ],
    },
    "drinks": {
        "label": "ਪੀਣ ਵਾਲੀਆਂ ਚੀਜ਼ਾਂ",
        "items": [
            {"name": "Sweet Lassi",       "punjabi": "ਮਿੱਠੀ ਲੱਸੀ",          "price": 80,  "veg": True},
            {"name": "Salted Lassi",      "punjabi": "ਨਮਕੀਨ ਲੱਸੀ",          "price": 70,  "veg": True},
            {"name": "Mango Lassi",       "punjabi": "ਅੰਬ ਲੱਸੀ",            "price": 100, "veg": True},
            {"name": "Masala Chai",       "punjabi": "ਮਸਾਲਾ ਚਾਹ",           "price": 40,  "veg": True},
        ],
    },
    "desserts": {
        "label": "ਮਿਠਾਈਆਂ",
        "items": [
            {"name": "Gulab Jamun",       "punjabi": "ਗੁਲਾਬ ਜਾਮੁਨ",         "price": 80,  "veg": True},
            {"name": "Kheer",             "punjabi": "ਖੀਰ",                  "price": 90,  "veg": True},
            {"name": "Gajar Halwa",       "punjabi": "ਗਾਜਰ ਦਾ ਹਲਵਾ",        "price": 110, "veg": True},
        ],
    },
}


def find_item(name: str) -> dict | None:
    name_lower = name.lower().strip()
    for category, data in MENU.items():
        for item in data["items"]:
            if name_lower in item["name"].lower() or name_lower in item["punjabi"]:
                return {**item, "category": category}
    return None


def get_menu_text() -> str:
    lines = []
    for category, data in MENU.items():
        lines.append(f"[{data['label']}]")
        for item in data["items"]:
            tag = "(V)" if item["veg"] else "(NV)"
            lines.append(f"  {item['name']} / {item['punjabi']} — ₹{item['price']} {tag}")
        lines.append("")
    return "\n".join(lines)
