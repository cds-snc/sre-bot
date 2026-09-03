"""Behaviour tests for provisioning user sourcing on DirectoryProvider.

The google branch yields canonical DirectoryUser values; the aws branch keeps
returning raw identity_store dicts.
"""

import pytest

from infrastructure.directory.models import DirectoryUser
from infrastructure.operations import OperationResult, OperationStatus
from modules.provisioning import users

_ERROR_CODE = "quotaExceeded"
# The retired google_directory.list_users() default page/limit size.
_RETIRED_DEFAULT_LIMIT = 100


class FakeDirectory:
    """Records how list_users was called and replays a canned result."""

    def __init__(self, result: OperationResult[list[DirectoryUser]]):
        self._result = result
        self.list_users_calls: list[tuple[tuple, dict]] = []

    def list_users(self, *args, **kwargs) -> OperationResult[list[DirectoryUser]]:
        self.list_users_calls.append((args, kwargs))
        return self._result


def _user(email: str, given_name: str = "User", family_name: str = "One") -> DirectoryUser:
    return DirectoryUser(
        email=email,
        provider_user_id=f"id-{email}",
        given_name=given_name,
        family_name=family_name,
    )


def _unavailable() -> OperationResult[list[DirectoryUser]]:
    return OperationResult.error(
        status=OperationStatus.TRANSIENT_ERROR,
        message="Google Directory is unavailable",
        error_code=_ERROR_CODE,
    )


@pytest.fixture
def bind_directory(monkeypatch: pytest.MonkeyPatch):
    """Bind a fake DirectoryProvider onto the module under test."""

    def _bind(result: OperationResult[list[DirectoryUser]]) -> FakeDirectory:
        fake = FakeDirectory(result)
        monkeypatch.setattr(users, "get_directory_provider", lambda: fake)
        return fake

    return _bind


@pytest.mark.unit
class TestGetUsersFromIntegration:
    """Source selection, canonical payloads and filtering."""

    def test_should_return_an_empty_list_for_an_unknown_integration(self):
        assert users.get_users_from_integration("unknown_integration") == []

    def test_should_return_directory_users_from_the_google_branch(self, bind_directory):
        bind_directory(OperationResult.success([_user("user1@example.com"), _user("user2@example.com")]))

        result = users.get_users_from_integration("google_directory")

        assert [user.email for user in result] == ["user1@example.com", "user2@example.com"]
        assert all(isinstance(user, DirectoryUser) for user in result)

    def test_should_request_the_full_directory_without_a_limit(self, bind_directory):
        fake = bind_directory(
            OperationResult.success([_user(f"user{index}@example.com") for index in range(_RETIRED_DEFAULT_LIMIT + 50)])
        )

        result = users.get_users_from_integration("google_directory")

        assert fake.list_users_calls == [((), {})]
        assert len(result) == _RETIRED_DEFAULT_LIMIT + 50

    def test_should_raise_a_module_local_error_carrying_the_error_code_on_a_failed_listing(self, bind_directory):
        bind_directory(_unavailable())

        with pytest.raises(users.DirectoryUsersUnavailableError) as excinfo:
            users.get_users_from_integration("google_directory")

        assert excinfo.value.error_code == _ERROR_CODE
        assert "unavailable" in str(excinfo.value)

    def test_should_apply_processing_filters_to_directory_user_attributes(self, bind_directory):
        bind_directory(OperationResult.success([_user("user1@example.com"), _user("user2@example.com")]))

        result = users.get_users_from_integration(
            "google_directory",
            processing_filters=[lambda user: user.email == "user1@example.com"],
        )

        assert [user.email for user in result] == ["user1@example.com"]

    def test_should_return_raw_identity_store_dicts_from_the_aws_branch(self, monkeypatch: pytest.MonkeyPatch):
        aws_users = [{"UserName": "user1@example.com", "UserId": "user-1"}]
        monkeypatch.setattr(users.identity_store, "list_users", lambda *args, **kwargs: aws_users)

        assert users.get_users_from_integration("aws_identity_center") == aws_users

    def test_should_not_bind_the_google_workspace_directory_module(self):
        assert not hasattr(users, "google_directory")
