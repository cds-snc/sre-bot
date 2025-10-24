import types
import pytest

from modules.groups.providers import get_provider
from modules.groups.providers import aws_identity_center as aws_module
from modules.groups.errors import IntegrationError


def _make_resp(success: bool, data=None, error=None):
    return types.SimpleNamespace(success=success, data=data, error=error)


# helper: recursively convert dict/list to SimpleNamespace for attribute access
def _to_ns(obj):
    if isinstance(obj, dict):
        return types.SimpleNamespace(**{k: _to_ns(v) for k, v in obj.items()})
    if isinstance(obj, list):
        return [_to_ns(i) for i in obj]
    return obj


def test_get_user_managed_groups_with_get_groups_for_user(monkeypatch):
    sample_groups = [{"GroupId": "g-1", "DisplayName": "Eng", "members": []}]

    monkeypatch.setattr(
        aws_module,
        "identity_store",
        types.SimpleNamespace(
            get_groups_for_user=lambda email, role=None: _make_resp(
                True, data=sample_groups
            )
        ),
    )

    # helper: recursively convert dict/list to SimpleNamespace for attribute access
    def _to_ns(obj):
        if isinstance(obj, dict):
            return types.SimpleNamespace(**{k: _to_ns(v) for k, v in obj.items()})
        if isinstance(obj, list):
            return [_to_ns(i) for i in obj]
        return obj

    # monkeypatch AwsGroup.model_validate to be permissive for tests
    monkeypatch.setattr(
        aws_module,
        "AwsGroup",
        types.SimpleNamespace(model_validate=lambda x: _to_ns(x)),
    )

    provider = get_provider("aws")
    with pytest.raises(IntegrationError):
        provider.get_user_managed_groups("alice@example.com")


def test_get_user_managed_groups_with_list_memberships(monkeypatch):
    # list_group_memberships_for_member returns memberships that include Group dict
    fake_user_id = "u-1"
    memberships = [{"Group": {"GroupId": "g-2", "DisplayName": "Ops", "members": []}}]

    monkeypatch.setattr(
        aws_module,
        "identity_store",
        types.SimpleNamespace(
            get_user_by_username=lambda email: _make_resp(
                True, data={"UserId": fake_user_id}
            ),
            list_group_memberships_for_member=lambda user_id, role=None: _make_resp(
                True, data=memberships
            ),
        ),
    )

    monkeypatch.setattr(
        aws_module,
        "AwsGroup",
        types.SimpleNamespace(model_validate=lambda x: _to_ns(x)),
    )

    provider = get_provider("aws")
    groups = provider.get_user_managed_groups("alice@example.com")
    assert isinstance(groups, list)
    assert groups and groups[0]["id"] == "g-2"


def test_add_member_sync_happy_path(monkeypatch):
    fake_user_id = "u-123"
    fake_user_data = {
        "UserId": fake_user_id,
        "Emails": [{"Value": "alice@example.com"}],
        "Name": {"GivenName": "Alice", "FamilyName": "Anderson"},
    }

    monkeypatch.setattr(
        aws_module,
        "identity_store",
        types.SimpleNamespace(
            get_user_by_username=lambda email: _make_resp(
                True, data={"UserId": fake_user_id}
            ),
            create_group_membership=lambda group_id, user_id: _make_resp(
                True, data={"MembershipId": "m-1", "MemberId": {"UserId": user_id}}
            ),
            get_user=lambda user_id: _make_resp(True, data=fake_user_data),
        ),
    )

    monkeypatch.setattr(
        aws_module,
        "AwsUser",
        types.SimpleNamespace(model_validate=lambda x: _to_ns(x)),
    )

    provider = get_provider("aws")
    member = {"email": "alice@example.com"}
    out = provider.add_member("g-1", member, "reason")
    assert out["email"] == "alice@example.com"
    assert out["first_name"] == "Alice"


def test_remove_member_sync_happy_path(monkeypatch):
    fake_user_id = "u-123"

    monkeypatch.setattr(
        aws_module,
        "identity_store",
        types.SimpleNamespace(
            get_user_by_username=lambda email: _make_resp(
                True, data={"UserId": fake_user_id}
            ),
            get_group_membership_id=lambda group_id, user_id: _make_resp(
                True, data={"MembershipId": "m-1"}
            ),
            delete_group_membership=lambda membership_id: _make_resp(
                True, data={"status": "deleted"}
            ),
            get_user=lambda user_id: _make_resp(
                True,
                data={
                    "UserId": fake_user_id,
                    "Emails": [{"Value": "alice@example.com"}],
                    "Name": {"GivenName": "Alice", "FamilyName": "Anderson"},
                },
            ),
        ),
    )

    monkeypatch.setattr(
        aws_module,
        "AwsUser",
        types.SimpleNamespace(model_validate=lambda x: _to_ns(x)),
    )

    provider = get_provider("aws")
    member = {"email": "alice@example.com"}
    out = provider.remove_member("g-1", member, "reason")
    assert out["email"] == "alice@example.com"
    assert out["family_name"] == "Anderson"


def test_add_member_user_resolution_failure_raises(monkeypatch):
    monkeypatch.setattr(
        aws_module,
        "identity_store",
        types.SimpleNamespace(
            get_user_by_username=lambda email: _make_resp(
                False, data=None, error="not found"
            )
        ),
    )

    provider = get_provider("aws")
    member = {"email": "missing@example.com"}
    with pytest.raises(IntegrationError):
        provider.add_member("g-1", member, "reason")


