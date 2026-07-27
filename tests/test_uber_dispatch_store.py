"""PR 097 P2 — durable Uber dispatch claims and state."""

from __future__ import annotations

import json

from restaurant.uber_direct.delivery_store import (
    claim_order_dispatch,
    get_delivery,
    get_order_dispatch,
    mark_dispatch_required,
    mark_dispatch_success,
)


def test_dispatch_claim_success_and_replay(monkeypatch, tmp_path):
    path = tmp_path / "deliveries.json"
    monkeypatch.setenv("UBER_DIRECT_DELIVERY_STORE_PATH", str(path))

    claim = claim_order_dispatch(
        order_key="ORDER-1",
        quote_id="dqt_1",
        checkout_key="checkout_123456789",
        session_id="session-1",
    )
    assert claim["action"] == "claimed"
    assert claim["attempts"] == 1
    assert (
        claim_order_dispatch(order_key="ORDER-1", quote_id="dqt_1")["action"]
        == "in_progress"
    )

    marked = mark_dispatch_success(
        order_key="ORDER-1",
        delivery_id="del_1",
        status="pending",
        tracking_url="https://tracking.example/del_1",
        raw={"id": "del_1"},
    )
    assert marked is not None
    assert marked["state"] == "dispatched"
    replay = claim_order_dispatch(order_key="ORDER-1", quote_id="dqt_1")
    assert replay["action"] == "dispatched"
    assert replay["delivery_id"] == "del_1"
    delivery = get_delivery("del_1")
    assert delivery is not None
    assert delivery["order_key"] == "ORDER-1"


def test_stale_creating_claim_becomes_manual_review(monkeypatch, tmp_path):
    path = tmp_path / "deliveries.json"
    monkeypatch.setenv("UBER_DIRECT_DELIVERY_STORE_PATH", str(path))
    path.write_text(
        json.dumps(
            {
                "deliveries": {},
                "orders": {
                    "ORDER-2": {
                        "order_key": "ORDER-2",
                        "quote_id": "dqt_2",
                        "state": "creating",
                        "attempts": 1,
                        "attempt_started_at": "2020-01-01T00:00:00Z",
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    result = claim_order_dispatch(
        order_key="ORDER-2",
        quote_id="dqt_2",
        stale_after_seconds=1,
    )
    assert result["action"] == "dispatch_required"
    assert result["reason"] == "dispatch_outcome_unknown"
    assert result["uncertain_outcome"] is True


def test_explicit_dispatch_failure_is_durable(monkeypatch, tmp_path):
    monkeypatch.setenv(
        "UBER_DIRECT_DELIVERY_STORE_PATH", str(tmp_path / "deliveries.json")
    )
    claim_order_dispatch(order_key="ORDER-3", quote_id="dqt_3")
    record = mark_dispatch_required(
        order_key="ORDER-3",
        reason="uber_create_rejected:400",
        uncertain_outcome=False,
    )
    assert record is not None
    assert record["state"] == "dispatch_required"
    assert record["attempts"] == 1
    assert get_order_dispatch("ORDER-3")["reason"] == "uber_create_rejected:400"
