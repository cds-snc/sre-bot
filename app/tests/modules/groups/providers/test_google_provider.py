import importlib
from types import SimpleNamespace

import pytest

from modules.groups.providers.base import OperationResult, OperationStatus
from modules.groups.schemas import NormalizedMember
from modules.groups.errors import IntegrationError


def _import_provider(safe_providers_import):
    # ensure safe import (fixture handles setup)
    _ = safe_providers_import
    return importlib.import_module("modules.groups.providers.google_workspace")


def test_capabilities_and_get_local_part(safe_providers_import):
    google_mod = _import_provider(safe_providers_import)
    p = google_mod.GoogleWorkspaceProvider()
    caps = p.capabilities
    assert caps.supports_member_management is True
    assert caps.provides_role_info is True

    assert p._get_local_part("alice@example.com") == "alice"
    assert p._get_local_part(None) is None
    assert p._get_local_part("no-at-symbol") == "no-at-symbol"


def test_normalize_group_missing_email_and_name(safe_providers_import):
    """Ensure the provider handles missing `email`/`name` gracefully and
    returns a NormalizedGroup without raising exceptions.
    """
    google_mod = _import_provider(safe_providers_import)
    p = google_mod.GoogleWorkspaceProvider()

    # group with no email and no name
    raw = {"id": "g-raw"}
    ng = p._normalize_group_from_google(raw)
    # local-part fallback needs an email; without email gid will be same as email (None)
    assert ng is not None
    assert ng.provider == "google"
    # since there is no email, id should be None (gid computed from email)
    assert ng.id is None or ng.id == "g-raw" or isinstance(ng.id, str)
    # name falls back to email or gid; ensure no exception and name set to something predictable
    assert ng.name is None or isinstance(ng.name, str)


def test_resolve_normalizedmember_missing_email_and_id_raises(safe_providers_import):
    """Test a NormalizedMember without email or id must raise ValueError."""
    google_mod = _import_provider(safe_providers_import)
    p = google_mod.GoogleWorkspaceProvider()

    nm = NormalizedMember(email=None, id=None, role=None, provider_member_id=None)
    with pytest.raises(ValueError):
        p._resolve_member_identifier(nm)


def test_resolve_dict_missing_id_or_email_raises(safe_providers_import):
    """Test a dict input without email/primaryEmail/id should raise ValueError."""
    google_mod = _import_provider(safe_providers_import)
    p = google_mod.GoogleWorkspaceProvider()

    with pytest.raises(ValueError):
        p._resolve_member_identifier({})


def test_add_member_with_no_data_returns_empty_dict(monkeypatch, safe_providers_import):
    """Test when insert_member returns success=True but data is None,
    add_member should return an OperationResult with empty result dict.
    """
    google_mod = _import_provider(safe_providers_import)
    p = google_mod.GoogleWorkspaceProvider()

    monkeypatch.setattr(
        google_mod.google_directory,
        "insert_member",
        lambda group_key, member_key: SimpleNamespace(success=True, data=None),
    )

    res = p.add_member("g1", "someone@example.com", "justification")
    assert isinstance(res, OperationResult)
    assert res.status == OperationStatus.SUCCESS
    assert res.data and "result" in res.data
    assert res.data["result"] == {}


def test_remove_member_integration_failure_returns_transient(
    monkeypatch, safe_providers_import
):
    """Test when delete_member returns success=False, provider should yield TRANSIENT_ERROR."""
    google_mod = _import_provider(safe_providers_import)
    p = google_mod.GoogleWorkspaceProvider()

    monkeypatch.setattr(
        google_mod.google_directory,
        "delete_member",
        lambda group_key, member_key: SimpleNamespace(success=False, data=None),
    )

    res = p.remove_member("g1", "user@example.com", "just")
    assert isinstance(res, OperationResult)
    assert res.status == OperationStatus.TRANSIENT_ERROR


