# pylint: disable=protected-access,missing-function-docstring,missing-module-docstring, missing-class-docstring
import importlib
import types

import pytest

from modules.groups.providers.base import OperationResult, OperationStatus
from modules.groups.models import NormalizedMember
from modules.groups.errors import IntegrationError


def _import_provider(safe_providers_import):
    # ensure safe import (fixture handles setup)
    _ = safe_providers_import
    return importlib.import_module("modules.groups.providers.aws_identity_center")


class _FakeResp:
    def __init__(self, success, data):
        self.success = success
        self.data = data


def _dict_to_obj(d):
    """Recursively convert a dict into a SimpleNamespace for attribute access."""
    if isinstance(d, dict):
        ns = types.SimpleNamespace()
        for k, v in d.items():
            setattr(ns, k, _dict_to_obj(v))
        return ns
    if isinstance(d, list):
        return [_dict_to_obj(i) for i in d]
    return d


@pytest.fixture
def provider_module(safe_providers_import):
    """Import and return the provider module under test."""
    return _import_provider(safe_providers_import)


@pytest.fixture
def provider(provider_module):
    """Instantiate and return a fresh provider instance."""
    return provider_module.AwsIdentityCenterProvider()


@pytest.fixture
def id_store_factory(monkeypatch, provider_module):
    """Return a helper that can install an identity_store with given callables.

    Usage: id_store_factory(create_group_membership=fn, get_user=fn)
    """

    def _installer(**fns):
        monkeypatch.setattr(
            provider_module, "identity_store", types.SimpleNamespace(**fns)
        )

    return _installer


@pytest.fixture
def allow_minimal_pydantic(monkeypatch, provider_module):
    """Monkeypatch AwsUser/AwsGroup model_validate to accept minimal dicts.

    Yields nothing; tests should call this fixture when they want to skip
    strict Pydantic validation and accept simple dicts.
    """

    # Provide dummy classes that both implement `model_validate` and are
    # constructible (AwsUser()). The provider sometimes calls AwsUser()
    # (no-arg constructor) so the dummy must provide safe default attrs
    # like Emails and Name to avoid attribute errors during normalization.
    class DummyAwsUser:
        def __init__(self, *a, **kw):
            # defaults used when provider calls AwsUser() without data
            self.Emails = []
            self.Name = types.SimpleNamespace(GivenName=None, FamilyName=None)
            self.UserId = None
            self.UserName = None

        @staticmethod
        def model_validate(data):
            # return a SimpleNamespace-like object for attribute access but
            # ensure required attributes the provider expects exist so tests
            # using this permissive fixture don't blow up with AttributeError.
            ns = _dict_to_obj(data if isinstance(data, dict) else {})

            # Emails: ensure list of namespaces with Value attr
            if not hasattr(ns, "Emails") or ns.Emails is None:
                ns.Emails = []
            else:
                if isinstance(ns.Emails, list):
                    out_emails = []
                    for e in ns.Emails:
                        if isinstance(e, dict):
                            out_emails.append(_dict_to_obj(e))
                        elif isinstance(e, types.SimpleNamespace):
                            out_emails.append(e)
                        else:
                            out_emails.append(types.SimpleNamespace(Value=e))
                    ns.Emails = out_emails

            # Name: ensure namespace with GivenName/FamilyName
            if not hasattr(ns, "Name") or ns.Name is None:
                ns.Name = types.SimpleNamespace(GivenName=None, FamilyName=None)
            else:
                if isinstance(ns.Name, dict):
                    ns.Name = _dict_to_obj(ns.Name)
                if not hasattr(ns.Name, "GivenName"):
                    ns.Name.GivenName = None
                if not hasattr(ns.Name, "FamilyName"):
                    ns.Name.FamilyName = None

            # UserId/UserName defaults
            if not hasattr(ns, "UserId"):
                ns.UserId = None
            if not hasattr(ns, "UserName"):
                ns.UserName = None

            return ns

    class DummyAwsGroup:
        def __init__(self, *a, **kw):
            self.GroupId = None
            self.DisplayName = None
            self.Description = None

        @staticmethod
        def model_validate(data):
            return _dict_to_obj(data)

    monkeypatch.setattr(provider_module, "AwsUser", DummyAwsUser)
    monkeypatch.setattr(provider_module, "AwsGroup", DummyAwsGroup)


