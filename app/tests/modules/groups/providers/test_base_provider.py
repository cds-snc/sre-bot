import pytest
from modules.groups.providers.base import (
    GroupProvider,
)


class DummyProvider(GroupProvider):
    @property
    def capabilities(self):
        return super().capabilities

    def list_groups_for_user(self, user_key):
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


def test_create_user_not_implemented():
    class NoUserProvider(GroupProvider):
        @property
        def capabilities(self):
            return super().capabilities

        def list_groups_for_user(self, user_key):
            raise NotImplementedError()

        def add_member(self, group_key, member_key, justification):
            raise NotImplementedError()

        def remove_member(self, group_key, member, justification):
            raise NotImplementedError()

        def get_group_members(self, group_key, **kwargs):
            raise NotImplementedError()

        def validate_permissions(self, user_email, group_key, action):
            raise NotImplementedError()

        def list_groups(self, *args, **kwargs):
            return []

        def list_groups_with_members(self, **kwargs):
            return []

    p = NoUserProvider()
    with pytest.raises(NotImplementedError):
        p.create_user({"name": "x"})
    with pytest.raises(NotImplementedError):
        p.delete_user("u1")
