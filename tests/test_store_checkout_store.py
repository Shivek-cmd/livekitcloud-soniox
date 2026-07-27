"""PR 097 P2 — Store checkout idempotency persistence."""

from restaurant.store_checkout_store import (
    checkout_request_fingerprint,
    claim_checkout,
    complete_checkout,
    get_checkout,
)


def _summary(qty=1):
    return {
        "items": [{"id": "ITEM-1", "qty": qty, "unit_price": 5.0}],
        "order_type": "pickup",
        "customer": {"name": "Alex", "phone": "+15875551234"},
        "payment_preference": "later",
        "total": 5.0 * qty,
    }


def test_checkout_claim_complete_replay_and_conflict(monkeypatch, tmp_path):
    monkeypatch.setenv(
        "STORE_CHECKOUT_IDEMPOTENCY_PATH", str(tmp_path / "checkout.json")
    )
    first_fp = checkout_request_fingerprint(_summary())
    first = claim_checkout(
        checkout_key="checkout_store_12345",
        request_fingerprint=first_fp,
    )
    assert first["action"] == "claimed"
    assert (
        claim_checkout(
            checkout_key="checkout_store_12345",
            request_fingerprint=first_fp,
        )["action"]
        == "in_progress"
    )
    complete_checkout(
        checkout_key="checkout_store_12345",
        result={"ok": True, "status": "placed", "summary": {"order_id": "O1"}},
    )
    replay = claim_checkout(
        checkout_key="checkout_store_12345",
        request_fingerprint=first_fp,
    )
    assert replay["action"] == "replay"
    assert replay["result"]["summary"]["order_id"] == "O1"

    conflict = claim_checkout(
        checkout_key="checkout_store_12345",
        request_fingerprint=checkout_request_fingerprint(_summary(qty=2)),
    )
    assert conflict["action"] == "conflict"
    assert get_checkout("checkout_store_12345")["state"] == "completed"
