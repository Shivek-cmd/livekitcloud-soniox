"""PR 032 — cross-script confidence menu matching + auto-add gate.

Regression anchor: live call 2026-07-02 where "ਮਿਕਸ ਪਕੌੜਾ ਪਲੈਟਰ" resolved to
Punjabi Fish Curry because the courtesy verb ਕਰ substring-matched ਕਰੀ (curry)
while the real item's Gurmukhi spelling variants scored zero.
"""

import pytest

from restaurant import menu_provider
from restaurant.clover.match import MatchIndex, content_tokens, phonetic_key
from restaurant.clover.menu import MenuCache
from restaurant.clover.models import CachedMenuItem
from restaurant.order_parse import can_auto_add_lines, parse_order_lines

LIVE_UTTERANCE = "ਹਾਂ ਜੀ, ਆਪਣੇ ਇੱਕ ਮਿਕਸ ਪਕੌੜਾ ਪਲੈਟਰ ਕਰ ਦਿਓ, ਤੇ ਇੱਕ ਸਮੋਸਾ ਚਾਟ ਕਰ ਦਿਓ।"


def _item(iid, name, speak_as, voice_line, aliases, price=1000):
    return CachedMenuItem(
        clover_item_id=iid,
        name=name,
        speak_as=speak_as,
        voice_line=voice_line,
        speech_mode="gurmukhi",
        price_cents=price,
        veg=True,
        available=True,
        category_id="",
        category_name="Test",
        aliases=aliases,
    )


def _cache(items=None) -> MenuCache:
    items = items or [
        _item(
            "PAKORA_PLATTER",
            "Mixed Pakora Platter",
            "ਮਿਸ਼ਰਿਤ ਪਕੋੜਾ ਪਲੇਟਰ",
            "ਮਿਸ਼ਰਿਤ ਪਕੋੜਾ ਪਲੇਟਰ",
            ["pakora platter", "pakora"],
        ),
        _item(
            "FISH_CURRY",
            "Punjabi Fish Curry",
            "ਪੰਜਾਬੀ ਮੱਛੀ ਕਰੀ",
            "ਪੰਜਾਬੀ ਮੱਛੀ ਕਰੀ",
            ["fish curry", "machhi curry"],
        ),
        _item(
            "FISH_PAKORA",
            "Amritsari Fish Pakora",
            "ਅੰਮ੍ਰਿਤਸਰੀ ਮੱਛੀ ਪਕੋੜਾ",
            "Fish Pakora",
            ["fish pakora", "amritsari fish"],
        ),
        _item(
            "SAMOSA_CHAAT",
            "Samosa Chaat (2 pcs)",
            "ਸਮੋਸਾ ਚਾਟ",
            "ਸਮੋਸਾ ਚਾਟ",
            ["samosa chaat", "samosa"],
        ),
        _item("GULAB_JAMUN", "Gulab Jamun", "ਗੁਲਾਬ ਜਾਮੁਨ", "ਗੁਲਾਬ ਜਾਮੁਨ", ["gulab jamun"]),
        _item("KHEER", "Kheer", "ਖੀਰ", "ਖੀਰ", ["kheer"]),
        _item("BUTTER_CHICKEN", "Butter Chicken", "ਬਟਰ ਚਿਕਨ", "ਬਟਰ ਚਿਕਨ", ["butter chicken"]),
    ]
    return MenuCache(items, tenant_id="test", synced_at="now")


@pytest.fixture
def clover_cache(monkeypatch):
    cache = _cache()
    monkeypatch.setattr(menu_provider, "_cache", cache)
    monkeypatch.setattr(menu_provider, "_cache_loaded", True)
    return cache


# ---------------------------------------------------------------------------
# Phonetic layer


def test_phonetic_key_folds_matra_variants():
    # STT variants and Latin all land on the same key
    assert phonetic_key("ਪਕੌੜਾ") == phonetic_key("ਪਕੋੜਾ") == phonetic_key("pakora")
    assert phonetic_key("ਪਲੈਟਰ") == phonetic_key("ਪਲੇਟਰ") == phonetic_key("platter")
    assert phonetic_key("ਸਮੋਸਾ") == phonetic_key("samosa")
    assert phonetic_key("ਚਾਟ") == phonetic_key("chaat")


