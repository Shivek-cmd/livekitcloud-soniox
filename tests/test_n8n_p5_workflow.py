"""Structural contract tests for the repository P5 n8n lifecycle branch."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ROOT / "n8n" / "sierra-ghl-connection-stub.json"
FIXTURES_PATH = ROOT / "n8n" / "fixtures" / "p5-delivery-status-events.json"


def _workflow() -> dict:
    return json.loads(WORKFLOW_PATH.read_text(encoding="utf-8"))


def _nodes(workflow: dict) -> dict[str, dict]:
    return {node["name"]: node for node in workflow["nodes"]}


def _outputs(workflow: dict, node_name: str) -> list[list[str]]:
    raw = workflow.get("connections", {}).get(node_name, {}).get("main", [])
    return [[edge["node"] for edge in branch] for branch in raw]


def _reachable(workflow: dict, starts: list[str]) -> set[str]:
    seen: set[str] = set()
    pending = list(starts)
    while pending:
        name = pending.pop()
        if name in seen:
            continue
        seen.add(name)
        for branch in _outputs(workflow, name):
            pending.extend(branch)
    return seen


def test_p5_route_is_after_all_p4_event_routes_and_before_dead_letter():
    workflow = _workflow()
    assert _outputs(workflow, "P4 · Route · dispatch_required?")[1] == [
        "P5 · Route · delivery.status_changed?"
    ]
    assert _outputs(workflow, "P5 · Route · delivery.status_changed?") == [
        ["P5 · Gate · Valid Status Event?"],
        ["P4 · Build Dead Letter"],
    ]
    assert _outputs(workflow, "P5 · Gate · Valid Status Event?")[1] == [
        "P4 · Build Dead Letter"
    ]


def test_every_valid_status_updates_contact_before_milestone_routing():
    workflow = _workflow()
    valid_gate = _nodes(workflow)["P5 · Gate · Valid Status Event?"]
    gate_conditions = valid_gate["parameters"]["conditions"]["conditions"]
    assert len(gate_conditions) == 2
    assert "staff_alert" in gate_conditions[1]["leftValue"]
    assert _outputs(workflow, "P5 · Gate · Valid Status Event?")[0] == [
        "P5 · Status · Upsert Customer"
    ]
    assert _outputs(workflow, "P5 · Status · Upsert Customer") == [
        ["P5 · Gate · Delivered?"]
    ]
    node = _nodes(workflow)["P5 · Status · Upsert Customer"]
    assert node["parameters"]["url"].endswith("/contacts/upsert")
    normalize = _nodes(workflow)["P4 · Normalize Envelope"]["parameters"]["jsCode"]
    assert "Q59Rb7F84BNHvrL1gzOJ" in normalize
    assert "delivery.${deliveryStatus}" in normalize


def test_only_delivered_branch_can_move_opportunity_to_completed():
    workflow = _workflow()
    nodes = _nodes(workflow)
    move_name = "P5 · Delivered · Move Opportunity → Completed"
    assert move_name in _reachable(
        workflow, _outputs(workflow, "P5 · Gate · Delivered?")[0]
    )
    assert move_name not in _reachable(
        workflow, _outputs(workflow, "P5 · Gate · Delivered?")[1]
    )
    move = nodes[move_name]["parameters"]
    assert move["method"] == "PUT"
    assert "35a07d49-4524-48b3-96c7-a89b679618f7" in move["jsonBody"]
    assert "wCQVOwUah69xD6KHFrsi" in move["jsonBody"]
    assert "status: 'open'" in move["jsonBody"]
    resolve = nodes["P5 · Delivered · Resolve Opportunity"]["parameters"]["jsCode"]
    assert "mqQZGfXEM7Ixbfcpbeej" in resolve
    assert "clover_order_id" in resolve
    assert "fieldValueString" in resolve


def test_customer_sms_policy_is_limited_to_on_way_and_delivered():
    workflow = _workflow()
    nodes = _nodes(workflow)
    p5_sms = {
        name
        for name, node in nodes.items()
        if name.startswith("P5")
        and node["type"] == "n8n-nodes-base.httpRequest"
        and node["parameters"].get("url", "").endswith("/conversations/messages")
    }
    assert p5_sms == {
        "P5 · On Way · Send Customer SMS",
        "P5 · Delivered · Send Customer SMS",
        "P5 · Issue · Send Staff SMS",
    }
    for name in p5_sms:
        headers = {
            header["name"]: header["value"]
            for header in nodes[name]["parameters"]["headerParameters"]["parameters"]
        }
        assert headers["Version"] == "v3"
    assert "P5 · Issue · Send Staff SMS" in _reachable(
        workflow, _outputs(workflow, "P5 · Gate · Staff Alert?")[0]
    )
    assert "P5 · On Way · Send Customer SMS" not in _reachable(
        workflow, _outputs(workflow, "P5 · Gate · Staff Alert?")[0]
    )
    assert "P5 · Delivered · Send Customer SMS" not in _reachable(
        workflow, _outputs(workflow, "P5 · Gate · Staff Alert?")[0]
    )


def test_non_milestone_status_finishes_as_crm_only():
    workflow = _workflow()
    assert _outputs(workflow, "P5 · Gate · Staff Alert?")[1] == [
        "P5 · Status · Build CRM Result"
    ]
    assert _outputs(workflow, "P5 · Status · Build CRM Result") == [
        ["P4 · Prepare Result"]
    ]


def test_missing_delivered_opportunity_is_retryable_failure():
    workflow = _workflow()
    assert _outputs(workflow, "P5 · Gate · Opportunity Found?")[1] == [
        "P5 · Delivered · Build Missing Opportunity Failure"
    ]
    node = _nodes(workflow)[
        "P5 · Delivered · Build Missing Opportunity Failure"
    ]
    code = node["parameters"]["jsCode"]
    assert "side_effect_ok: false" in code
    assert "delivery_opportunity_not_found" in code
    assert _outputs(workflow, node["name"]) == [["P4 · Prepare Result"]]


def test_p5_fixtures_cover_lifecycle_policies_with_stable_ids():
    fixtures = json.loads(FIXTURES_PATH.read_text(encoding="utf-8"))
    assert {fixture["expected_route"] for fixture in fixtures} == {
        "crm_only",
        "on_the_way",
        "delivered",
        "staff_alert",
        "dead_letter",
    }
    event_ids = [fixture["payload"]["event_id"] for fixture in fixtures]
    assert len(event_ids) == len(set(event_ids))
    assert all(
        fixture["payload"]["event"] == "delivery.status_changed"
        and fixture["payload"]["schema_version"] == 1
        for fixture in fixtures
    )
    staff_statuses = {
        fixture["payload"]["order"]["delivery_status"]
        for fixture in fixtures
        if fixture["expected_route"] == "staff_alert"
    }
    assert staff_statuses == {"canceled", "failed", "returned"}


def test_p5_keeps_workflow_inactive_and_private_config_uncommitted():
    workflow = _workflow()
    text = WORKFLOW_PATH.read_text(encoding="utf-8")
    assert workflow["active"] is False
    assert "$vars.BIZBULL_STAFF_ALERT_PHONE" in text
    assert '"staffPhone": "+' not in text
