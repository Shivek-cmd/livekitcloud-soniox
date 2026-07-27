"""PR 093 P1 — Uber Direct OAuth + Store delivery quote."""

from __future__ import annotations

import json

import pytest

from restaurant.uber_direct.address import (
    address_fingerprint,
    to_uber_address_json,
    validate_structured_address,
)
from restaurant.uber_direct.client import (
    CreatedDelivery,
    UberDirectError,
    clear_token_cache,
    create_delivery_quote,
    fetch_access_token,
)
from restaurant.uber_direct.config import (
    StructuredAddress,
    UberDirectCredentials,
    public_store_flags,
    store_uber_direct_enabled,
)
from restaurant.uber_direct.service import (
    dispatch_store_delivery,
    request_store_delivery_quote,
)


CREDS = UberDirectCredentials(
    customer_id="cust-test",
    client_id="client-test",
    client_secret="secret-test",
)


def _pickup() -> StructuredAddress:
    return StructuredAddress(
        street="99 Wye Rd #31",
        city="Sherwood Park",
        state="AB",
        postal="T8B 1C9",
        country="CA",
        phone="+17805550100",
        name="Bizbull Restaurant",
    )


def _dropoff() -> StructuredAddress:
    return StructuredAddress(
        street="100 Main St",
        city="Edmonton",
        state="AB",
        postal="T5J 0N3",
        country="CA",
    )


def test_validate_ca_postal_normalizes():
    addr, blockers = validate_structured_address(
        street="100 Main St",
        city="Edmonton",
        state="ab",
        postal="t5j0n3",
        country="CA",
    )
    assert blockers == []
    assert addr is not None
    assert addr.postal == "T5J 0N3"
    assert addr.state == "AB"


def test_validate_rejects_bad_postal():
    addr, blockers = validate_structured_address(
        street="100 Main St",
        city="Edmonton",
        state="AB",
        postal="12345",
        country="CA",
    )
    assert addr is None
    assert any("postal" in b.lower() for b in blockers)


def test_to_uber_address_json_shape():
    raw = to_uber_address_json(_pickup())
    parsed = json.loads(raw)
    assert parsed["city"] == "Sherwood Park"
    assert parsed["state"] == "AB"
    assert parsed["zip_code"] == "T8B 1C9"
    assert parsed["country"] == "CA"
    assert "99 Wye Rd #31" in parsed["street_address"]


def test_address_fingerprint_ignores_harmless_formatting():
    left, left_blockers = validate_structured_address(
        street="100 Main St",
        city="Edmonton",
        state="AB",
        postal="T5J 0N3",
        country="CA",
        unit="Unit 2",
    )
    right, right_blockers = validate_structured_address(
        street="  100   MAIN st ",
        city="edmonton",
        state="ab",
        postal="t5j0n3",
        country="canada",
        unit="unit 2",
    )
    assert left_blockers == right_blockers == []
    assert left is not None and right is not None
    assert address_fingerprint(left) == address_fingerprint(right)


def test_address_fingerprint_changes_with_destination():
    assert address_fingerprint(_dropoff()) != address_fingerprint(
        StructuredAddress(
            street="101 Main St",
            city="Edmonton",
            state="AB",
            postal="T5J 0N3",
            country="CA",
        )
    )


def test_kill_switch_off_returns_fallback(monkeypatch):
    monkeypatch.setenv("STORE_UBER_DIRECT_ENABLED", "0")
    monkeypatch.setenv("DELIVERY_CHARGE", "5")
    result = request_store_delivery_quote(
        {
            "dropoff": {
                "street": "100 Main St",
                "city": "Edmonton",
                "state": "AB",
                "postal": "T5J 0N3",
            }
        }
    )
    assert result.ok is True
    assert result.enabled is False
    assert result.fee == 5.0
    assert result.fee_policy == "fallback_flat"
    assert result.quote_id is None