def test_content_tokens_drop_courtesy_words():
    assert content_tokens("ਹਾਂ ਜੀ, ਆਪਣੇ ਇੱਕ ਕਰ ਦਿਓ।") == []
    assert content_tokens("can you please add one") == []
    assert content_tokens("ਇੱਕ ਮਿਕਸ ਪਕੌੜਾ ਪਲੈਟਰ ਕਰ ਦਿਓ") == ["ਮਿਕਸ", "ਪਕੌੜਾ", "ਪਲੈਟਰ"]


# ---------------------------------------------------------------------------
# Live transcript regression


def test_live_transcript_resolves_correct_items(clover_cache):
    lines = parse_order_lines(LIVE_UTTERANCE)
    names = [line.item["name"] for line in lines]
    assert names == ["Mixed Pakora Platter", "Samosa Chaat (2 pcs)"]
    assert all(line.quantity == 1 for line in lines)
    assert can_auto_add_lines(lines) is True


def test_courtesy_verb_never_matches_curry(clover_cache):
    assert menu_provider.find_item("ਕਰ") is None
    assert menu_provider.find_item("ਕਰ ਦਿਓ") is None
    assert menu_provider.find_item("ਹਾਂ ਜੀ") is None


def test_ambiguous_fish_disambiguates_not_guesses(clover_cache):
    # Live-call bug: caller said "one fish" and got Fish Curry + two Fish Pakora.
    # "fish" is ambiguous — the strict matcher must abstain, and disambiguation
    # must surface BOTH real dishes so the agent asks which one instead of the
    # model inventing dishes/quantities.
    assert menu_provider.find_item("fish") is None
    assert menu_provider.find_item("ਮੱਛੀ") is None
    names = {o["name"] for o in menu_provider.disambiguation_options("fish")}
    assert names == {"Punjabi Fish Curry", "Amritsari Fish Pakora"}
    names_pa = {o["name"] for o in menu_provider.disambiguation_options("ਮੱਛੀ")}
    assert names_pa == {"Punjabi Fish Curry", "Amritsari Fish Pakora"}


def test_disambiguation_empty_for_non_item(clover_cache):
    assert menu_provider.disambiguation_options("unicorn burger") == []


def test_specific_fish_dish_still_resolves(clover_cache):
    # Naming the specific dish must still add cleanly — no false disambiguation.
    assert menu_provider.find_item("fish curry")["name"] == "Punjabi Fish Curry"
    assert menu_provider.find_item("fish pakora")["name"] == "Amritsari Fish Pakora"


def test_gurmukhi_spelling_variant_matches(clover_cache):
    hit = menu_provider.find_item("ਮਿਕਸ ਪਕੌੜਾ ਪਲੈਟਰ")
    assert hit is not None
    assert hit["name"] == "Mixed Pakora Platter"
    assert hit["match_confidence"] >= 0.8


# ---------------------------------------------------------------------------
# Abstain behaviour


def test_ambiguous_shared_token_abstains(clover_cache):
    # "fish" appears in Fish Curry and Fish Pakora — must not pick one
    assert clover_cache.find_item("ਮੱਛੀ") is None


