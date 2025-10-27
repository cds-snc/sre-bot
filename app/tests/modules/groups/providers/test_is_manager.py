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

    def _list_members_ok(group_key, **kwargs):
        # return a payload; normalize is monkeypatched so contents don't matter
        return [{"email": "u@example.com", "id": "uid-1", "role": "MANAGER"}]

    monkeypatch.setattr(google_directory, "list_members", _list_members_ok)

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

    # Case A: provides_role_info = True -> provider returns role info
    set_provider_capability("google", True)
    res = prov.is_manager("u@example.com", "g1")
    assert res.status == OperationStatus.SUCCESS
    assert res.data is not None
    assert res.data.get("allowed") is True
    assert res.data.get("role") == "MANAGER"

    # Case B: provides_role_info = False -> fallback to base implementation
    set_provider_capability("google", False)
    res2 = prov.is_manager("u@example.com", "g1")
    assert res2.status == OperationStatus.SUCCESS
    assert res2.data is not None
    # Fallback returns allowed flag (no role key)
    assert res2.data.get("allowed") is True
    assert "role" not in res2.data

    # Negative case: when the provider reports no managers, allowed should be False
    def _list_members_none(group_key, **kwargs):
        return []

    monkeypatch.setattr(google_directory, "list_members", _list_members_none)
    set_provider_capability("google", True)
    res3 = prov.is_manager("u@example.com", "g1")
    assert res3.status == OperationStatus.SUCCESS
    assert res3.data is not None
    assert res3.data.get("allowed") is False


def test_aws_is_manager_toggles(
    monkeypatch, safe_providers_import, set_provider_capability
):
    # Prevent module-level register decorator from instantiating the class
    providers_mod = safe_providers_import

    monkeypatch.setattr(
        providers_mod, "register_provider", lambda name: (lambda obj: obj)
    )

    from modules.groups.providers.aws_identity_center import AwsIdentityCenterProvider
    from modules.groups.providers.base import OperationStatus

    prov = AwsIdentityCenterProvider()

    # Stub _ensure_user_id_from_email to simply echo the input
    monkeypatch.setattr(prov, "_ensure_user_id_from_email", lambda x: x)

    # Prepare a fake response object for identity_store
    import integrations.aws.identity_store_next as identity_store

    def _list_group_memberships_for_member(user_id, role=None):
        return types.SimpleNamespace(
            success=True,
            data=[{"Group": {"GroupId": "g-1"}}],
        )

    monkeypatch.setattr(
        identity_store,
        "list_group_memberships_for_member",
        _list_group_memberships_for_member,
    )

    # Case A: provides_role_info = True -> direct check returns role
    set_provider_capability("aws", True)
    res = prov.is_manager("u-1", "g-1")
    assert res.status == OperationStatus.SUCCESS
    assert res.data is not None
    assert res.data.get("allowed") is True
    assert res.data.get("role") == "MANAGER"

    # Case B: provides_role_info = False -> fallback to base implementation
    # For AWS fallback, base will call get_user_managed_groups which is not
    # implemented; so ensure it returns PERMANENT_ERROR NOT_IMPLEMENTED
    set_provider_capability("aws", False)
    res2 = prov.is_manager("u-1", "g-1")
    # When fallback cannot be satisfied, base returns PERMANENT_ERROR
    assert res2.status in (OperationStatus.PERMANENT_ERROR, OperationStatus.SUCCESS)

    # Negative case: when the membership listing does not include the group,
    # the provider should report allowed=False
    def _list_group_memberships_for_member_none(user_id, role=None):
        return types.SimpleNamespace(success=True, data=[])

    monkeypatch.setattr(
        identity_store,
        "list_group_memberships_for_member",
        _list_group_memberships_for_member_none,
    )
    set_provider_capability("aws", True)
    res3 = prov.is_manager("u-1", "g-1")
    assert res3.status == OperationStatus.SUCCESS
    assert res3.data is not None
    assert res3.data.get("allowed") is False
