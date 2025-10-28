import types


def test_google_is_manager_toggles(
    monkeypatch, safe_providers_import, set_provider_capability
):
    # Prevent the module-level register decorator from instantiating the class
    providers_mod = safe_providers_import

    monkeypatch.setattr(
        providers_mod, "register_provider", lambda name: (lambda obj: obj)
    )

    from modules.groups.providers.google_workspace import GoogleWorkspaceProvider
    from modules.groups.schemas import NormalizedMember
    from modules.groups.providers.base import OperationStatus

    # Prepare a concrete provider instance (GoogleWorkspaceProvider is missing
    # a concrete `list_groups` implementation in this test environment so
    # subclass and provide the minimal required method).
    from modules.groups.providers.base import OperationResult

    class ConcreteGoogle(GoogleWorkspaceProvider):
        def list_groups(self, **kwargs) -> OperationResult:
            return OperationResult.success(data={"groups": []})

    prov = ConcreteGoogle()

    # Monkeypatch the google_directory.list_members to return a simple response
    import integrations.google_workspace.google_directory_next as google_directory

    def _get_member_ok(group_key, user_key, **kwargs):
        # return a payload; normalize is monkeypatched so contents don't matter
        return {"email": "u@example.com", "id": "uid-1", "role": "MANAGER"}

    monkeypatch.setattr(google_directory, "get_member", _get_member_ok)

    # Monkeypatch normalize to avoid Pydantic validation complexities
    def _normalize(m):
        return NormalizedMember(
            email="u@example.com",
            id="uid-1",
            role="MANAGER",
            provider_member_id="uid-1",
            first_name=None,
            family_name=None,
            raw=m,
        )

    monkeypatch.setattr(prov, "_normalize_member_from_google", _normalize)

    # Case A: provides_role_info = True -> provider returns boolean is_manager
    set_provider_capability("google", True)
    res = prov.is_manager("u@example.com", "g1")
    assert res.status == OperationStatus.SUCCESS
    assert res.data is not None
    # New contract: provider returns 'is_manager' boolean (role is no longer returned)
    assert res.data.get("is_manager") is True

    # Case B: provides_role_info = False -> fallback to base implementation
    set_provider_capability("google", False)
    res2 = prov.is_manager("u@example.com", "g1")
    assert res2.status == OperationStatus.SUCCESS
    assert res2.data is not None
    # Fallback returns only the boolean is_manager (no role key)
    assert res2.data.get("is_manager") is True
    assert "role" not in res2.data

    # Negative case: when the provider reports no managers, is_manager should be False

    def _get_member_none(group_key, user_key, **kwargs):
        # Simulate no member/role info returned
        return {}

    monkeypatch.setattr(google_directory, "get_member", _get_member_none)
    set_provider_capability("google", True)
    res3 = prov.is_manager("u@example.com", "g1")
    assert res3.status == OperationStatus.SUCCESS
    assert res3.data is not None
    assert res3.data.get("is_manager") is False
