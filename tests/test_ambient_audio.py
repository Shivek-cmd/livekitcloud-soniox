"""Web ambient audio config."""

from restaurant.ambient_audio import build_web_ambient_player, web_ambient_enabled


def test_web_ambient_enabled_default(monkeypatch):
    monkeypatch.delenv("WEB_AMBIENT_ENABLED", raising=False)
    assert web_ambient_enabled() is True


def test_web_ambient_disabled(monkeypatch):
    monkeypatch.setenv("WEB_AMBIENT_ENABLED", "0")
    assert web_ambient_enabled() is False
    assert build_web_ambient_player() is None


def test_build_web_ambient_player(monkeypatch):
    monkeypatch.setenv("WEB_AMBIENT_ENABLED", "1")
    monkeypatch.setenv("WEB_AMBIENT_VOLUME", "0.3")
    player = build_web_ambient_player()
    assert player is not None
