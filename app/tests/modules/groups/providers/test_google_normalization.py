import pytest

from modules.groups.providers.google_workspace import GoogleWorkspaceProvider
from types import SimpleNamespace
from modules.groups.errors import IntegrationError
from integrations.google_workspace import google_directory_next as google_directory
from integrations.google_workspace.schemas import Group as GoogleGroup


def test_map_google_member_to_normalized_basic():
    p = GoogleWorkspaceProvider()
    raw_member = {
        "id": "m1",
        "email": "user@example.com",
        "role": "MEMBER",
        "name": {"givenName": "Alice", "familyName": "Smith"},
    }

    res = p._map_google_member_to_normalized(raw_member)
    assert isinstance(res, dict)
    assert res["email"] == "user@example.com"
    assert res["id"] == "m1"
    assert res["role"] == "MEMBER"
    assert res["first_name"] == "Alice"
    assert res["family_name"] == "Smith"
    assert res["raw"] == raw_member


def test_map_google_group_to_normalized_with_members():
    p = GoogleWorkspaceProvider()
    raw_group = {
        "id": "g1",
        "email": "group@example.com",
        "name": "My Group",
        "description": "A test group",
        "members": [
            {
                "id": "m1",
                "email": "user1@example.com",
                "role": "MEMBER",
                "name": {"givenName": "Bob", "familyName": "Jones"},
            },
            {
                "id": "m2",
                "email": "user2@example.com",
                "role": "MANAGER",
                "name": {"givenName": "Carol", "familyName": "Lee"},
            },
        ],
    }

    res = p._map_google_group_to_normalized(raw_group)
    assert isinstance(res, dict)
    assert res["id"] == "g1"
    assert res["name"] == "My Group"
    assert res["description"] == "A test group"
    assert res["provider"] == "google"
    assert isinstance(res["members"], list)
    assert len(res["members"]) == 2
    assert res["members"][0]["email"] == "user1@example.com"
    assert res["members"][1]["role"] == "MANAGER"


def test_map_google_member_to_normalized_invalid_payload():
    p = GoogleWorkspaceProvider()
    # Non-dict payload should trigger validation -> IntegrationError
    with pytest.raises(IntegrationError):
        p._map_google_member_to_normalized(123)


def test_map_google_group_to_normalized_invalid_payload():
    p = GoogleWorkspaceProvider()
    with pytest.raises(IntegrationError):
        p._map_google_group_to_normalized(None)


def test_add_member_success_and_failure(monkeypatch):
    p = GoogleWorkspaceProvider()

    # success case: insert_member returns successful IntegrationResponse-like object
    fake_member = {"id": "m10", "email": "new@example.com", "role": "MEMBER"}
    monkeypatch.setattr(
        google_directory,
        "insert_member",
        lambda group_key, member_key: SimpleNamespace(success=True, data=fake_member),
    )
    res = p.add_member("g1", "new@example.com", "reason")
    assert isinstance(res, dict)
    assert res.get("email") == "new@example.com"

    # failure case: insert_member returns non-success -> IntegrationError
    monkeypatch.setattr(
        google_directory,
        "insert_member",
        lambda group_key, member_key: SimpleNamespace(success=False, data=None),
    )
    with pytest.raises(IntegrationError):
        p.add_member("g1", "new@example.com", "reason")


def test_remove_member_success(monkeypatch):
    p = GoogleWorkspaceProvider()

    monkeypatch.setattr(
        google_directory,
        "delete_member",
        lambda group_key, member_key: SimpleNamespace(success=True, data=None),
    )
    res = p.remove_member("g1", "m1", "reason")
    assert res == {"status": "removed"}


def test_direct_members_count_coercion():
    # Pydantic coercion: numeric string should become int
    raw_group = {"id": "g42", "directMembersCount": "42"}
    g = GoogleGroup.model_validate(raw_group)
    assert isinstance(g.directMembersCount, int)
    assert g.directMembersCount == 42

    # provider mapping should still succeed
    p = GoogleWorkspaceProvider()
    mapped = p._map_google_group_to_normalized(raw_group)
    assert isinstance(mapped, dict)


def test_group_with_member_with_user_enrichment():
    p = GoogleWorkspaceProvider()
    raw_group = {
        "id": "g2",
        "email": "group2@example.com",
        "members": [
            {
                "id": "m1",
                "email": "u1@example.com",
                "role": "MEMBER",
                "user": {
                    "id": "u1",
                    "primaryEmail": "u1@example.com",
                    "name": {"givenName": "U", "familyName": "One"},
                },
            }
        ],
    }
    mapped = p._map_google_group_to_normalized(raw_group)
    assert isinstance(mapped, dict)
    assert "members" in mapped
    assert len(mapped["members"]) == 1
    # The normalized member raw should include the nested user object
    assert mapped["members"][0]["raw"].get("user") is not None


def test_get_group_members_handles_unexpected_shapes(monkeypatch):
    p = GoogleWorkspaceProvider()
    # list_members returns mixed types: non-dict entries should be ignored
    monkeypatch.setattr(
        google_directory,
        "list_members",
        lambda group_key, **kwargs: SimpleNamespace(
            success=True, data=["x", {"id": "m1", "email": "u@example.com"}]
        ),
    )
    members = p.get_group_members("g1")
    assert isinstance(members, list)
    assert len(members) == 1
    assert members[0]["email"] == "u@example.com"


def test_validate_permissions_failure_modes(monkeypatch):
    p = GoogleWorkspaceProvider()

    # Case: list_members returns success=False -> IntegrationError
    monkeypatch.setattr(
        google_directory,
        "list_members",
        lambda group_key, **kwargs: SimpleNamespace(success=False, data=None),
    )
    with pytest.raises(IntegrationError):
        p.validate_permissions("admin@example.com", "g1", "action")

    # Case: list_members returns mixed shapes -> handled gracefully and returns False
    monkeypatch.setattr(
        google_directory,
        "list_members",
        lambda group_key, **kwargs: SimpleNamespace(
            success=True, data=["x", {"id": "m2", "email": "bob@example.com"}]
        ),
    )
    assert p.validate_permissions("alice@example.com", "g1", "action") is False
