"""Unit tests for orchestration response helpers.

These tests exercise branching in serialization and formatting helpers used by
API and Slack handlers.
"""

from types import SimpleNamespace
from datetime import datetime

import pytest

from modules.groups.core import orchestration_responses as orch


@pytest.mark.unit
def test_serialize_primary_all_fields():
    status = SimpleNamespace(name="SUCCESS")
    primary = SimpleNamespace(
        status=status,
        message="ok",
        data={"k": "v"},
        error_code="E123",
        retry_after=30,
    )

    out = orch.serialize_primary(primary)

    assert out["status"].name == "SUCCESS"
    assert out["message"] == "ok"
    assert out["data"] == {"k": "v"}
    assert out["error_code"] == "E123"
    assert out["retry_after"] == 30


@pytest.mark.unit
def test_serialize_primary_missing_attrs_returns_none_or_empty():
    # Primary missing optional attributes should not raise
    primary = SimpleNamespace()
    out = orch.serialize_primary(primary)

    assert out["status"] is None
    assert out["message"] == ""
    assert out["data"] is None
    assert out["error_code"] is None
    assert out["retry_after"] is None


@pytest.mark.unit
def test_format_orchestration_response_success_and_propagation():
    primary = SimpleNamespace(
        status=SimpleNamespace(name="SUCCESS"), message="ok", data={"id": "g1"}
    )

    # provider1 succeeded, provider2 failed with retry metadata
    p1 = SimpleNamespace(status=SimpleNamespace(name="SUCCESS"), message="ok")
    p2 = SimpleNamespace(
        status=SimpleNamespace(name="TRANSIENT_ERROR"),
        message="down",
        error_code="E_NET",
        retry_after=10,
    )

    resp = orch.format_orchestration_response(
        primary=primary,
        propagation={"aws": p1, "gcp": p2},
        partial_failures=True,
        correlation_id="corr-1",
        action="add_member",
        group_id="developers",
        member_email="user@example.com",
    )

    assert resp["success"] is True
    assert resp["correlation_id"] == "corr-1"
    assert resp["action"] == "add_member"
    assert resp["primary"]["data"] == {"id": "g1"}
    assert "aws" in resp["propagation"] and "gcp" in resp["propagation"]
    # provider with retry should expose retry_after and error_code
    assert resp["propagation"]["gcp"]["error_code"] == "E_NET"
    assert resp["propagation"]["gcp"]["retry_after"] == 10
    assert resp["group_id"] == "developers"
    assert resp["member_email"] == "user@example.com"
    # timestamp is present and isoformat-like
    assert isinstance(resp["timestamp"], str)
    datetime.fromisoformat(resp["timestamp"].replace("Z", "+00:00"))


@pytest.mark.unit
def test_format_orchestration_response_primary_missing_status_sets_success_false():
    # primary without status or with status that causes getattr(...).name access to fail
    primary = SimpleNamespace(message="no status")
    resp = orch.format_orchestration_response(
        primary=primary, propagation={}, partial_failures=False, correlation_id="c2"
    )
    assert resp["success"] is False
    assert resp["primary"]["message"] == "no status"


@pytest.mark.unit
def test_format_read_response_includes_primary_and_metadata():
    primary = SimpleNamespace(
        status=SimpleNamespace(name="SUCCESS"), message="ok", data={"count": 2}
    )
    resp = orch.format_read_response(
        primary=primary, action="read", group_id="g1", member_email="u@x.com"
    )

    assert resp["success"] is True
    assert resp["action"] == "read"
    assert resp["primary"]["data"]["count"] == 2
    assert resp["group_id"] == "g1"
    assert resp["member_email"] == "u@x.com"


@pytest.mark.unit
def test_extract_orchestration_response_for_slack_when_failure():
    orch_resp = {"success": False, "primary": {"message": "oops"}}
    msg = orch.extract_orchestration_response_for_slack(orch_resp)
    assert msg.startswith("❌")
    assert "oops" in msg


@pytest.mark.unit
def test_extract_orchestration_response_for_slack_partial_failures_and_action_emoji():
    orch_resp = {
        "success": True,
        "action": "add_member",
        "member_email": "u@x.com",
        "group_id": "g1",
        "partial_failures": True,
        "propagation": {
            "aws": {"status": "SUCCESS"},
            "gcp": {"status": "TRANSIENT_ERROR"},
        },
    }

    msg = orch.extract_orchestration_response_for_slack(orch_resp)
    assert msg.startswith("➕")
    assert "Sync pending for" in msg
    assert "gcp" in msg


@pytest.mark.unit
def test_extract_orchestration_response_for_api_maps_status_code():
    orch_resp = {"success": True}
    out, status = orch.extract_orchestration_response_for_api(
        orch_resp, status_code=201
    )
    assert status == 201

    orch_resp_false = {"success": False}
    out2, status2 = orch.extract_orchestration_response_for_api(
        orch_resp_false, status_code=200
    )
    assert status2 == 500
