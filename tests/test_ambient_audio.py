"""Web and phone ambient audio config."""

from restaurant.channels.ambient_audio import (
    ambient_enabled,
    build_ambient_player,
    build_web_ambient_player,
    phone_ambient_enabled,
    web_ambient_enabled,
)


def test_web_ambient_enabled_default(monkeypatch):
    monkeypatch.delenv("WEB_AMBIENT_ENABLED", raising=False)
    assert web_ambient_enabled() is True


def test_phone_ambient_enabled_default(monkeypatch):
    monkeypatch.delenv("PHONE_AMBIENT_ENABLED", raising=False)
    assert phone_ambient_enabled() is True


def test_web_ambient_disabled(monkeypatch):
    monkeypatch.setenv("WEB_AMBIENT_ENABLED", "0")
    assert web_ambient_enabled() is False
    assert build_web_ambient_player() is None


def test_phone_ambient_disabled(monkeypatch):
    monkeypatch.setenv("PHONE_AMBIENT_ENABLED", "0")
    assert phone_ambient_enabled() is False
    assert build_ambient_player(is_phone=True) is None


def test_ambient_enabled_by_channel(monkeypatch):
    monkeypatch.setenv("WEB_AMBIENT_ENABLED", "1")
    monkeypatch.setenv("PHONE_AMBIENT_ENABLED", "0")
    assert ambient_enabled(is_phone=False) is True
    assert ambient_enabled(is_phone=True) is False


def test_build_web_ambient_player(monkeypatch):
    monkeypatch.setenv("WEB_AMBIENT_ENABLED", "1")
    monkeypatch.setenv("WEB_AMBIENT_VOLUME", "0.3")
    player = build_web_ambient_player()
    assert player is not None


def test_build_phone_ambient_player(monkeypatch):
    monkeypatch.setenv("PHONE_AMBIENT_ENABLED", "1")
    monkeypatch.setenv("PHONE_AMBIENT_VOLUME", "0.25")
    player = build_ambient_player(is_phone=True)
    assert player is not None