def test_enabled_missing_pickup_config(monkeypatch):
    monkeypatch.setenv("STORE_UBER_DIRECT_ENABLED", "1")
    monkeypatch.setenv("UBER_DIRECT_CUSTOMER_ID", "c")
    monkeypatch.setenv("UBER_DIRECT_CLIENT_ID", "i")
    monkeypatch.setenv("UBER_DIRECT_CLIENT_SECRET", "s")
    for key in (
        "UBER_DIRECT_PICKUP_STREET",
        "UBER_DIRECT_PICKUP_CITY",
        "UBER_DIRECT_PICKUP_STATE",
        "UBER_DIRECT_PICKUP_POSTAL",
    ):
        monkeypatch.delenv(key, raising=False)

    result = request_store_delivery_quote(
        {
            "dropoff": {
                "street": "100 Main St",
                "city": "Edmonton",
                "state": "AB",
                "postal": "T5J 0N3",
            }
        }
    )
    assert result.ok is False
    assert result.enabled is True
    assert any("pickup" in b.lower() for b in result.blockers)


def test_enabled_invalid_dropoff(monkeypatch):
    monkeypatch.setenv("STORE_UBER_DIRECT_ENABLED", "1")
    result = request_store_delivery_quote(
        {"dropoff": {"street": "", "city": "", "state": "", "postal": ""}}
    )
    assert result.ok is False
    assert len(result.blockers) >= 1


def test_fetch_access_token_caches(monkeypatch):
    clear_token_cache()
    calls = {"n": 0}

    def fake_request(method, url, **kwargs):
        calls["n"] += 1
        assert "oauth" in url
        return {"access_token": "tok-1", "expires_in": 3600, "token_type": "Bearer"}

    monkeypatch.setattr(
        "restaurant.uber_direct.client._request_json", fake_request
    )
    t1 = fetch_access_token(CREDS)
    t2 = fetch_access_token(CREDS)
    assert t1 == t2 == "tok-1"
    assert calls["n"] == 1


def test_create_delivery_quote_parses_fee(monkeypatch):
    clear_token_cache()

    def fake_request(method, url, **kwargs):
        if "oauth" in url:
            return {"access_token": "tok", "expires_in": 3600}
        assert method == "POST"
        assert "/delivery_quotes" in url
        body = kwargs.get("body") or {}
        assert "pickup_address" in body
        assert "dropoff_address" in body
        return {
            "kind": "delivery_quote",
            "id": "dqt_test123",
            "fee": 840,
            "currency_type": "CAD",
            "duration": 40,
            "pickup_duration": 20,
            "dropoff_eta": "2026-07-24T22:00:00Z",
            "expires": "2026-07-24T21:15:00Z",
        }

    monkeypatch.setattr(
        "restaurant.uber_direct.client._request_json", fake_request
    )
    quote = create_delivery_quote(
        pickup=_pickup(), dropoff=_dropoff(), creds=CREDS
    )
    assert quote.quote_id == "dqt_test123"
    assert quote.fee_cents == 840
    assert quote.fee == 8.40
    assert quote.currency == "CAD"
    assert quote.duration_minutes == 40


def test_request_quote_pass_through(monkeypatch):
    monkeypatch.setenv("STORE_UBER_DIRECT_ENABLED", "1")
    monkeypatch.setenv("UBER_DIRECT_CUSTOMER_ID", "c")
    monkeypatch.setenv("UBER_DIRECT_CLIENT_ID", "i")
    monkeypatch.setenv("UBER_DIRECT_CLIENT_SECRET", "s")
    monkeypatch.setenv("UBER_DIRECT_PICKUP_STREET", "99 Wye Rd #31")
    monkeypatch.setenv("UBER_DIRECT_PICKUP_CITY", "Sherwood Park")
    monkeypatch.setenv("UBER_DIRECT_PICKUP_STATE", "AB")
    monkeypatch.setenv("UBER_DIRECT_PICKUP_POSTAL", "T8B 1C9")
    monkeypatch.setenv("UBER_DIRECT_PICKUP_COUNTRY", "CA")
    monkeypatch.setenv("UBER_DIRECT_FEE_POLICY", "pass_through")

    from restaurant.uber_direct.client import DeliveryQuote

    def fake_create(**kwargs):
        return DeliveryQuote(
            quote_id="dqt_abc",
            fee_cents=725,
            currency="CAD",
            duration_minutes=35,
            pickup_duration_minutes=18,
            dropoff_eta="2026-07-24T22:10:00Z",
            expires_at="2026-07-24T21:20:00Z",
            raw={},
        )

    monkeypatch.setattr(
        "restaurant.uber_direct.service.create_delivery_quote", fake_create
    )
    result = request_store_delivery_quote(
        {
            "dropoff": {
                "street": "100 Main St",
                "city": "Edmonton",
                "state": "AB",
                "postal": "T5J 0N3",
            },
            "subtotal": 40.0,
        }
    )
    assert result.ok is True
    assert result.enabled is True
    assert result.quote_id == "dqt_abc"
    assert result.fee == 7.25
    assert result.fee_policy == "pass_through"
    assert "Edmonton" in (result.dropoff_line or "")