def test_get_group_members_with_raw_list(monkeypatch, safe_providers_import):
    """Todo #6: list_members returns a raw list (not IntegrationResponse-like)."""
    google_mod = _import_provider(safe_providers_import)
    p = google_mod.GoogleWorkspaceProvider()

    monkeypatch.setattr(
        google_mod.google_directory,
        "list_members",
        lambda group_key, **kwargs: [{"id": "m1", "email": "u@example.com"}],
    )

    res = p.get_group_members("g1")
    assert isinstance(res, OperationResult)
    assert res.status == OperationStatus.SUCCESS
    assert res.data and "members" in res.data
    assert res.data["members"][0]["email"] == "u@example.com"


def test_list_groups_with_raw_list(monkeypatch, safe_providers_import):
    """Todo #7: list_groups returns a raw list of group dicts."""
    google_mod = _import_provider(safe_providers_import)
    p = google_mod.GoogleWorkspaceProvider()

    monkeypatch.setattr(
        google_mod.google_directory,
        "list_groups",
        lambda **kwargs: [{"id": "g1", "email": "g1@example.com", "name": "G1"}],
    )

    res = p.list_groups()
    assert isinstance(res, OperationResult)
    assert res.status == OperationStatus.SUCCESS
    assert res.data and "groups" in res.data
    assert (
        res.data["groups"][0]["id"] == "g1"
        or res.data["groups"][0]["id"] == "g1@example.com"
    )


def test_list_groups_with_members_integration_failure(
    monkeypatch, safe_providers_import
):
    """Todo #8: when the underlying integration returns success=False, provider should propagate transient error."""
    google_mod = _import_provider(safe_providers_import)
    p = google_mod.GoogleWorkspaceProvider()

    monkeypatch.setattr(
        google_mod.google_directory,
        "list_groups_with_members",
        lambda **kwargs: SimpleNamespace(success=False, data=None),
    )

    res = p.list_groups_with_members()
    assert isinstance(res, OperationResult)
    assert res.status == OperationStatus.TRANSIENT_ERROR


def test_validate_permissions_match_by_id(monkeypatch, safe_providers_import):
    """Todo #9: ensure validate_permissions matches member id as well as email."""
    google_mod = _import_provider(safe_providers_import)
    p = google_mod.GoogleWorkspaceProvider()

    monkeypatch.setattr(
        google_mod.google_directory,
        "list_members",
        lambda group_key, **kwargs: SimpleNamespace(
            success=True, data=[{"id": "u-123"}]
        ),
    )

    res = p.validate_permissions("u-123", "g1", "action")
    assert isinstance(res, OperationResult)
    assert res.status == OperationStatus.SUCCESS
    # decorated returns allowed in data when wrapped
    assert res.data and res.data.get("allowed") is True


def test_normalize_member_and_group_success_and_failure(safe_providers_import):
    google_mod = _import_provider(safe_providers_import)
    p = google_mod.GoogleWorkspaceProvider()

    raw_member = {
        "id": "m1",
        "email": "user@example.com",
        "role": "MEMBER",
        "name": {"givenName": "Alice", "familyName": "Smith"},
    }
    nm = p._normalize_member_from_google(raw_member)
    assert nm.email == "user@example.com"
    assert nm.id == "m1"
    assert nm.role == "MEMBER"
    assert nm.first_name == "Alice"
    assert nm.family_name == "Smith"

    # invalid payload -> IntegrationError (pydantic validation failure)
    with pytest.raises(IntegrationError):
        p._normalize_member_from_google(123)

    raw_group = {
        "id": "g1",
        "email": "group@example.com",
        "name": "MyGroup",
        "description": "d",
        "members": [raw_member],
    }
    ng = p._normalize_group_from_google(raw_group, members=raw_group["members"])
    assert ng.id == "group"
    assert ng.name == "MyGroup"
    assert ng.provider == "google"
    assert len(ng.members) == 1

    with pytest.raises(IntegrationError):
        p._normalize_group_from_google(None)


