from modules.groups import service, orchestration, event_system
from modules.groups import schemas


class DummyOp:
    def __init__(self, success=True, data=None, message="ok"):
        self.status = (
            type("S", (), {"name": "SUCCESS"})
            if success
            else type("F", (), {"name": "FAILED"})
        )
        self.data = data
        self.message = message


def test_add_member_schedules_event(monkeypatch):
    # Mock orchestration to return a dict-like orchestration response
    orch_resp = {
        "success": True,
        "group_id": "g1",
        "member_email": "u@example.com",
        "timestamp": "2025-01-01T00:00:00Z",
    }

    monkeypatch.setattr(orchestration, "add_member_to_group", lambda *a, **k: orch_resp)

    dispatched = {}

    # Make the background dispatcher call our fake synchronously by patching
    # the event_system background submit function so tests are deterministic.
    def fake_dispatch(event_type, payload):
        dispatched["event_type"] = event_type
        dispatched["payload"] = payload

    monkeypatch.setattr(event_system, "dispatch_background", fake_dispatch)

    req = schemas.AddMemberRequest(
        group_id="g1",
        member_email="u@example.com",
        provider=schemas.ProviderType.GOOGLE,
    )

    res = service.add_member(req)

    assert res.success is True
    assert res.group_id == "g1"
    # Event scheduled (fire-and-forget uses executor; we patched dispatch_event)
    # The background submission may not have run yet; ensure dispatcher was submitted by calling executor worker synchronously
    # But since we patched dispatch_event, we can inspect dispatched dict
    # Allow for eventual consistency in the test via simple check. The
    # service now emits the final canonical event name after orchestration.
    assert dispatched.get("event_type") == "group.member.added"


def test_remove_member_schedules_event(monkeypatch):
    orch_resp = {
        "success": True,
        "group_id": "g2",
        "member_email": "v@example.com",
        "timestamp": "2025-01-01T00:00:00Z",
    }

    monkeypatch.setattr(
        orchestration, "remove_member_from_group", lambda *a, **k: orch_resp
    )

    called = {}

    def fake_dispatch(event_type, payload):
        called["event"] = event_type

    monkeypatch.setattr(event_system, "dispatch_background", fake_dispatch)

    req = schemas.RemoveMemberRequest(
        group_id="g2",
        member_email="v@example.com",
        provider=schemas.ProviderType.GOOGLE,
    )

    res = service.remove_member(req)

    assert res.success is True
    assert res.group_id == "g2"
    # Service emits the canonical post-write event name now
    assert called.get("event") == "group.member.removed"


def test_bulk_operations_calls_add_and_remove(monkeypatch):
    # Mock add and remove to return success responses with valid timestamps
    from datetime import datetime

    monkeypatch.setattr(
        service,
        "add_member",
        lambda r: schemas.ActionResponse(
            success=True,
            action=schemas.OperationType.ADD_MEMBER,
            timestamp=datetime.utcnow(),
        ),
    )
    monkeypatch.setattr(
        service,
        "remove_member",
        lambda r: schemas.ActionResponse(
            success=True,
            action=schemas.OperationType.REMOVE_MEMBER,
            timestamp=datetime.utcnow(),
        ),
    )

    ops = [
        {
            "operation": "add_member",
            "payload": {
                "group_id": "g1",
                "member_email": "a@example.com",
                "provider": "google",
            },
        },
        {
            "operation": "remove_member",
            "payload": {
                "group_id": "g2",
                "member_email": "b@example.com",
                "provider": "google",
            },
        },
    ]

    req = schemas.BulkOperationsRequest(
        operations=[
            schemas.OperationItem(
                operation=schemas.OperationType.ADD_MEMBER, payload=ops[0]["payload"]
            ),
            schemas.OperationItem(
                operation=schemas.OperationType.REMOVE_MEMBER, payload=ops[1]["payload"]
            ),
        ]
    )

    res = service.bulk_operations(req)

    assert isinstance(res.results, list)
    assert len(res.results) == 2
    assert res.summary["success"] == 2
