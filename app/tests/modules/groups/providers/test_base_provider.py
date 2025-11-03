import pytest
from modules.groups.providers.base import (
    GroupProvider,
    OperationResult,
)


class DummyProvider(GroupProvider):
    def __init__(self):
        # Skip circuit breaker init for test provider
        self._circuit_breaker = None

    @property
    def capabilities(self):
        return super().capabilities

    def list_groups_for_user(self, user_key):
        return [{"id": "g1"}, {"id": "g2"}]

    def _add_member_impl(self, group_key, member_key, justification):
        return OperationResult.success(
            data={
                "result": {
                    "group": group_key,
                    "member": member_key,
                    "justification": justification,
                }
            }
        )

    def _remove_member_impl(self, group_key, member, justification):
        return OperationResult.success(
            data={
                "result": {
                    "group": group_key,
                    "member": member,
                    "justification": justification,
                }
            }
        )

    def _get_group_members_impl(self, group_key, **kwargs):
        return OperationResult.success(data={"members": [{"id": "m1"}, {"id": "m2"}]})

    def _list_groups_impl(self, **kwargs):
        return OperationResult.success(data={"groups": []})

    def _list_groups_with_members_impl(self, **kwargs):
        return OperationResult.success(data={"groups": []})

    def validate_permissions(self, user_email, group_key, action):
        return user_email == "admin@example.com"

    def create_user(self, user_data):
        return {"id": "u1", **user_data}

    def delete_user(self, user_key):
        return {"id": user_key, "deleted": True}


def test_create_user_not_implemented():
    class NoUserProvider(GroupProvider):
        def __init__(self):
            # Skip circuit breaker init for test provider
            self._circuit_breaker = None

        @property
        def capabilities(self):
            return super().capabilities

        def list_groups_for_user(self, user_key):
            raise NotImplementedError()

        def _add_member_impl(self, group_key, member_key, justification):
            raise NotImplementedError()

        def _remove_member_impl(self, group_key, member, justification):
            raise NotImplementedError()

        def _get_group_members_impl(self, group_key, **kwargs):
            raise NotImplementedError()

        def validate_permissions(self, user_email, group_key, action):
            raise NotImplementedError()

        def _list_groups_impl(self, *args, **kwargs):
            return OperationResult.success(data={"groups": []})

        def _list_groups_with_members_impl(self, **kwargs):
            return OperationResult.success(data={"groups": []})

    p = NoUserProvider()
    with pytest.raises(NotImplementedError):
        p.create_user({"name": "x"})
    with pytest.raises(NotImplementedError):
        p.delete_user("u1")