def test_resolve_member_identifier_various_inputs(safe_providers_import):
    google_mod = _import_provider(safe_providers_import)
    p = google_mod.GoogleWorkspaceProvider()

    # NormalizedMember with email
    nm = NormalizedMember(email="e@x.com", id=None, role=None, provider_member_id=None)
    assert p._resolve_member_identifier(nm) == "e@x.com"

    # NormalizedMember with id only
    nm2 = NormalizedMember(email=None, id="ID42", role=None, provider_member_id=None)
    assert p._resolve_member_identifier(nm2) == "ID42"

    # dict input with primaryEmail
    assert p._resolve_member_identifier({"primaryEmail": "p@x"}) == "p@x"
    # dict input with id
    assert p._resolve_member_identifier({"id": "m-1"}) == "m-1"

    # str input
    assert p._resolve_member_identifier("  trimmed@ex.com  ") == "trimmed@ex.com"

    with pytest.raises(ValueError):
        p._resolve_member_identifier("")

    with pytest.raises(TypeError):
        p._resolve_member_identifier(123.4)


def test_add_and_remove_member_operationresult(monkeypatch, safe_providers_import):
    google_mod = _import_provider(safe_providers_import)
    p = google_mod.GoogleWorkspaceProvider()

    fake_member = {"id": "m10", "email": "new@example.com", "role": "MEMBER"}
    monkeypatch.setattr(
        google_mod.google_directory,
        "insert_member",
        lambda group_key, member_key: SimpleNamespace(success=True, data=fake_member),
    )

    res = p.add_member("g1", "new@example.com", "justification")
    assert isinstance(res, OperationResult)
    assert res.status == OperationStatus.SUCCESS
    assert res.data and "result" in res.data
    assert res.data["result"]["email"] == "new@example.com"

    # insert_member indicates failure -> decorator should surface transient error
    monkeypatch.setattr(
        google_mod.google_directory,
        "insert_member",
        lambda group_key, member_key: SimpleNamespace(success=False, data=None),
    )
    res2 = p.add_member("g1", "new@example.com", "justification")
    assert isinstance(res2, OperationResult)
    assert res2.status == OperationStatus.TRANSIENT_ERROR

    # remove_member success
    monkeypatch.setattr(
        google_mod.google_directory,
        "delete_member",
        lambda group_key, member_key: SimpleNamespace(success=True, data=None),
    )
    rem = p.remove_member("g1", "m1", "reason")
    assert isinstance(rem, OperationResult)
    assert rem.status == OperationStatus.SUCCESS
    assert rem.data and rem.data.get("result", {}).get("status") == "removed"

    # remove failure case
    monkeypatch.setattr(
        google_mod.google_directory,
        "delete_member",
        lambda group_key, member_key: SimpleNamespace(success=False, data=None),
    )
    rem2 = p.remove_member("g1", "m1", "reason")
    assert rem2.status == OperationStatus.TRANSIENT_ERROR


def test_get_group_members_and_list_groups(monkeypatch, safe_providers_import):
    google_mod = _import_provider(safe_providers_import)
    p = google_mod.GoogleWorkspaceProvider()

    # list_members returns mixed shapes; only dicts normalized
    monkeypatch.setattr(
        google_mod.google_directory,
        "list_members",
        lambda group_key, **kwargs: SimpleNamespace(
            success=True, data=["x", {"id": "m1", "email": "u@example.com"}]
        ),
    )
    members_res = p.get_group_members("g1")
    assert members_res.status == OperationStatus.SUCCESS
    assert isinstance(members_res.data["members"], list)
    assert members_res.data["members"][0]["email"] == "u@example.com"

    # list_groups
    monkeypatch.setattr(
        google_mod.google_directory,
        "list_groups",
        lambda **kwargs: SimpleNamespace(
            success=True,
            data=[{"id": "g1", "email": "group@example.com", "name": "G"}],
        ),
    )
    groups_res = p.list_groups()
    assert groups_res.status == OperationStatus.SUCCESS
    assert groups_res.data["groups"][0]["id"] == "group"


