"""Structural contract tests for the importable P4 n8n workflow."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ROOT / "n8n" / "sierra-ghl-connection-stub.json"
FIXTURES_PATH = ROOT / "n8n" / "fixtures" / "p4-events.json"


def _workflow() -> dict:
    return json.loads(WORKFLOW_PATH.read_text(encoding="utf-8"))


def _nodes(workflow: dict) -> dict[str, dict]:
    return {node["name"]: node for node in workflow["nodes"]}


def _outputs(workflow: dict, node_name: str) -> list[list[str]]:
    raw = workflow.get("connections", {}).get(node_name, {}).get("main", [])
    return [
        [edge["node"] for edge in branch if edge]
        for branch in raw
    ]


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


def test_workflow_json_has_unique_nodes_and_valid_edges():
    workflow = _workflow()
    names = [node["name"] for node in workflow["nodes"]]
    ids = [node["id"] for node in workflow["nodes"]]
    assert len(names) == len(set(names))
    assert len(ids) == len(set(ids))
    name_set = set(names)
    for source, connection in workflow["connections"].items():
        assert source in name_set
        for branches in connection.get("main", []):
            for edge in branches:
                assert edge["node"] in name_set


def test_webhook_authenticates_before_normalize_or_ghl():
    workflow = _workflow()
    nodes = _nodes(workflow)
    webhook = nodes["01 · Receive Order Webhook"]
    assert webhook["parameters"]["authentication"] == "headerAuth"
    assert _outputs(workflow, webhook["name"]) == [["P4 · Normalize Envelope"]]
    serialized = json.dumps(workflow)
    assert "X-Webhook-Secret" in serialized
    assert "N8N_WEBHOOK_SECRET=" not in serialized


def test_durable_dedup_claim_precedes_every_event_route():
    workflow = _workflow()
    path = [
        "P4 · Normalize Envelope",
        "P4 · Gate · Valid Envelope?",
        "P4 · Data Table · Find Event",
        "P4 · Resolve Duplicate",
        "P4 · Gate · Duplicate?",
    ]
    for left, right in zip(path, path[1:]):
        assert right in _outputs(workflow, left)[0]
    duplicate_outputs = _outputs(workflow, "P4 · Gate · Duplicate?")
    assert duplicate_outputs[0] == ["P4 · Respond · Duplicate"]
    assert duplicate_outputs[1] == ["P4 · Data Table · Claim Event"]
    assert _outputs(workflow, "P4 · Data Table · Claim Event") == [
        ["P4 · Route · order.placed?"]
    ]

    data_nodes = [
        node
        for node in workflow["nodes"]
        if node["type"] == "n8n-nodes-base.dataTable"
    ]
    assert {node["parameters"]["operation"] for node in data_nodes} == {
        "get",
        "upsert",
        "update",
    }
    for node in data_nodes:
        assert (
            node["parameters"]["dataTableId"]["value"]
            == "REPLACE_WITH_SIERRA_EVENTS_TABLE_ID"
        )

    claim_node = next(
        node for node in data_nodes
        if node["id"] == "p4000000-0000-4000-8000-000000000006"
    )
    claim_values = claim_node["parameters"]["columns"]["value"]
    assert "completed_at" not in claim_values


def test_event_branches_are_isolated_from_placed_opportunity_path():
    workflow = _workflow()
    placed_nodes = {
        "05 · GHL · Upsert Contact + Fields",
        "06 · GHL · Re-arm SMS (remove order-placed)",
        "07 · GHL · Apply Order Tags",
        "09 · GHL · Search Abandoned Opp",
        "11a · GHL · Move Opp → Placed",
        "11b · GHL · Create Opp Placed",
    }

    placed_start = _outputs(workflow, "P4 · Route · order.placed?")[0]
    paid_start = _outputs(workflow, "P4 · Route · order.paid?")[0]
    dispatched_start = _outputs(
        workflow, "P4 · Route · delivery.dispatched?"
    )[0]
    alert_start = _outputs(
        workflow, "P4 · Route · dispatch_required?"
    )[0]

    assert placed_nodes <= _reachable(workflow, placed_start)
    for start in (paid_start, dispatched_start, alert_start):
        assert placed_nodes.isdisjoint(_reachable(workflow, start))

    assert "P4 · Paid · Send Receipt SMS" in _reachable(workflow, paid_start)
    assert "P4 · Dispatched · Send Tracking SMS" in _reachable(
        workflow, dispatched_start
    )
    assert "P4 · Alert · Send Staff SMS" in _reachable(workflow, alert_start)


def test_unknown_event_dead_letters_without_ghl_side_effect():
    workflow = _workflow()
    p5_route = _outputs(workflow, "P4 · Route · dispatch_required?")[1]
    assert p5_route == ["P5 · Route · delivery.status_changed?"]
    unknown_start = _outputs(
        workflow, "P5 · Route · delivery.status_changed?"
    )[1]
    reachable = _reachable(workflow, unknown_start)
    assert "P4 · Build Dead Letter" in reachable
    assert "P4 · Data Table · Dead Letter" in reachable
    assert "P4 · Respond · Dead Letter" in reachable
    assert not any("GHL" in name or "Send Staff SMS" in name for name in reachable)


def test_sms_nodes_use_ghl_message_endpoint_and_v3():
    workflow = _workflow()
    nodes = _nodes(workflow)
    sms_names = (
        "P4 · Paid · Send Receipt SMS",
        "P4 · Dispatched · Send Tracking SMS",
        "P4 · Alert · Send Staff SMS",
    )
    for name in sms_names:
        params = nodes[name]["parameters"]
        assert params["method"] == "POST"
        assert params["url"].endswith("/conversations/messages")
        headers = {
            item["name"]: item["value"]
            for item in params["headerParameters"]["parameters"]
        }
        assert headers["Version"] == "v3"
        assert "'SMS'" in params["jsonBody"]


def test_staff_phone_is_private_variable_not_committed_value():
    workflow_text = WORKFLOW_PATH.read_text(encoding="utf-8")
    assert "$vars.BIZBULL_STAFF_ALERT_PHONE" in workflow_text
    assert '"staffPhone": "+' not in workflow_text


def test_p4_fixtures_cover_each_route_with_stable_event_ids():
    fixtures = json.loads(FIXTURES_PATH.read_text(encoding="utf-8"))
    expected = {
        "order.placed",
        "order.paid",
        "delivery.dispatched",
        "delivery.dispatch_required",
        "dead_letter",
    }
    assert {fixture["expected_route"] for fixture in fixtures} == expected
    event_ids = [fixture["payload"]["event_id"] for fixture in fixtures]
    assert len(event_ids) == len(set(event_ids))
    assert all(fixture["payload"]["schema_version"] == 1 for fixture in fixtures)
