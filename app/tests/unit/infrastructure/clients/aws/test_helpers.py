
from infrastructure.clients.aws.helpers import (
    get_batch_users,
    get_batch_groups,
    _assemble_groups_with_memberships,
    healthcheck,
)
from infrastructure.operations.result import OperationResult


class DummyAWS:
    def __init__(self, users=None, groups=None, memberships=None):
        self._users = users or {}
        self._groups = groups or []
        self._memberships = memberships or {}

    def get_user(self, identity_store_id, user_id, **kwargs):
        if user_id in self._users:
            return OperationResult.success(data=self._users[user_id])
        return OperationResult.permanent_error(message="not found")

    def list_users(self, identity_store_id, **kwargs):
        # Used both for listing users and for placeholder memberships in helpers
        if self._groups:
            return OperationResult.success(data=self._groups)
        return OperationResult.success(data=list(self._users.values()))


class TestHelpers:
    def test_get_batch_users(self):
        users = {
            "u1": {"UserId": "u1", "Name": "A"},
            "u2": {"UserId": "u2", "Name": "B"},
        }
        aws = DummyAWS(users=users)
        res = get_batch_users(aws, "sid", ["u1", "u3"])
        assert res.is_success
        assert res.data["u1"]["UserId"] == "u1"
        assert res.data["u3"] is None

    def test_get_batch_groups(self):
        groups = {"g1": {"GroupId": "g1", "DisplayName": "G1"}}
        aws = DummyAWS(users=groups)
        res = get_batch_groups(aws, "sid", ["g1", "g2"])
        assert res.is_success
        assert res.data["g1"]["GroupId"] == "g1"
        assert res.data["g2"] is None

    def test_assemble_groups_with_memberships_basic(self):
        groups = [{"GroupId": "g1", "DisplayName": "G1"}]
        memberships = {"g1": [{"UserId": "u1"}, {"UserId": "u2"}]}
        users_by_id = {
            "u1": {"UserId": "u1", "Name": "A"},
            "u2": {"UserId": "u2", "Name": "B"},
        }

        res = _assemble_groups_with_memberships(
            groups, memberships, users_by_id, tolerate_errors=False
        )
        assert isinstance(res, list)
        assert res[0]["GroupMemberships"][0]["UserDetails"]["UserId"] == "u1"

    def test_healthcheck_success(self):
        aws = DummyAWS(users={"u1": {"UserId": "u1"}})
        assert healthcheck(aws, "sid") is True

    def test_healthcheck_failure(self):
        class BadAWS:
            def list_users(self, identity_store_id, **kwargs):
                return OperationResult.permanent_error(message="boom")

        assert healthcheck(BadAWS(), "sid") is False