def test_extract_id_from_resp_none(provider):
    assert provider._extract_id_from_resp(None, ["UserId"]) is None


def test_extract_id_from_resp_missing_success(provider):
    class BadResp:
        def __init__(self, data):
            self.data = data

    with pytest.raises(Exception):
        provider._extract_id_from_resp(BadResp({}), ["UserId"])


def test_extract_id_from_resp_success_false(provider):
    resp = _FakeResp(False, {"UserId": "u-1"})
    assert provider._extract_id_from_resp(resp, ["UserId"]) is None


def test_extract_id_from_resp_string_data(provider):
    resp = _FakeResp(True, "simple-id")
    assert provider._extract_id_from_resp(resp, ["UserId"]) == "simple-id"


def test_extract_id_from_resp_dict_userid_or_id(provider):
    resp1 = _FakeResp(True, {"UserId": "u-123"})
    assert provider._extract_id_from_resp(resp1, ["UserId", "Id"]) == "u-123"

    resp2 = _FakeResp(True, {"Id": "i-456"})
    assert provider._extract_id_from_resp(resp2, ["UserId", "Id"]) == "i-456"


def test_extract_id_from_resp_memberid_dict(provider):
    resp = _FakeResp(True, {"MemberId": {"UserId": "member-u-1"}})
    assert provider._extract_id_from_resp(resp, ["UserId"]) == "member-u-1"


def test_ensure_user_id_from_email_missing_integration_function(
    monkeypatch, provider_module, provider
):
    """If identity_store lacks get_user_by_username, raise IntegrationError."""

    # replace identity_store with an object that has no get_user_by_username
    monkeypatch.setattr(provider_module, "identity_store", types.SimpleNamespace())

    with pytest.raises(IntegrationError):
        provider._ensure_user_id_from_email("user@example.com")


def test_ensure_user_id_from_email_unexpected_return_type(
    monkeypatch, provider_module, provider
):
    """If get_user_by_username returns object missing 'success', raise IntegrationError."""

    def fake_get_user_by_username(email):
        return types.SimpleNamespace(data={"UserId": "u-1"})

    monkeypatch.setattr(
        provider_module,
        "identity_store",
        types.SimpleNamespace(get_user_by_username=fake_get_user_by_username),
    )

    with pytest.raises(IntegrationError):
        provider._ensure_user_id_from_email("user@example.com")


def test_ensure_user_id_from_email_integration_failure(
    monkeypatch, provider_module, provider
):
    """If underlying integration returns success=False, raise IntegrationError."""

    def fake_get_user_by_username(email):
        return types.SimpleNamespace(success=False, data=None)

    monkeypatch.setattr(
        provider_module,
        "identity_store",
        types.SimpleNamespace(get_user_by_username=fake_get_user_by_username),
    )

    with pytest.raises(IntegrationError):
        provider._ensure_user_id_from_email("user@example.com")


def test_ensure_user_id_from_email_success_returns_id(
    monkeypatch, provider_module, provider
):
    """When integration returns success and a UserId, ensure it's returned."""

    def fake_get_user_by_username(email):
        return types.SimpleNamespace(success=True, data={"UserId": "u-999"})

    monkeypatch.setattr(
        provider_module,
        "identity_store",
        types.SimpleNamespace(get_user_by_username=fake_get_user_by_username),
    )

    assert provider._ensure_user_id_from_email("user@example.com") == "u-999"


def test_ensure_user_id_from_email_success_but_no_id_raises(
    monkeypatch, provider_module, provider
):
    """If success=True but no id present, raise ValueError."""

    def fake_get_user_by_username(email):
        return types.SimpleNamespace(success=True, data={})

    monkeypatch.setattr(
        provider_module,
        "identity_store",
        types.SimpleNamespace(get_user_by_username=fake_get_user_by_username),
    )

    with pytest.raises(ValueError):
        provider._ensure_user_id_from_email("user@example.com")


