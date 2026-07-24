"""Tests for restaurant.agent.readback_verify — the post-speech readback
verifier (PR 078). False negatives fail safe toward a re-read."""

from restaurant.agent.readback_verify import (
    normalize_tokens,
    readback_verify_mode,
    verify_readback,
)
from restaurant.orders import OrderCart

_BC = {"name": "Butter Chicken", "voice_line": "ਬਟਰ ਚਿਕਨ", "price": 13.99}
_NAAN = {"name": "Garlic Naan", "voice_line": "ਗਾਰਲਿਕ ਨਾਨ", "price": 3.50}
_PAKORA = {
    "name": "Amritsari Fish Pakora (2 pcs)",
    "voice_line": "ਅੰਮ੍ਰਿਤਸਰੀ ਫਿਸ਼ ਪਕੌੜਾ (2 pcs)",
    "price": 11.99,
}


def _cart(order_type: str = "pickup") -> OrderCart:
    cart = OrderCart()
    cart.add_item(_BC, 2)
    cart.add_item(_NAAN, 1)
    cart.order_type = order_type
    return cart


# ── passing phrasings, three languages ───────────────────────────────────────


def test_english_readback_passes():
    spoken = (
        "So that's two Butter Chicken with medium spice and a Garlic Naan "
        "for pickup — is everything correct?"
    )
    assert verify_readback(spoken, _cart()).ok


def test_punjabi_readback_passes():
    spoken = (
        "ਠੀਕ ਹੈ ਜੀ — ਦੋ ਬਟਰ ਚਿਕਨ ਅਤੇ ਇੱਕ ਗਾਰਲਿਕ ਨਾਨ, pickup ਲਈ। "
        "ਸਭ ਕੁਝ ਠੀਕ ਹੈ?"
    )
    assert verify_readback(spoken, _cart()).ok


def test_hindi_qty_with_voice_line_passes():
    spoken = "जी — दो ਬਟਰ ਚਿਕਨ और एक ਗਾਰਲਿਕ ਨਾਨ, pickup। सब ठीक है?"
    assert verify_readback(spoken, _cart()).ok


def test_gurmukhi_dish_with_english_qty_passes():
    spoken = "Two ਬਟਰ ਚਿਕਨ and one ਗਾਰਲਿਕ ਨਾਨ for pickup, all good?"
    assert verify_readback(spoken, _cart()).ok


def test_english_name_alias_passes():
    # Spoken with the English menu name instead of the voice_line.
    spoken = "Two Butter Chicken and one Garlic Naan, pickup. Correct?"
    assert verify_readback(spoken, _cart()).ok


# ── failures ─────────────────────────────────────────────────────────────────


def test_missing_item_fails():
    spoken = "Two Butter Chicken for pickup — everything correct?"
    check = verify_readback(spoken, _cart())
    assert not check.ok
    assert any("Garlic Naan" in p or "ਗਾਰਲਿਕ ਨਾਨ" in p for p in check.problems)


def test_wrong_quantity_fails():
    spoken = "Three Butter Chicken and one Garlic Naan, pickup — okay?"
    check = verify_readback(spoken, _cart())
    assert not check.ok
    assert any("quantity" in p for p in check.problems)


def test_qty_two_omitted_fails():
    spoken = "Butter Chicken and a Garlic Naan for pickup, all good?"
    check = verify_readback(spoken, _cart())
    assert not check.ok


def test_qty_one_omitted_passes():
    # "and a Garlic Naan" — no number needed for quantity 1.
    spoken = "Two Butter Chicken and a Garlic Naan, pickup. Correct?"
    assert verify_readback(spoken, _cart()).ok


def test_missing_order_type_fails():
    spoken = "Two Butter Chicken and one Garlic Naan — everything correct?"
    check = verify_readback(spoken, _cart())
    assert not check.ok
    assert any("order type" in p for p in check.problems)