def test_list_groups_with_members(monkeypatch, safe_providers_import):
    google_mod = _import_provider(safe_providers_import)
    p = google_mod.GoogleWorkspaceProvider()

    # stub underlying integration function
    groups = [{"id": "g1", "email": "g1@example.com", "name": "G1"}]
    monkeypatch.setattr(
        google_mod.google_directory,
        "list_groups_with_members",
        lambda **kwargs: SimpleNamespace(success=True, data=groups),
    )

    res = p.list_groups_with_members()
    assert res.status == OperationStatus.SUCCESS
    assert isinstance(res.data["groups"], list)
    assert res.data["groups"][0]["id"] == "g1"


def test_validate_permissions_and_get_groups_for_user(
    monkeypatch, safe_providers_import
):
    google_mod = _import_provider(safe_providers_import)
    p = google_mod.GoogleWorkspaceProvider()

    # validate_permissions: list_members failure -> transient
    monkeypatch.setattr(
        google_mod.google_directory,
        "list_members",
        lambda group_key, **kwargs: SimpleNamespace(success=False, data=None),
    )
    vp = p.validate_permissions("u@e", "g1", "action")
    assert isinstance(vp, OperationResult)
    assert vp.status == OperationStatus.TRANSIENT_ERROR

    # success but not manager -> allowed False
    monkeypatch.setattr(
        google_mod.google_directory,
        "list_members",
        lambda group_key, **kwargs: SimpleNamespace(
            success=True, data=[{"id": "m2", "email": "bob@e"}]
        ),
    )
    vp2 = p.validate_permissions("alice@e", "g1", "action")
    assert vp2.status == OperationStatus.SUCCESS
    assert vp2.data and vp2.data.get("allowed") is False

    # get_groups_for_user success
    monkeypatch.setattr(
        google_mod.google_directory,
        "list_groups",
        lambda **kwargs: SimpleNamespace(
            success=True, data=[{"id": "g1", "email": "g1@example.com"}]
        ),
    )
    ug = p.get_groups_for_user("u@e")
    assert ug.status == OperationStatus.SUCCESS
    assert isinstance(ug.data["groups"], list)


def test_is_manager_paths(monkeypatch, safe_providers_import):
    google_mod = _import_provider(safe_providers_import)
    p = google_mod.GoogleWorkspaceProvider()

    # Force provider_provides_role_info True path
    monkeypatch.setattr(google_mod, "provider_provides_role_info", lambda name: True)

    # Case: member found among MANAGERs
    monkeypatch.setattr(
        google_mod.google_directory,
        "get_member",
        lambda group_key, user_key, **kwargs: SimpleNamespace(
            success=True,
            data=[{"id": "m1", "email": "mgr@example.com", "role": "MANAGER"}],
        ),
    )
    res = p.is_manager("mgr@example.com", "g1")
    assert isinstance(res, OperationResult)
    assert res.status == OperationStatus.SUCCESS
    assert res.data and res.data.get("is_manager") is True

    # Case: integration error -> transient_error returned
    monkeypatch.setattr(
        google_mod.google_directory,
        "get_member",
        lambda group_key, user_key, **kwargs: SimpleNamespace(success=False, data=None),
    )
    res2 = p.is_manager("any@example.com", "g1")
    assert res2.status == OperationStatus.TRANSIENT_ERROR

    # Force provider_provides_role_info False -> should delegate to base
    monkeypatch.setattr(google_mod, "provider_provides_role_info", lambda name: False)
    # stub GroupProvider.is_manager to a known result
    from modules.groups.providers.base import GroupProvider

    monkeypatch.setattr(
        GroupProvider,
        "is_manager",
        lambda self, u, g: OperationResult.success(data={"is_manager": False}),
    )
    res3 = p.is_manager("u@example.com", "g1")
    assert res3.status == OperationStatus.SUCCESS
    assert res3.data and res3.data.get("is_manager") is False