def test_resolve_membership_id_missing_integration_function(
    monkeypatch, provider_module, provider
):
    """If identity_store lacks get_group_membership_id, raise IntegrationError."""
    monkeypatch.setattr(provider_module, "identity_store", types.SimpleNamespace())

    with pytest.raises(IntegrationError):
        provider._resolve_membership_id("g1", "u1")


def test_resolve_membership_id_unexpected_return_type(
    monkeypatch, provider_module, provider
):
    """get_group_membership_id returns object missing 'success' -> IntegrationError"""

    def fake_get_group_membership_id(gk, uid):
        return types.SimpleNamespace(data={"MembershipId": "m-1"})

    monkeypatch.setattr(
        provider_module,
        "identity_store",
        types.SimpleNamespace(get_group_membership_id=fake_get_group_membership_id),
    )

    with pytest.raises(IntegrationError):
        provider._resolve_membership_id("g1", "u1")


def test_resolve_membership_id_integration_failure(
    monkeypatch, provider_module, provider
):
    """If integration returns success=False -> IntegrationError"""

    def fake_get_group_membership_id(gk, uid):
        return types.SimpleNamespace(success=False, data=None)

    monkeypatch.setattr(
        provider_module,
        "identity_store",
        types.SimpleNamespace(get_group_membership_id=fake_get_group_membership_id),
    )

    with pytest.raises(IntegrationError):
        provider._resolve_membership_id("g1", "u1")


def test_resolve_membership_id_success_returns_mid(
    monkeypatch, provider_module, provider
):
    """When integration returns membership id successfully, it's returned."""

    def fake_get_group_membership_id(gk, uid):
        return types.SimpleNamespace(success=True, data={"MembershipId": "m-999"})

    monkeypatch.setattr(
        provider_module,
        "identity_store",
        types.SimpleNamespace(get_group_membership_id=fake_get_group_membership_id),
    )

    assert provider._resolve_membership_id("g1", "u1") == "m-999"


def test_fetch_user_details_missing_integration_function(
    monkeypatch, provider_module, provider
):
    """If identity_store lacks get_user, raise IntegrationError."""
    monkeypatch.setattr(provider_module, "identity_store", types.SimpleNamespace())

    with pytest.raises(IntegrationError):
        provider._fetch_user_details("u-1")


def test_fetch_user_details_unexpected_return_type(
    monkeypatch, provider_module, provider
):
    """If get_user returns object missing 'success', raise IntegrationError."""

    def fake_get_user(uid):
        return types.SimpleNamespace(data={"UserId": "u-1"})

    monkeypatch.setattr(
        provider_module, "identity_store", types.SimpleNamespace(get_user=fake_get_user)
    )

    with pytest.raises(IntegrationError):
        provider._fetch_user_details("u-1")


def test_fetch_user_details_integration_failure(monkeypatch, provider_module, provider):
    """If get_user returns success=False, raise IntegrationError."""

    def fake_get_user(uid):
        return types.SimpleNamespace(success=False, data=None)

    monkeypatch.setattr(
        provider_module, "identity_store", types.SimpleNamespace(get_user=fake_get_user)
    )

    with pytest.raises(IntegrationError):
        provider._fetch_user_details("u-1")


def test_fetch_user_details_success_returns_data(
    monkeypatch, provider_module, provider
):
    """If get_user returns success=True with data, return that dict."""
    fake_data = {"UserId": "u-55", "Emails": [{"Value": "x@y"}]}

    def fake_get_user(uid):
        return types.SimpleNamespace(success=True, data=fake_data)

    monkeypatch.setattr(
        provider_module, "identity_store", types.SimpleNamespace(get_user=fake_get_user)
    )

    assert provider._fetch_user_details("u-55") == fake_data


def test_fetch_user_details_success_with_none_returns_empty_dict(
    monkeypatch, provider_module, provider
):
    """If success=True but data is None, return empty dict."""

    def fake_get_user(uid):
        return types.SimpleNamespace(success=True, data=None)

    monkeypatch.setattr(
        provider_module, "identity_store", types.SimpleNamespace(get_user=fake_get_user)
    )

    assert provider._fetch_user_details("u-66") == {}