def test_order_type_transliteration_accepted():
    # Exact phonetic renditions of "pickup" count — the customer heard it;
    # anything outside the closed vocab still fails.
    spoken = "दो ਬਟਰ ਚਿਕਨ और एक ਗਾਰਲਿਕ ਨਾਨ, पिकअप। ठीक है?"
    assert verify_readback(spoken, _cart()).ok
    spoken_pa = "ਦੋ ਬਟਰ ਚਿਕਨ ਅਤੇ ਇੱਕ ਗਾਰਲਿਕ ਨਾਨ, ਪਿਕਅਪ ਲਈ। ਠੀਕ ਹੈ?"
    assert verify_readback(spoken_pa, _cart()).ok
    translated = "ਦੋ ਬਟਰ ਚਿਕਨ ਅਤੇ ਇੱਕ ਗਾਰਲਿਕ ਨਾਨ ਲੈ ਜਾਣ ਲਈ। ਠੀਕ ਹੈ?"
    check = verify_readback(translated, _cart())
    assert any("order type" in p for p in check.problems)


def test_empty_buffer_fails():
    check = verify_readback("", _cart())
    assert not check.ok
    assert len(check.problems) >= 3  # both items + order type


def test_truncated_readback_fails():
    # Barge-in truncation mid-list.
    spoken = "So that's two Butter"
    assert not verify_readback(spoken, _cart()).ok


# ── vocab / normalization details ────────────────────────────────────────────


def test_pick_up_two_words_passes():
    spoken = "Two Butter Chicken and one Garlic Naan to pick up — correct?"
    assert verify_readback(spoken, _cart()).ok


def test_delivery_vocab():
    spoken = "Two Butter Chicken and one Garlic Naan, delivered to you. Okay?"
    assert verify_readback(spoken, _cart("delivery")).ok


def test_parenthetical_stripped_from_alias():
    cart = OrderCart()
    cart.add_item(_PAKORA, 1)
    cart.order_type = "pickup"
    spoken = "One ਅੰਮ੍ਰਿਤਸਰੀ ਫਿਸ਼ ਪਕੌੜਾ for pickup — is that right?"
    assert verify_readback(spoken, cart).ok


def test_indic_numeral_quantity_passes():
    spoken = "੨ ਬਟਰ ਚਿਕਨ ਅਤੇ ਇੱਕ ਗਾਰਲਿਕ ਨਾਨ, pickup ਜੀ। ਠੀਕ?"
    assert verify_readback(spoken, _cart()).ok


def test_punctuation_and_case_ignored():
    spoken = 'TWO "Butter Chicken", one Garlic-Naan... PICKUP! Correct?'
    assert verify_readback(spoken, _cart()).ok


def test_normalize_tokens_preserves_indic():
    assert normalize_tokens("ਦੋ ਬਟਰ ਚਿਕਨ, two!") == ["ਦੋ", "ਬਟਰ", "ਚਿਕਨ", "two"]


# ── total (web, warn-level) ──────────────────────────────────────────────────


def test_total_mismatch_warns_but_does_not_block():
    cart = _cart()
    spoken = (
        f"Two Butter Chicken and one Garlic Naan, pickup, total 99 dollars."
    )
    check = verify_readback(spoken, cart, check_total=True)
    assert check.ok  # warnings never block
    assert check.warnings


def test_total_correct_no_warning():
    cart = _cart()
    spoken = (
        f"Two Butter Chicken and one Garlic Naan, pickup, "
        f"total ${cart.total:.2f}."
    )
    check = verify_readback(spoken, cart, check_total=True)
    assert check.ok and not check.warnings


def test_no_total_spoken_no_warning():
    spoken = "Two Butter Chicken and one Garlic Naan, pickup."
    check = verify_readback(spoken, _cart(), check_total=True)
    assert not check.warnings


# ── mode env ─────────────────────────────────────────────────────────────────


def test_mode_env(monkeypatch):
    # PR 080: strict is the default; warn/off are explicit opt-outs.
    monkeypatch.delenv("READBACK_VERIFY", raising=False)
    assert readback_verify_mode() == "strict"
    monkeypatch.setenv("READBACK_VERIFY", "warn")
    assert readback_verify_mode() == "warn"
    monkeypatch.setenv("READBACK_VERIFY", "OFF")
    assert readback_verify_mode() == "off"
    monkeypatch.setenv("READBACK_VERIFY", "bogus")
    assert readback_verify_mode() == "strict"
