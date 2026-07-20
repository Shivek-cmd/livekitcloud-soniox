"""Speech policy voice_line for mango drinks and chole/bhature."""

from restaurant.clover.seed_menu import menu_item_by_key
from restaurant.clover.speech_policy import resolve_item_speech


def _speech(key: str) -> tuple[str, str]:
    spec = menu_item_by_key()[key]
    line, mode = resolve_item_speech(spec)
    return line, mode


def test_mango_drinks_english():
    assert _speech("mango_shake") == ("Mango Shake", "english")
    assert _speech("mango_lassi") == ("Mango Lassi", "english")


def test_chole_bhature_gurmukhi():
    assert _speech("chole") == ("ਛੋਲੇ", "gurmukhi")
    assert _speech("bhatura_single") == ("ਭਟੂਰਾ", "gurmukhi")
    assert _speech("chole_bhature_combo") == ("ਛੋਲੇ ਭਟੂਰੇ ਕੌਂਬੋ", "gurmukhi")


def test_english_proper_name_nonveg_mains_english():
    # PR 085 (Gap 5): English proper-name Non-Veg Mains must speak Roman —
    # their Gurmukhi speak_as only transliterates the English word ("ਲੈਮ").
    assert _speech("lamb_biryani") == ("Lamb Biryani", "english")
    assert _speech("chicken_biryani") == ("Chicken Biryani", "english")
    assert _speech("lamb_rogan_josh") == ("Lamb Rogan Josh", "english")
    assert _speech("chicken_tikka_masala") == ("Chicken Tikka Masala", "english")