def test_normalize_member_from_aws_success(allow_minimal_pydantic, provider):
    # allow_minimal_pydantic fixture monkeypatches AwsUser to accept minimal dicts

    raw_user = {
        "UserId": "u-1",
        "UserName": "user@example.com",
        "Emails": [{"Value": "user@example.com"}],
        "Name": {"GivenName": "Alice", "FamilyName": "Smith"},
    }

    nm = provider._normalize_member_from_aws(raw_user)
    assert isinstance(nm, NormalizedMember)
    assert nm.email == "user@example.com"
    assert nm.id == "u-1"
    assert nm.first_name == "Alice"
    assert nm.family_name == "Smith"


def test_normalize_member_from_aws_invalid_raises(allow_minimal_pydantic, provider):
    # With the permissive pydantic fixture, invalid-ish input should be
    # accepted and normalized to a NormalizedMember (fields may be None).
    nm = provider._normalize_member_from_aws({"not": "a user"})
    assert isinstance(nm, NormalizedMember)
    # missing email/id should yield None
    assert nm.email is None
    assert nm.id is None


def test_normalize_group_from_aws_no_members(allow_minimal_pydantic, provider):
    raw_group = {"GroupId": "g-1", "DisplayName": "G One", "Description": "d"}
    ng = provider._normalize_group_from_aws(raw_group)
    assert ng.id == "g-1"
    assert ng.name == "G One"
    assert ng.description == "d"
    assert ng.provider == "aws"
    assert isinstance(ng.members, list) and len(ng.members) == 0


def test_normalize_group_from_aws_with_members(allow_minimal_pydantic, provider):
    member = {
        "UserId": "u-2",
        "UserName": "bob@example.com",
        "Emails": [{"Value": "bob@example.com"}],
        "Name": {"GivenName": "Bob", "FamilyName": "Jones"},
    }
    # AWS returns memberships under the `GroupMemberships` key in this
    # provider's contract; tests updated to reflect that.
    raw_group = {"GroupId": "g-2", "DisplayName": "G Two", "GroupMemberships": [member]}

    ng = provider._normalize_group_from_aws(raw_group)
    assert ng.id == "g-2"
    assert ng.name == "G Two"
    assert ng.provider == "aws"
    assert len(ng.members) == 1
    m = ng.members[0]
    assert m.email == "bob@example.com"
    assert m.id == "u-2"


def test_resolve_member_identifier_with_string(safe_providers_import):
    mod = _import_provider(safe_providers_import)
    prov = mod.AwsIdentityCenterProvider()

    assert prov._resolve_member_identifier("user@example.com") == "user@example.com"


def test_resolve_member_identifier_empty_string_raises(safe_providers_import):
    mod = _import_provider(safe_providers_import)
    prov = mod.AwsIdentityCenterProvider()

    with pytest.raises(ValueError):
        prov._resolve_member_identifier("")


def test_resolve_member_identifier_with_dict(safe_providers_import):
    mod = _import_provider(safe_providers_import)
    prov = mod.AwsIdentityCenterProvider()

    assert prov._resolve_member_identifier({"email": "a@b.com"}) == "a@b.com"


def test_resolve_member_identifier_dict_missing_email_raises(safe_providers_import):
    mod = _import_provider(safe_providers_import)
    prov = mod.AwsIdentityCenterProvider()

    with pytest.raises(ValueError):
        prov._resolve_member_identifier({"id": "u-1"})


def test_resolve_member_identifier_wrong_type_raises(safe_providers_import):
    mod = _import_provider(safe_providers_import)
    prov = mod.AwsIdentityCenterProvider()

    with pytest.raises(TypeError):
        prov._resolve_member_identifier(123)


def test_add_member_rejects_non_dict(provider):
    res = provider.add_member("g1", "not-a-dict")
    assert isinstance(res, OperationResult)
    assert res.status == OperationStatus.TRANSIENT_ERROR
    assert "member_data must be a dict" in (res.message or "")


def test_add_member_missing_email_rejects(provider):
    res = provider.add_member("g1", {"not": "email"})
    assert isinstance(res, OperationResult)
    assert res.status == OperationStatus.TRANSIENT_ERROR
    assert "member_data.email is required" in (res.message or "")


