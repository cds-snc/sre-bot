from modules.groups import service, orchestration, mappings
from modules.groups import schemas


def test_add_member_maps_non_primary_group(monkeypatch):
    # Simulate primary provider being 'google' and caller passing 'aws' group id
    monkeypatch.setattr(
        "modules.groups.providers.get_primary_provider_name",
        lambda: "google",
    )

    # mapping should be called to convert aws->google formatted id
    def fake_map(from_provider, from_group_id, to_provider, **k):
        assert from_provider == "aws"
        assert to_provider == "google"
        assert from_group_id == "aws-group-123"
        return "google-aws-group-123"

    monkeypatch.setattr(mappings, "map_provider_group_id", fake_map)

    captured = {}

    def fake_orch(primary_group_id, member_email, justification, provider_hint=None):
        captured["primary_group_id"] = primary_group_id
        return {
            "success": True,
            "group_id": primary_group_id,
            "member_email": member_email,
            "timestamp": "2025-01-01T00:00:00Z",
        }

    monkeypatch.setattr(orchestration, "add_member_to_group", fake_orch)

    req = schemas.AddMemberRequest(
        group_id="aws-group-123",
        member_email="u@example.com",
        provider=schemas.ProviderType.AWS,
    )

    res = service.add_member(req)

    assert res.success is True
    assert captured["primary_group_id"] == "google-aws-group-123"


def test_remove_member_maps_non_primary_group(monkeypatch):
    monkeypatch.setattr(
        "modules.groups.providers.get_primary_provider_name",
        lambda: "google",
    )

    def fake_map(from_provider, from_group_id, to_provider, **k):
        assert from_provider == "aws"
        assert to_provider == "google"
        assert from_group_id == "aws-group-456"
        return "google-aws-group-456"

    monkeypatch.setattr(mappings, "map_provider_group_id", fake_map)

    captured = {}

    def fake_orch(primary_group_id, member_email, justification, provider_hint=None):
        captured["primary_group_id"] = primary_group_id
        return {
            "success": True,
            "group_id": primary_group_id,
            "member_email": member_email,
            "timestamp": "2025-01-01T00:00:00Z",
        }

    monkeypatch.setattr(orchestration, "remove_member_from_group", fake_orch)

    req = schemas.RemoveMemberRequest(
        group_id="aws-group-456",
        member_email="v@example.com",
        provider=schemas.ProviderType.AWS,
    )

    res = service.remove_member(req)

    assert res.success is True
    assert captured["primary_group_id"] == "google-aws-group-456"