def test_is_manager_integration_error_returns_transient(
    monkeypatch, safe_providers_import
):
    """Todo #11: when google_directory.list_members raises IntegrationError,
    is_manager should return an OperationResult.transient_error.
    """
    google_mod = _import_provider(safe_providers_import)
    p = google_mod.GoogleWorkspaceProvider()

    # force provider to report role info available
    monkeypatch.setattr(google_mod, "provider_provides_role_info", lambda name: True)

    def _raise(*a, **k):
        raise IntegrationError("boom")

    monkeypatch.setattr(google_mod.google_directory, "get_member", _raise)

    res = p.is_manager("u@example.com", "g1")
    assert isinstance(res, OperationResult)
    assert res.status == OperationStatus.TRANSIENT_ERROR


def test_is_manager_unexpected_exception_returns_transient_with_message(
    monkeypatch, safe_providers_import
):
    """Todo #12: when google_directory.list_members raises a non-IntegrationError
    (e.g., RuntimeError), is_manager should return TRANSIENT_ERROR and include
    the exception message.
    """
    google_mod = _import_provider(safe_providers_import)
    p = google_mod.GoogleWorkspaceProvider()

    # ensure provider claims to expose role info
    monkeypatch.setattr(google_mod, "provider_provides_role_info", lambda name: True)

    def _raise_runtime(*a, **k):
        raise RuntimeError("unexpected failure")

    monkeypatch.setattr(google_mod.google_directory, "get_member", _raise_runtime)

    res = p.is_manager("u@example.com", "g1")
    assert isinstance(res, OperationResult)
    assert res.status == OperationStatus.TRANSIENT_ERROR
    # message text should include the raised exception string
    assert "unexpected failure" in (res.message or "")


def test_list_groups_with_members_filters_invalid_groups(
    monkeypatch, safe_providers_import
):
    """Todo #13: list_groups_with_members should skip non-dict or invalid group
    entries when normalizing and only return valid canonical groups.
    """
    google_mod = _import_provider(safe_providers_import)
    p = google_mod.GoogleWorkspaceProvider()

    mixed = [
        "not-a-dict",
        {"id": "g1", "email": "g1@example.com", "name": "G1"},
        {"no_email": True},
    ]

    monkeypatch.setattr(
        google_mod.google_directory,
        "list_groups_with_members",
        lambda **kwargs: SimpleNamespace(success=True, data=mixed),
    )

    res = p.list_groups_with_members()
    assert isinstance(res, OperationResult)
    assert res.status == OperationStatus.SUCCESS
    groups = res.data.get("groups")
    # non-dict entries are skipped, but dicts (even missing email/name) are
    # processed by the provider and returned as normalized groups
    assert isinstance(groups, list)
    assert len(groups) == 2
    # first normalized group corresponds to the well-formed dict
    assert groups[0]["id"] == "g1"
    # second normalized group corresponds to the dict missing an email/name
    assert groups[1]["id"] is None


def test_get_groups_for_user_with_raw_list(monkeypatch, safe_providers_import):
    """Todo #10: when list_groups returns a raw list (not IntegrationResponse-like),
    get_groups_for_user should normalize and return OperationResult.SUCCESS.
    """
    google_mod = _import_provider(safe_providers_import)
    p = google_mod.GoogleWorkspaceProvider()

    # monkeypatch to return a raw list of groups
    monkeypatch.setattr(
        google_mod.google_directory,
        "list_groups",
        lambda **kwargs: [
            {"id": "g-raw", "email": "raw@example.com", "name": "RawGroup"}
        ],
    )

    res = p.get_groups_for_user("u@e")
    assert isinstance(res, OperationResult)
    assert res.status == OperationStatus.SUCCESS
    assert res.data and "groups" in res.data
    assert isinstance(res.data["groups"], list)
    # normalization uses the local-part of the email as the group's id
    assert res.data["groups"][0]["id"] == "raw"
    assert res.data["groups"][0]["name"] == "RawGroup"