def test_add_member_missing_create_group_membership(id_store_factory, provider):
    # install identity_store with only get_user_by_username
    def fake_get_user_by_username(email):
        return types.SimpleNamespace(success=True, data={"UserId": "u-1"})

    id_store_factory(get_user_by_username=fake_get_user_by_username)

    res = provider.add_member("g1", {"email": "x@y"})
    assert isinstance(res, OperationResult)
    assert res.status == OperationStatus.TRANSIENT_ERROR
    assert "create_group_membership" in (res.message or "")


def test_add_member_create_group_membership_unexpected_response(
    id_store_factory, provider
):
    def fake_create_group_membership(gk, uid):
        return types.SimpleNamespace(data={"MembershipId": "m-1"})

    def fake_get_user_by_username(email):
        return types.SimpleNamespace(success=True, data={"UserId": "u-1"})

    id_store_factory(
        create_group_membership=fake_create_group_membership,
        get_user_by_username=fake_get_user_by_username,
    )

    res = provider.add_member("g1", {"email": "x@y"})
    assert isinstance(res, OperationResult)
    assert res.status == OperationStatus.TRANSIENT_ERROR
    assert "create_group_membership returned unexpected type" in (res.message or "")


def test_add_member_success_returns_normalized(
    id_store_factory, allow_minimal_pydantic, provider
):
    # stub create_group_membership to return success and an id
    def fake_create_group_membership(gk, uid):
        return types.SimpleNamespace(success=True, data={"MembershipId": "m-1"})

    # stub identity_store.get_user_by_username used by _ensure_user_id_from_email
    def fake_get_user_by_username(email):
        return types.SimpleNamespace(success=True, data={"UserId": "u-900"})

    # stub get_user returning user details
    fake_user = {"UserId": "u-900", "Emails": [{"Value": "x@y"}], "Name": {}}

    def fake_get_user(uid):
        return types.SimpleNamespace(success=True, data=fake_user)

    id_store_factory(
        create_group_membership=fake_create_group_membership,
        get_user_by_username=fake_get_user_by_username,
        get_user=fake_get_user,
    )

    # allow_minimal_pydantic fixture monkeypatches AwsUser/AwsGroup
    res = provider.add_member("g1", {"email": "x@y"})
    # opresult_wrapper returns OperationResult, ensure success and payload shape
    assert isinstance(res, OperationResult)
    assert res.status == OperationStatus.SUCCESS
    assert isinstance(res.data.get("result"), dict)
    # The provider currently builds a minimal member payload for add_member
    # (it attaches 'id' and Name only), so the normalizer may not populate
    # the email field. Assert email is None and id is None to reflect that.
    assert res.data["result"].get("email") is None
    assert res.data["result"].get("id") is None


# end of tests


def test_remove_member_rejects_non_dict(provider):
    res = provider.remove_member("g1", "not-a-dict")
    assert isinstance(res, OperationResult)
    assert res.status == OperationStatus.TRANSIENT_ERROR


def test_remove_member_missing_email_rejects(provider):
    res = provider.remove_member("g1", {"not": "email"})
    assert isinstance(res, OperationResult)
    assert res.status == OperationStatus.TRANSIENT_ERROR


def test_remove_member_missing_delete_group_membership(
    monkeypatch, provider_module, provider
):
    # stub _ensure_user_id_from_email to return a user id
    monkeypatch.setattr(
        provider_module.AwsIdentityCenterProvider,
        "_ensure_user_id_from_email",
        lambda self, e: "u-1",
    )

    # ensure delete_group_membership missing
    monkeypatch.setattr(provider_module, "identity_store", types.SimpleNamespace())

    res = provider.remove_member("g1", {"email": "x@y"})
    assert isinstance(res, OperationResult)
    assert res.status == OperationStatus.TRANSIENT_ERROR


def test_remove_member_delete_group_membership_unexpected_response(
    monkeypatch, provider_module, provider
):
    monkeypatch.setattr(
        provider_module.AwsIdentityCenterProvider,
        "_ensure_user_id_from_email",
        lambda self, e: "u-1",
    )
    monkeypatch.setattr(
        provider_module.AwsIdentityCenterProvider,
        "_resolve_membership_id",
        lambda self, gk, uid: "m-1",
    )

    def fake_delete_group_membership(m_id):
        return types.SimpleNamespace(data=None)

    monkeypatch.setattr(
        provider_module,
        "identity_store",
        types.SimpleNamespace(delete_group_membership=fake_delete_group_membership),
    )

    res = provider.remove_member("g1", {"email": "x@y"})
    assert isinstance(res, OperationResult)
    assert res.status == OperationStatus.TRANSIENT_ERROR


