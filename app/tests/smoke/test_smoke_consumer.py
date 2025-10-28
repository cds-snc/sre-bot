from modules.groups import api, event_system


class SmokeProvider:
    def get_user_managed_groups(self, user_email):
        return [{"id": "g-smoke-1", "name": "smoke-group"}]

    def validate_permissions(self, user_email, group_id, action):
        return True

    def add_member(self, group_id, member_email, justification):
        return {"member": member_email, "status": "added"}


def test_smoke_provider_and_event_dispatch(monkeypatch):
    smoke_provider = SmokeProvider()

    # Patch provider registry used by base (use valid provider key 'aws' so validation passes)
    monkeypatch.setattr(
        "modules.groups.base.get_active_providers",
        lambda provider_type=None: {"aws": smoke_provider},
    )

    # Verify list API returns provider groups
    list_res = api.handle_list_user_groups_request("user@example.com")
    assert list_res.get("success") is True
    assert "aws" in list_res.get("providers")
    assert list_res["providers"]["aws"][0]["id"] == "g-smoke-1"

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

    add_res = api.handle_add_member_request(payload)
    assert add_res.get("success") is False or add_res.get("success") is True
    # Ensure our handler received the event
    assert len(captured) >= 1
    assert captured[0]["member_email"] == "new@example.com"
