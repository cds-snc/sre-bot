import pytest

from types import SimpleNamespace
from modules.groups.errors import IntegrationError
from integrations.google_workspace import google_directory_next as google_directory
from integrations.google_workspace.schemas import Group as GoogleGroup


def test_map_google_member_to_normalized_basic(safe_providers_import):
    _ = safe_providers_import
    import importlib

    google_mod = importlib.import_module("modules.groups.providers.google_workspace")
    p = google_mod.GoogleWorkspaceProvider()
    raw_member = {
        "id": "m1",
        "email": "user@example.com",
        "role": "MEMBER",
        "name": {"givenName": "Alice", "familyName": "Smith"},
    }

    res = p._normalize_member_from_google(raw_member, include_raw=True)
    assert isinstance(
        res, type(p._normalize_member_from_google({}))
    )  # NormalizedMember
    assert res.email == "user@example.com"
    assert res.id == "m1"
    assert res.role == "MEMBER"
    assert res.first_name == "Alice"
    assert res.family_name == "Smith"
    assert res.raw == raw_member


def test_map_google_group_to_normalized_with_members(safe_providers_import):
    _ = safe_providers_import
    import importlib

    google_mod = importlib.import_module("modules.groups.providers.google_workspace")
    p = google_mod.GoogleWorkspaceProvider()
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

    res = p._normalize_group_from_google(raw_group)
    assert isinstance(res, type(p._normalize_group_from_google({})))  # NormalizedGroup
    # Provider normalizes group id to the local-part of the email
    assert res.id == "group"
    assert res.name == "My Group"
    assert res.description == "A test group"
    assert res.provider == "google"
    assert isinstance(res.members, list)
    assert len(res.members) == 2
    assert res.members[0].email == "user1@example.com"
    assert res.members[1].role == "MANAGER"


def test_map_google_member_to_normalized_invalid_payload(safe_providers_import):
    _ = safe_providers_import
    import importlib

    google_mod = importlib.import_module("modules.groups.providers.google_workspace")
    p = google_mod.GoogleWorkspaceProvider()
    # Non-dict payload should trigger validation -> IntegrationError
    with pytest.raises(IntegrationError):
        p._normalize_member_from_google(123)


def test_map_google_group_to_normalized_invalid_payload(safe_providers_import):
    _ = safe_providers_import
    import importlib

    google_mod = importlib.import_module("modules.groups.providers.google_workspace")
    p = google_mod.GoogleWorkspaceProvider()
    with pytest.raises(IntegrationError):
        p._normalize_group_from_google(None)


def test_add_member_success_and_failure(monkeypatch, safe_providers_import):
    _ = safe_providers_import
    import importlib

    google_mod = importlib.import_module("modules.groups.providers.google_workspace")
    p = google_mod.GoogleWorkspaceProvider()

    # success case: insert_member returns successful IntegrationResponse-like object
    fake_member = {"id": "m10", "email": "new@example.com", "role": "MEMBER"}
    monkeypatch.setattr(
        google_directory,
        "insert_member",
        lambda group_key, member_key: SimpleNamespace(success=True, data=fake_member),
    )
    res = p.add_member("g1", "new@example.com")
    assert isinstance(
        res, type(p.add_member("g1", "new@example.com"))
    )  # OperationResult
    assert res.status.name == "SUCCESS"
    assert res.data["result"]["email"] == "new@example.com"

    # failure case: insert_member returns non-success -> IntegrationError
    monkeypatch.setattr(
        google_directory,
        "insert_member",
        lambda group_key, member_key: SimpleNamespace(success=False, data=None),
    )
    # opresult_wrapper converts exceptions into an OperationResult with
    # TRANSIENT_ERROR rather than letting IntegrationError propagate.
    res2 = p.add_member("g1", "new@example.com")
    assert res2.status.name == "TRANSIENT_ERROR"