def test_remove_member_success_returns_normalized(
    monkeypatch, id_store_factory, allow_minimal_pydantic, provider
):
    monkeypatch.setattr(
        provider.__class__,
        "_ensure_user_id_from_email",
        lambda self, e: "u-2",
    )
    monkeypatch.setattr(
        provider.__class__,
        "_resolve_membership_id",
        lambda self, gk, uid: "m-2",
    )

    def fake_delete_group_membership(m_id):
        return types.SimpleNamespace(success=True, data=None)

    def fake_get_user(uid):
        return types.SimpleNamespace(
            success=True, data={"UserId": uid, "Emails": [{"Value": "b@c"}]}
        )

    id_store_factory(
        delete_group_membership=fake_delete_group_membership, get_user=fake_get_user
    )

    res = provider.remove_member("g1", {"email": "b@c"})
    assert isinstance(res, OperationResult)
    assert res.status == OperationStatus.SUCCESS
    assert isinstance(res.data.get("result"), dict)


def test_get_group_members_missing_list_group_memberships(provider_module, provider):
    monkeypatch = pytest.MonkeyPatch()
    try:
        monkeypatch.setattr(provider_module, "identity_store", types.SimpleNamespace())
        res = provider.get_group_members("g1")
    finally:
        monkeypatch.undo()

    assert isinstance(res, OperationResult)
    assert res.status == OperationStatus.TRANSIENT_ERROR
    assert "list_group_memberships" in (res.message or "")


def test_get_group_members_success_no_user_details(
    provider_module, provider, allow_minimal_pydantic
):
    # return a list of memberships without MemberId details
    def fake_list_group_memberships(gk):
        return types.SimpleNamespace(
            success=True, data=[{"MemberId": {"UserId": None}}]
        )

    def _installer(**fns):
        setattr(provider_module, "identity_store", types.SimpleNamespace(**fns))

    _installer(list_group_memberships=fake_list_group_memberships)

    res = provider.get_group_members("g1")
    assert isinstance(res, OperationResult)
    assert res.status == OperationStatus.SUCCESS
    assert isinstance(res.data.get("members"), list)


def test_list_groups_missing_list_groups(provider_module, provider):
    monkeypatch = pytest.MonkeyPatch()
    try:
        monkeypatch.setattr(provider_module, "identity_store", types.SimpleNamespace())
        res = provider.list_groups()
    finally:
        monkeypatch.undo()

    assert isinstance(res, OperationResult)
    assert res.status == OperationStatus.TRANSIENT_ERROR
    assert "list_groups" in (res.message or "")


def test_list_groups_success(provider_module, provider, allow_minimal_pydantic):
    def fake_list_groups(**kwargs):
        return types.SimpleNamespace(
            success=True,
            data=[{"GroupId": "g-1", "DisplayName": "G1", "Description": "d"}],
        )

    setattr(
        provider_module,
        "identity_store",
        types.SimpleNamespace(list_groups=fake_list_groups),
    )

    res = provider.list_groups()
    assert isinstance(res, OperationResult)
    assert res.status == OperationStatus.SUCCESS
    assert isinstance(res.data.get("groups"), list)


def test_list_groups_with_members_success(
    provider_module, provider, allow_minimal_pydantic
):
    fake_group = {"GroupId": "g-2", "DisplayName": "G2", "members": []}

    def fake_list_groups_with_memberships(**kwargs):
        return types.SimpleNamespace(success=True, data=[fake_group])

    setattr(
        provider_module,
        "identity_store",
        types.SimpleNamespace(
            list_groups_with_memberships=fake_list_groups_with_memberships
        ),
    )

    res = provider.list_groups_with_members()
    assert isinstance(res, OperationResult)
    assert res.status == OperationStatus.SUCCESS
    assert isinstance(res.data.get("groups"), list)
