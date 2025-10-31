from datetime import datetime

from modules.groups import commands, service, schemas


def test_handle_add_command_calls_service(monkeypatch):
    # Prepare inputs
    body = {"user": {"email": "req@example.com"}}
    args = ["new@example.com", "group-1", "google", "Because"]

    captured = {"text": None}

    def respond(text):
        captured["text"] = text

    # Mock AddMemberRequest -> service.add_member
    def fake_add(req):
        return schemas.ActionResponse(
            success=True,
            action=schemas.OperationType.ADD_MEMBER,
            group_id=req.group_id,
            member_email=req.member_email,
            provider=req.provider,
            timestamp=datetime.utcnow(),
        )

    monkeypatch.setattr(service, "add_member", fake_add)

    commands._handle_add_command(None, body, respond, args)

    assert captured["text"] is not None
    assert (
        "Added" in captured["text"]
        or "Added" in str(captured["text"])
        or "✅" in captured["text"]
    )


def test_handle_remove_command_calls_service(monkeypatch):
    body = {"user": {"email": "req@example.com"}}
    args = ["old@example.com", "group-2", "google", "Because"]

    captured = {"text": None}

    def respond(text):
        captured["text"] = text

    def fake_remove(req):
        return schemas.ActionResponse(
            success=True,
            action=schemas.OperationType.REMOVE_MEMBER,
            group_id=req.group_id,
            member_email=req.member_email,
            provider=req.provider,
            timestamp=datetime.utcnow(),
        )

    monkeypatch.setattr(service, "remove_member", fake_remove)

    commands._handle_remove_command(None, body, respond, args)

    assert captured["text"] is not None
    assert (
        ("Removed" in captured["text"])
        or ("✅" in captured["text"])
        or ("➖" in captured["text"])
    )
