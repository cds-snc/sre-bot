from fastapi import FastAPI
from fastapi.testclient import TestClient
from datetime import datetime

from modules.groups import controllers, service, schemas


def create_app():
    app = FastAPI()
    app.include_router(controllers.router)
    return app


def test_add_member_endpoint(monkeypatch):
    app = create_app()
    client = TestClient(app)

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

    payload = {
        "group_id": "g1",
        "member_email": "u@example.com",
        "provider": "google",
    }

    resp = client.post("/api/v1/groups/add", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["action"] == "add_member"


def test_remove_member_endpoint(monkeypatch):
    app = create_app()
    client = TestClient(app)

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

    payload = {
        "group_id": "g2",
        "member_email": "v@example.com",
        "provider": "google",
    }

    resp = client.post("/api/v1/groups/remove", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["action"] == "remove_member"


def test_list_groups_endpoint(monkeypatch):
    app = create_app()
    client = TestClient(app)

    # Return a proper NormalizedGroup dataclass so serialization succeeds
    group_payload = {"id": "g1", "name": "Group One", "description": "", "members": []}
    from modules.groups import models

    monkeypatch.setattr(
        service,
        "list_groups",
        lambda req: [models.group_from_dict(group_payload, "google")],
    )

    resp = client.get("/api/v1/groups/?user_email=test@example.com")
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)
    assert body[0]["id"] == "g1"
