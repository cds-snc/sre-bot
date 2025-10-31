from modules.groups import event_system, service, schemas
from modules.groups.providers.base import OperationResult
from modules.groups.models import group_from_dict


class SmokeProvider:
    def get_user_managed_groups(self, user_email):
        return [{"id": "g-smoke-1", "name": "smoke-group"}]

    def list_groups_for_user(self, user_key: str, provider_name: str, **kwargs):
        # Return NormalizedGroup instances wrapped in an OperationResult so
        # orchestration/list_groups_for_user returns dataclasses with .id
        grp = group_from_dict({"id": "g-smoke-1", "name": "smoke-group"}, provider_name)
        return OperationResult.success({"groups": [grp]})

    def validate_permissions(self, user_email, group_id, action):
        return True

    def add_member(self, group_id, member_email, justification):
        return {"member": member_email, "status": "added"}


def test_smoke_provider_and_event_dispatch(monkeypatch):
    smoke_provider = SmokeProvider()

    # Patch provider registry used by base (use valid provider key 'aws' so validation passes)
    monkeypatch.setattr(
        "modules.groups.providers.get_active_providers",
        lambda provider_type=None: {"aws": smoke_provider},
    )

    # Patch get_primary_provider so orchestration will accept our smoke provider
    monkeypatch.setattr(
        "modules.groups.orchestration.get_primary_provider", lambda: smoke_provider
    )
    monkeypatch.setattr(
        "modules.groups.orchestration.get_primary_provider_name", lambda: "aws"
    )

    # Verify service.list_groups returns provider groups
    list_req = schemas.ListGroupsRequest(user_email="user@example.com")
    list_res = service.list_groups(list_req)
    # list_res is a list of NormalizedGroup dataclasses (from provider)
    assert isinstance(list_res, list)
    # At least one provider mapping should produce the expected group id when
    # converted to canonical dicts by callers.
    assert any(g.id == "g-smoke-1" for g in list_res)

    # Register a temporary event handler to capture add events
    captured = []

    @event_system.register_event_handler("group.member.added")
    def _capture(payload):
        captured.append(payload)

    # Call add member API which should dispatch the event
    payload = {
        "group_id": "arn:aws:iam::123456789012:group/smoke-group",
        "member_email": "new@example.com",
        "requestor_email": "admin@example.com",
        "provider_type": "aws",
        "justification": "smoke test",
    }

    add_req = schemas.AddMemberRequest(
        group_id=payload["group_id"],
        member_email=payload["member_email"],
        provider=schemas.ProviderType(payload["provider_type"]),
        justification=payload.get("justification"),
        requestor=payload.get("requestor_email"),
    )
    add_res = service.add_member(add_req)
    assert hasattr(add_res, "success")
    # Ensure our handler received the event
    assert len(captured) >= 1
    assert captured[0]["member_email"] == "new@example.com"
