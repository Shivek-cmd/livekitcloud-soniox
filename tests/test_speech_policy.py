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
    assert _speech("chole_bhature_combo") == ("ਛੋਲੇ ਭਟੂਰੇ ਕੰਬੋ", "gurmukhi")
