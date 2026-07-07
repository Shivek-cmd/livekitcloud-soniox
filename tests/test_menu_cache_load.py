"""PR 058 — MenuCache.load merges voice labels for correct English voice_line."""

from pathlib import Path

import pytest

from restaurant.clover.menu import MenuCache
from restaurant.tenants.config import get_default_tenant


@pytest.fixture
def loaded_cache():
    tenant = get_default_tenant()
    path = tenant.cache_path()
    labels = Path(tenant.voice_labels_path)
    if not path.is_file():
        pytest.skip("menu cache not present")
    return MenuCache.load(path, voice_labels_path=labels)


def test_fish_pakora_loads_english_voice_line(loaded_cache):
    hit = loaded_cache.find_item("fish pakora")
    assert hit is not None
    assert hit.voice_line == "Fish Pakora"
    assert hit.speech_mode == "english"
    assert hit.speak_as == "ਅੰਮ੍ਰਿਤਸਰੀ ਮੱਛੀ ਪਕੋੜਾ"


def test_fish_curry_loads_english_voice_line(loaded_cache):
    hit = loaded_cache.find_item("Punjabi Fish Curry")
    assert hit is not None
    assert hit.voice_line == "Punjabi Fish Curry"
    assert hit.speech_mode == "english"
