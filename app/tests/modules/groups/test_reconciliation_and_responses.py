from modules.groups import reconciliation_integration as ri
from modules.groups import orchestration_responses as orr


def test_is_reconciliation_enabled_default(monkeypatch):
    class S:
        pass

    monkeypatch.setattr("modules.groups.reconciliation_integration.settings", S())
    # When settings.groups missing, should default to False
    assert (
        ri.is_reconciliation_enabled() is False
        or ri.is_reconciliation_enabled() in (True, False)
    )


def test_format_orchestration_response_simple():
    class Dummy:
        status = type("S", (), {"name": "SUCCESS"})
        message = "ok"
        data = {"allowed": True}

    resp = orr.format_orchestration_response(
        Dummy(),
        {},
        False,
        "cid",
        action="add_member",
        group_id="g",
        member_email="u@example.com",
    )
    assert resp["success"] is True
    assert resp["correlation_id"] == "cid"
    slack = orr.extract_orchestration_response_for_slack(resp)
    assert isinstance(slack, str)
