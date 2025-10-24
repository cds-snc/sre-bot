import pytest
from modules.groups.providers.base import (
    GroupProvider,
    OperationResult,
    OperationStatus,
)


class DummyProvider(GroupProvider):
    @property
    def capabilities(self):
        return super().capabilities

    def get_user_managed_groups(self, user_key):
        return [{"id": "g1"}, {"id": "g2"}]

    def add_member(self, group_key, member_key, justification):
        return {
            "group": group_key,
            "member": member_key,
            "justification": justification,
        }

    def remove_member(self, group_key, member, justification):
        return {"group": group_key, "member": member, "justification": justification}

    def get_group_members(self, group_key, **kwargs):
        return [{"id": "m1"}, {"id": "m2"}]

    def validate_permissions(self, user_email, group_key, action):
        return user_email == "admin@example.com"

    def create_user(self, user_data):
        return {"id": "u1", **user_data}

    def delete_user(self, user_key):
        return {"id": user_key, "deleted": True}


def test_get_user_managed_groups_result():
    p = DummyProvider()
    result = p.get_user_managed_groups_result("alice@example.com")
    assert isinstance(result, OperationResult)
    assert result.status == OperationStatus.SUCCESS
    assert "groups" in result.data
    assert len(result.data["groups"]) == 2


def test_add_member_result():
    p = DummyProvider()
    result = p.add_member_result("g1", "m1", "reason")
    assert result.status == OperationStatus.SUCCESS
    assert result.data["member"]["member"] == "m1"


def test_remove_member_result():
    p = DummyProvider()
    result = p.remove_member_result("g1", "m1", "reason")
    assert result.status == OperationStatus.SUCCESS
    assert result.data["member"] == "m1"


def test_get_group_members_result():
    p = DummyProvider()
    result = p.get_group_members_result("g1")
    assert result.status == OperationStatus.SUCCESS
    assert "members" in result.data
    assert len(result.data["members"]) == 2


def test_validate_permissions_result_true():
    p = DummyProvider()
    result = p.validate_permissions_result("admin@example.com", "g1", "action")
    assert result.status == OperationStatus.SUCCESS
    assert result.data is True


def test_validate_permissions_result_false():
    p = DummyProvider()
    result = p.validate_permissions_result("bob@example.com", "g1", "action")
    assert result.status == OperationStatus.SUCCESS
    assert result.data is False


def test_create_user_not_implemented():
    class NoUserProvider(GroupProvider):
        @property
        def capabilities(self):
            return super().capabilities

        def get_user_managed_groups(self, user_key):
            raise NotImplementedError()

        def add_member(self, group_key, member_key, justification):
            raise NotImplementedError()

        def remove_member(self, group_key, member, justification):
            raise NotImplementedError()

        def get_group_members(self, group_key, **kwargs):
            raise NotImplementedError()

        def validate_permissions(self, user_email, group_key, action):
            raise NotImplementedError()

    p = NoUserProvider()
    with pytest.raises(NotImplementedError):
        p.create_user({"name": "x"})
    with pytest.raises(NotImplementedError):
        p.delete_user("u1")


def test_opresult_wrapper_handles_exception():
    class FailingProvider(DummyProvider):
        def get_user_managed_groups(self, user_key):
            raise ValueError("fail")

    p = FailingProvider()
    result = p.get_user_managed_groups_result("any")
    assert result.status == OperationStatus.TRANSIENT_ERROR
    assert "fail" in result.message