def test_quote_uber_error_returns_blockers(monkeypatch):
    monkeypatch.setenv("STORE_UBER_DIRECT_ENABLED", "1")
    monkeypatch.setenv("UBER_DIRECT_CUSTOMER_ID", "c")
    monkeypatch.setenv("UBER_DIRECT_CLIENT_ID", "i")
    monkeypatch.setenv("UBER_DIRECT_CLIENT_SECRET", "s")
    monkeypatch.setenv("UBER_DIRECT_PICKUP_STREET", "99 Wye Rd #31")
    monkeypatch.setenv("UBER_DIRECT_PICKUP_CITY", "Sherwood Park")
    monkeypatch.setenv("UBER_DIRECT_PICKUP_STATE", "AB")
    monkeypatch.setenv("UBER_DIRECT_PICKUP_POSTAL", "T8B 1C9")

    def boom(**kwargs):
        raise UberDirectError("Uber HTTP 400", status=400, payload={"code": "bad"})

    monkeypatch.setattr(
        "restaurant.uber_direct.service.create_delivery_quote", boom
    )
    result = request_store_delivery_quote(
        {
            "dropoff": {
                "street": "100 Main St",
                "city": "Edmonton",
                "state": "AB",
                "postal": "T5J 0N3",
            }
        }
    )
    assert result.ok is False
    assert any("quote" in b.lower() for b in result.blockers)


def test_public_store_flags(monkeypatch):
    monkeypatch.setenv("STORE_UBER_DIRECT_ENABLED", "1")
    monkeypatch.setenv("UBER_DIRECT_PREP_MINUTES", "25")
    flags = public_store_flags()
    assert flags["uber_direct_enabled"] is True
    assert flags["uber_direct_prep_minutes"] == 25
    assert store_uber_direct_enabled() is True


def test_dispatch_uses_checked_out_dropoff_not_quote_copy(monkeypatch, tmp_path):
    monkeypatch.setenv("STORE_UBER_DIRECT_ENABLED", "1")
    monkeypatch.setenv("UBER_DIRECT_QUOTE_STORE_PATH", str(tmp_path / "quotes.json"))
    monkeypatch.setenv(
        "UBER_DIRECT_DELIVERY_STORE_PATH", str(tmp_path / "deliveries.json")
    )
    monkeypatch.setenv("UBER_DIRECT_PICKUP_STREET", "99 Wye Rd #31")
    monkeypatch.setenv("UBER_DIRECT_PICKUP_CITY", "Sherwood Park")
    monkeypatch.setenv("UBER_DIRECT_PICKUP_STATE", "AB")
    monkeypatch.setenv("UBER_DIRECT_PICKUP_POSTAL", "T8B 1C9")
    from restaurant.uber_direct.quote_store import record_quote

    checkout_dropoff = _dropoff()
    record_quote(
        quote_id="dqt_bound",
        fee_cents=725,
        currency="CAD",
        expires_at="2099-01-01T00:00:00Z",
        # Simulate stale/tampered informational quote data. Dispatch must ignore it.
        dropoff={
            "street": "999 Wrong Ave",
            "city": "Edmonton",
            "state": "AB",
            "postal": "T5J 0N3",
            "country": "CA",
        },
        dropoff_address=checkout_dropoff,
    )

    seen = {"calls": 0}

    def fake_create_delivery(**kwargs):
        seen["calls"] += 1
        seen["dropoff"] = kwargs["dropoff"]
        return CreatedDelivery(
            delivery_id="del_bound",
            tracking_url="https://tracking.example/del_bound",
            status="pending",
            fee_cents=725,
            raw={},
        )

    monkeypatch.setattr(
        "restaurant.uber_direct.client.create_delivery",
        fake_create_delivery,
    )
    summary = {
        "order_type": "delivery",
        "uber_quote_id": "dqt_bound",
        "delivery_dropoff": {
            "street": checkout_dropoff.street,
            "city": checkout_dropoff.city,
            "state": checkout_dropoff.state,
            "postal": checkout_dropoff.postal,
            "country": checkout_dropoff.country,
        },
        "customer": {"name": "Alex", "phone": "+15875551234"},
        "items": [{"name": "Sweet Lassi", "qty": 1, "unit_price": 5.0}],
        "order_id": "ORDER-1",
    }
    result = dispatch_store_delivery(summary)
    assert result["ok"] is True
    assert seen["dropoff"].street == "100 Main St"
    assert seen["dropoff"].phone == "+15875551234"
    from restaurant.uber_direct.delivery_store import get_delivery

    delivery = get_delivery("del_bound")
    assert delivery is not None
    assert delivery["notification_context"] == {
        "channel": "web_store",
        "customer_name": "Alex",
        "customer_phone": "+15875551234",
        "clover_order_id": "ORDER-1",
        "order_type": "delivery",
        "total": None,
        "session_id": None,
    }
    replay = dispatch_store_delivery(summary)
    assert replay["ok"] is True
    assert replay["reused"] is True
    assert seen["calls"] == 1