def test_remove_member_success(monkeypatch, safe_providers_import):
    _ = safe_providers_import
    import importlib

    google_mod = importlib.import_module("modules.groups.providers.google_workspace")
    p = google_mod.GoogleWorkspaceProvider()

    monkeypatch.setattr(
        google_directory,
        "delete_member",
        lambda group_key, member_key: SimpleNamespace(success=True, data=None),
    )
    res = p.remove_member("g1", "m1")
    assert isinstance(res, type(p.remove_member("g1", "m1")))  # OperationResult
    assert res.status.name == "SUCCESS"
    assert res.data["result"]["status"] == "removed"


def test_direct_members_count_coercion(safe_providers_import):
    # Pydantic coercion: numeric string should become int
    raw_group = {"id": "g42", "directMembersCount": "42"}
    g = GoogleGroup.model_validate(raw_group)
    assert isinstance(g.directMembersCount, int)
    assert g.directMembersCount == 42

    # provider mapping should still succeed
    _ = safe_providers_import
    import importlib

    google_mod = importlib.import_module("modules.groups.providers.google_workspace")
    p = google_mod.GoogleWorkspaceProvider()
    mapped = p._normalize_group_from_google(raw_group, include_raw=True)
    assert isinstance(mapped, type(p._normalize_group_from_google({})))


def test_group_with_member_with_user_enrichment(safe_providers_import):
    _ = safe_providers_import
    import importlib

    google_mod = importlib.import_module("modules.groups.providers.google_workspace")
    p = google_mod.GoogleWorkspaceProvider()
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
    mapped = p._normalize_group_from_google(raw_group, include_raw=True)
    assert isinstance(mapped, type(p._normalize_group_from_google({})))
    assert hasattr(mapped, "members")
    assert len(mapped.members) == 1
    # The group's raw payload should include the nested user object for the member
    assert mapped.raw is not None
    assert (
        mapped.raw.get("members") and mapped.raw["members"][0].get("user") is not None
    )


def test_get_group_members_handles_unexpected_shapes(
    monkeypatch, safe_providers_import
):
    _ = safe_providers_import
    import importlib

    google_mod = importlib.import_module("modules.groups.providers.google_workspace")
    p = google_mod.GoogleWorkspaceProvider()
    # list_members returns mixed types: non-dict entries should be ignored
    monkeypatch.setattr(
        google_directory,
        "list_members",
        lambda group_key, **kwargs: SimpleNamespace(
            success=True, data=["x", {"id": "m1", "email": "u@example.com"}]
        ),
    )
    res = p.get_group_members("g1")
    assert isinstance(res, type(p.get_group_members("g1")))  # OperationResult
    assert res.status.name == "SUCCESS"
    members = res.data["members"]
    assert isinstance(members, list)
    assert len(members) == 1
    assert members[0]["email"] == "u@example.com"


def test_validate_permissions_failure_modes(monkeypatch, safe_providers_import):
    _ = safe_providers_import
    import importlib

    google_mod = importlib.import_module("modules.groups.providers.google_workspace")
    p = google_mod.GoogleWorkspaceProvider()

    # Case: list_members returns success=False -> IntegrationError
    monkeypatch.setattr(
        google_directory,
        "list_members",
        lambda group_key, **kwargs: SimpleNamespace(success=False, data=None),
    )
    # validate_permissions is wrapped; it returns an OperationResult on failures
    vp_res = p.validate_permissions("admin@example.com", "g1", "action")
    assert vp_res.status.name == "TRANSIENT_ERROR"

    # Case: list_members returns mixed shapes -> handled gracefully and returns False
    monkeypatch.setattr(
        google_directory,
        "list_members",
        lambda group_key, **kwargs: SimpleNamespace(
            success=True, data=["x", {"id": "m2", "email": "bob@example.com"}]
        ),
    )
    res = p.validate_permissions("alice@example.com", "g1", "action")
    assert isinstance(
        res, type(p.validate_permissions("alice@example.com", "g1", "action"))
    )
    assert res.status.name == "SUCCESS"
    assert res.data["allowed"] is False
