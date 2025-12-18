import pytest

from infrastructure.clients.aws.helpers import AWSHelpers
from infrastructure.operations.result import OperationResult


class DummyAWS:
    def __init__(self, users=None, groups=None, memberships=None):
        self._users = users or {}
        self._groups = groups or []
        self._memberships = memberships or {}

    def get_user(self, user_id, **kwargs):
        """Mock get_user - identity_store_id optional, not required positional."""
        if user_id in self._users:
            return OperationResult.success(data=self._users[user_id])
        return OperationResult.permanent_error(message="not found")

    def list_users(self, **kwargs):
        """Mock list_users - identity_store_id optional keyword."""
        if self._groups:
            return OperationResult.success(data=self._groups)
        return OperationResult.success(data=list(self._users.values()))


@pytest.mark.unit
class TestHelpers:
    def test_get_batch_users(self):
        users = {
            "u1": {"UserId": "u1", "Name": "A"},
            "u2": {"UserId": "u2", "Name": "B"},
        }
        aws = DummyAWS(users=users)
        helpers = AWSHelpers(aws)
        res = helpers.get_batch_users("sid", ["u1", "u3"])
        assert res.is_success
        assert res.data["u1"]["UserId"] == "u1"
        assert res.data["u3"] is None

    def test_get_batch_groups(self):
        groups = {"g1": {"GroupId": "g1", "DisplayName": "G1"}}
        aws = DummyAWS(users=groups)
        helpers = AWSHelpers(aws)
        res = helpers.get_batch_groups("sid", ["g1", "g2"])
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

        helpers = AWSHelpers(DummyAWS())
        res = helpers._assemble_groups_with_memberships(
            groups, memberships, users_by_id, tolerate_errors=False
        )
        assert isinstance(res, list)
        assert res[0]["GroupMemberships"][0]["UserDetails"]["UserId"] == "u1"

    def test_healthcheck_success(self):
        aws = DummyAWS(users={"u1": {"UserId": "u1"}})
        helpers = AWSHelpers(aws)
        assert helpers.healthcheck("sid") is True

    def test_healthcheck_failure(self):
        class BadAWS:
            def list_users(self, identity_store_id, **kwargs):
                return OperationResult.permanent_error(message="boom")

        assert AWSHelpers(BadAWS()).healthcheck("sid") is False
