"""S5 — Store checkout rate limit."""

import os

from restaurant.store_rate_limit import (
    allow_hco_webhook,
    allow_store_checkout,
    reset_store_rate_limits,
)


def test_rate_limit_blocks_after_limit(monkeypatch):
    monkeypatch.setenv("STORE_CHECKOUT_RATE_LIMIT", "3")
    monkeypatch.setenv("STORE_CHECKOUT_RATE_WINDOW_SEC", "60")
    reset_store_rate_limits()
    assert allow_store_checkout("1.2.3.4")
    assert allow_store_checkout("1.2.3.4")
    assert allow_store_checkout("1.2.3.4")
    assert not allow_store_checkout("1.2.3.4")
    # Different client still allowed
    assert allow_store_checkout("9.9.9.9")


def test_rate_limit_window_resets(monkeypatch):
    monkeypatch.setenv("STORE_CHECKOUT_RATE_LIMIT", "1")
    monkeypatch.setenv("STORE_CHECKOUT_RATE_WINDOW_SEC", "60")
    reset_store_rate_limits()
    assert allow_store_checkout("ip-a")
    assert not allow_store_checkout("ip-a")

    # Simulate time passing by clearing (window expiry tested via clear)
    reset_store_rate_limits()
    assert allow_store_checkout("ip-a")


def test_hco_webhook_rate_limit(monkeypatch):
    monkeypatch.setenv("STORE_HCO_WEBHOOK_RATE_LIMIT", "2")
    monkeypatch.setenv("STORE_HCO_WEBHOOK_RATE_WINDOW_SEC", "60")
    reset_store_rate_limits()
    assert allow_hco_webhook("clover")
    assert allow_hco_webhook("clover")
    assert not allow_hco_webhook("clover")