def test_add_and_remove_with_string_member(monkeypatch):
    # provider.add_member/remove_member accept string member (email)
    fake_user_id = "u-str"
    monkeypatch.setattr(
        aws_module,
        "identity_store",
        types.SimpleNamespace(
            get_user_by_username=lambda email: _make_resp(
                True, data={"UserId": fake_user_id}
            ),
            create_group_membership=lambda gid, uid: _make_resp(
                True, data={"MembershipId": "m-1", "MemberId": {"UserId": uid}}
            ),
            get_group_membership_id=lambda gid, uid: _make_resp(
                True, data={"MembershipId": "m-1"}
            ),
            delete_group_membership=lambda mid: _make_resp(
                True, data={"status": "deleted"}
            ),
            get_user=lambda uid: _make_resp(
                True,
                data={
                    "UserId": uid,
                    "Emails": [{"Value": "s@example.com"}],
                    "Name": {"GivenName": "S", "FamilyName": "User"},
                },
            ),
        ),
    )
    monkeypatch.setattr(
        aws_module, "AwsUser", types.SimpleNamespace(model_validate=lambda x: _to_ns(x))
    )

    provider = get_provider("aws")
    add_out = provider.add_member("g-1", "s@example.com", "j")
    assert add_out["email"] == "s@example.com"
    rem_out = provider.remove_member("g-1", "s@example.com", "j")
    assert rem_out["email"] == "s@example.com"


def test_identity_store_returns_raw_dict_raises(monkeypatch):
    # identity_store returns a raw dict without .success -> should raise IntegrationError
    monkeypatch.setattr(
        aws_module,
        "identity_store",
        types.SimpleNamespace(get_user_by_username=lambda email: {"UserId": "u-x"}),
    )
    provider = get_provider("aws")
    with pytest.raises(IntegrationError):
        provider.add_member("g-1", {"email": "x@e.com"}, "j")


def test_get_group_members_handles_missing_userid(monkeypatch):
    fake_user_id = "u-no"
    # membership without MemberId.UserId
    memberships = [{"MemberId": {}}, {"MemberId": {"UserId": fake_user_id}}]
    monkeypatch.setattr(
        aws_module,
        "identity_store",
        types.SimpleNamespace(
            list_group_memberships=lambda gid: _make_resp(True, data=memberships),
            get_user=lambda uid: _make_resp(
                True, data={"UserId": uid, "Emails": [{"Value": "a@b"}], "Name": {}}
            ),
        ),
    )
    monkeypatch.setattr(
        aws_module, "AwsUser", types.SimpleNamespace(model_validate=lambda x: _to_ns(x))
    )

    provider = get_provider("aws")
    members = provider.get_group_members("g-1")
    assert isinstance(members, list)
    # first member has no user id -> email None
    assert members[0]["email"] is None


def test_validate_permissions_true_false(monkeypatch):
    monkeypatch.setattr(
        aws_module,
        "identity_store",
        types.SimpleNamespace(),
    )
    provider = get_provider("aws")
    # monkeypatch provider internals
    monkeypatch.setattr(provider, "_get_user_managed_groups", lambda u: [{"id": "g-1"}])
    assert provider.validate_permissions("u", "g-1", "act") is True
    assert provider.validate_permissions("u", "g-2", "act") is False


@pytest.mark.asyncio
async def test_async_wrappers_call_sync_impl(monkeypatch):
    # reuse happy-path add_member flow for async wrapper
    fake_user_id = "u-async"

    monkeypatch.setattr(
        aws_module,
        "identity_store",
        types.SimpleNamespace(
            get_user_by_username=lambda email: _make_resp(
                True, data={"UserId": fake_user_id}
            ),
            create_group_membership=lambda group_id, user_id: _make_resp(
                True, data={"MembershipId": "m-1", "MemberId": {"UserId": user_id}}
            ),
            get_user=lambda user_id: _make_resp(
                True,
                data={
                    "UserId": fake_user_id,
                    "Emails": [{"Value": "async@example.com"}],
                    "Name": {"GivenName": "Async", "FamilyName": "User"},
                },
            ),
        ),
    )

    monkeypatch.setattr(
        aws_module,
        "AwsUser",
        types.SimpleNamespace(model_validate=lambda x: _to_ns(x)),
    )

    provider = get_provider("aws")
    # async add
    result = await provider.add_group_member(
        "g-1", "async@example.com", justification="j"
    )
    assert result.status == result.status.__class__.SUCCESS
    assert "member" in (result.data or {})

    # async list
    monkeypatch.setattr(
        aws_module.identity_store,
        "list_group_memberships",
        lambda group_key: _make_resp(
            True, data=[{"MemberId": {"UserId": fake_user_id}}]
        ),
        raising=False,
    )
    list_res = await provider.list_group_members("g-1")
    assert list_res.status == list_res.status.__class__.SUCCESS

    # async remove
    monkeypatch.setattr(
        aws_module.identity_store,
        "get_group_membership_id",
        lambda group_key, user_id: _make_resp(True, data={"MembershipId": "m-1"}),
        raising=False,
    )
    monkeypatch.setattr(
        aws_module.identity_store,
        "delete_group_membership",
        lambda membership_id: _make_resp(True, data={"status": "deleted"}),
        raising=False,
    )
    rem_res = await provider.remove_group_member(
        "g-1", "async@example.com", justification="j"
    )
    assert rem_res.status == rem_res.status.__class__.SUCCESS