def test_dispatch_unknown_outcome_requires_staff_and_is_not_retried(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("STORE_UBER_DIRECT_ENABLED", "1")
    monkeypatch.setenv("UBER_DIRECT_QUOTE_STORE_PATH", str(tmp_path / "quotes.json"))
    monkeypatch.setenv(
        "UBER_DIRECT_DELIVERY_STORE_PATH", str(tmp_path / "deliveries.json")
    )
    monkeypatch.setenv("UBER_DIRECT_PICKUP_STREET", "99 Wye Rd #31")
    monkeypatch.setenv("UBER_DIRECT_PICKUP_CITY", "Sherwood Park")
    monkeypatch.setenv("UBER_DIRECT_PICKUP_STATE", "AB")
    monkeypatch.setenv("UBER_DIRECT_PICKUP_POSTAL", "T8B 1C9")
    from restaurant.uber_direct.delivery_store import get_order_dispatch
    from restaurant.uber_direct.quote_store import record_quote

    checkout_dropoff = _dropoff()
    record_quote(
        quote_id="dqt_unknown",
        fee_cents=725,
        currency="CAD",
        expires_at="2099-01-01T00:00:00Z",
        dropoff_address=checkout_dropoff,
    )
    calls = {"n": 0}

    def timeout(**_kwargs):
        calls["n"] += 1
        raise UberDirectError("network timeout")

    monkeypatch.setattr("restaurant.uber_direct.client.create_delivery", timeout)
    summary = {
        "order_type": "delivery",
        "uber_quote_id": "dqt_unknown",
        "delivery_dropoff": {
            "street": checkout_dropoff.street,
            "city": checkout_dropoff.city,
            "state": checkout_dropoff.state,
            "postal": checkout_dropoff.postal,
            "country": checkout_dropoff.country,
        },
        "customer": {"name": "Alex", "phone": "+15875551234"},
        "items": [{"name": "Sweet Lassi", "qty": 1, "unit_price": 5.0}],
        "order_id": "ORDER-UNKNOWN",
        "session_id": "web-store-unknown",
        "checkout_key": "checkout_unknown_12345",
    }
    first = dispatch_store_delivery(summary)
    second = dispatch_store_delivery(summary)
    assert first["dispatch_state"] == "dispatch_required"
    assert first["error"] == "uber_create_outcome_unknown"
    assert summary["uber_dispatch_uncertain"] is True
    assert second["reused"] is True
    assert calls["n"] == 1
    record = get_order_dispatch("ORDER-UNKNOWN")
    assert record is not None
    assert record["state"] == "dispatch_required"
    assert record["attempts"] == 1