def test_compressed_spelling_needs_explicit_alias():
    # Live-call regression (PR 052): "ਦਾਲਮਖਨੀ" (no space) is one token, but
    # the canonical label "ਦਾਲ ਮੱਖਣੀ" is two — content_tokens() splits on
    # whitespace, so a fused query token can never align 1:1 against two
    # separate label tokens with this token-based matcher. Without an
    # explicit alias for the fused spelling, this abstains — confirming the
    # root cause is a real architectural limit, not something to "just fix"
    # in the scoring algorithm without adding real risk to an already
    # carefully-tuned matcher (PR 032/033/034).
    cache = _cache(
        [
            _item(
                "DAL_MAKHANI",
                "Dal Makhani",
                "ਦਾਲ ਮੱਖਣੀ",
                "ਦਾਲ ਮੱਖਣੀ",
                ["dal makhani", "black dal"],
            ),
        ]
    )
    assert cache.find_item("ਦਾਲਮਖਨੀ") is None

    # Adding the exact fused spelling as an alias (the fix — same pattern as
    # data/clover_voice_labels.json) resolves it with full confidence.
    cache_with_alias = _cache(
        [
            _item(
                "DAL_MAKHANI",
                "Dal Makhani",
                "ਦਾਲ ਮੱਖਣੀ",
                "ਦਾਲ ਮੱਖਣੀ",
                ["dal makhani", "black dal", "ਦਾਲਮਖਨੀ"],
            ),
        ]
    )
    hit = cache_with_alias.find_item("ਦਾਲਮਖਨੀ")
    assert hit is not None
    assert hit.name == "Dal Makhani"


def test_unique_single_token_matches(clover_cache):
    hit = clover_cache.find_item("jamun")
    assert hit is not None
    assert hit.name == "Gulab Jamun"


def test_explicit_single_alias_wins(clover_cache):
    # data deliberately aliases bare "pakora" to the platter — respect it
    hit = clover_cache.find_item("ਪਕੌੜਾ")
    assert hit is not None
    assert hit.name == "Mixed Pakora Platter"


def test_exact_name_still_full_confidence(clover_cache):
    scored = clover_cache.find_item_scored("butter chicken")
    assert scored is not None
    assert scored[0].name == "Butter Chicken"
    assert scored[1] == 1.0


def test_extra_descriptors_do_not_break_match(clover_cache):
    hit = clover_cache.find_item("one butter chicken extra spicy please")
    assert hit is not None
    assert hit.name == "Butter Chicken"


# ---------------------------------------------------------------------------
# Auto-add confidence gate


def test_low_confidence_line_blocks_auto_add(clover_cache):
    lines = parse_order_lines(LIVE_UTTERANCE)
    assert len(lines) == 2
    weak = [
        type(lines[0])(quantity=1, item=lines[0].item, confidence=0.5),
        lines[1],
    ]
    assert can_auto_add_lines(weak) is False


def test_auto_add_threshold_env(clover_cache, monkeypatch):
    monkeypatch.setenv("AUTO_ADD_MIN_CONFIDENCE", "1.1")
    lines = parse_order_lines(LIVE_UTTERANCE)
    assert can_auto_add_lines(lines) is False


# ---------------------------------------------------------------------------
# Determinism + kill switch


def test_result_independent_of_menu_order(monkeypatch):
    base = _cache()
    reversed_cache = MenuCache(
        list(reversed(base._items)), tenant_id="test", synced_at="now"
    )
    a = base.find_item("ਮਿਕਸ ਪਕੌੜਾ ਪਲੈਟਰ")
    b = reversed_cache.find_item("ਮਿਕਸ ਪਕੌੜਾ ਪਲੈਟਰ")
    assert a is not None and b is not None
    assert a.name == b.name == "Mixed Pakora Platter"


def test_legacy_kill_switch_restores_old_matcher(clover_cache, monkeypatch):
    monkeypatch.setenv("MENU_MATCH_LEGACY", "1")
    # old matcher: courtesy verb ਕਰ substring-matches ਕਰੀ → Fish Curry
    hit = clover_cache.find_item("ਕਰ")
    assert hit is not None
    assert hit.name == "Punjabi Fish Curry"


def test_match_index_direct():
    idx = MatchIndex(
        [
            ("A", "Mixed Pakora Platter", ["Mixed Pakora Platter", "pakora platter"]),
            ("B", "Punjabi Fish Curry", ["Punjabi Fish Curry", "fish curry"]),
        ]
    )
    m = idx.best("ਇੱਕ ਮਿਕਸ ਪਕੌੜਾ ਪਲੈਟਰ ਕਰ ਦਿਓ")
    assert m is not None and m.key == "A"
    assert idx.best("ਕਰ ਦਿਓ") is None
