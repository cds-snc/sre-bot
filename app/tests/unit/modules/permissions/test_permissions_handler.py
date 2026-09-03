"""Behaviour tests for the permissions group-membership gate on DirectoryProvider.

The seam is the module-bound get_directory_provider symbol; the double is a
local Protocol-conformant fake rather than a MagicMock (decisions/testing.md).
"""

import pytest

from infrastructure.directory.models import DirectoryMember
from infrastructure.operations import OperationResult, OperationStatus
from modules.permissions import handler

_ERROR_CODE = "rateLimitExceeded"


class FakeDirectory:
    """Replays a queued get_group_members result per group key and records asks."""

    def __init__(self, results: dict[str, OperationResult[list[DirectoryMember]]]):
        self._results = results
        self.requested_group_keys: list[str] = []

    def get_group_members(
        self,
        group_key: str,
        include_member_types: set[str] | None = None,
    ) -> OperationResult[list[DirectoryMember]]:
        self.requested_group_keys.append(group_key)
        return self._results[group_key]


def _members(*emails: str) -> OperationResult[list[DirectoryMember]]:
    return OperationResult.success([DirectoryMember(email=email) for email in emails])


def _unavailable() -> OperationResult[list[DirectoryMember]]:
    return OperationResult.error(
        status=OperationStatus.TRANSIENT_ERROR,
        message="Google Directory is unavailable",
        error_code=_ERROR_CODE,
    )


@pytest.fixture
def bind_directory(monkeypatch: pytest.MonkeyPatch):
    """Bind a fake DirectoryProvider onto the module under test."""

    def _bind(results: dict[str, OperationResult[list[DirectoryMember]]]) -> FakeDirectory:
        fake = FakeDirectory(results)
        monkeypatch.setattr(handler, "get_directory_provider", lambda: fake)
        return fake

    return _bind


@pytest.mark.unit
class TestIsUserMemberOfGroups:
    """The security gate guarding the /aws groups and /aws users commands."""

    def test_should_return_true_when_the_user_is_in_the_first_group(self, bind_directory):
        bind_directory(
            {
                "group_id_1": _members("user.name1@email.com", "user.name2@email.com"),
                "group_id_2": _members("user.name4@email.com"),
            }
        )

        assert handler.is_user_member_of_groups("user.name1@email.com", ["group_id_1", "group_id_2"]) is True

    def test_should_return_true_when_the_user_is_only_in_a_later_group(self, bind_directory):
        bind_directory(
            {
                "group_id_1": _members("user.name1@email.com"),
                "group_id_2": _members("user.name4@email.com"),
            }
        )

        assert handler.is_user_member_of_groups("user.name4@email.com", ["group_id_1", "group_id_2"]) is True

    def test_should_return_false_when_the_user_is_in_no_group(self, bind_directory):
        bind_directory(
            {
                "group_id_1": _members("user.name1@email.com"),
                "group_id_2": _members("user.name4@email.com"),
            }
        )

        assert handler.is_user_member_of_groups("user.name3@email.com", ["group_id_1", "group_id_2"]) is False

    def test_should_skip_an_empty_group_without_error(self, bind_directory):
        bind_directory(
            {
                "group_id_1": _members(),
                "group_id_2": _members("user.name4@email.com"),
            }
        )

        assert handler.is_user_member_of_groups("user.name4@email.com", ["group_id_1", "group_id_2"]) is True

    def test_should_match_the_user_key_case_insensitively(self, bind_directory):
        bind_directory({"group_id_1": _members("user.name1@email.com")})

        assert handler.is_user_member_of_groups("User.Name1@Email.com", ["group_id_1"]) is True

    def test_should_request_the_configured_group_keys_verbatim(self, bind_directory):
        fake = bind_directory(
            {
                "group_id_1": _members("user.name1@email.com"),
                "group_id_2": _members(),
            }
        )

        handler.is_user_member_of_groups("nobody@email.com", ["group_id_1", "group_id_2"])

        assert fake.requested_group_keys == ["group_id_1", "group_id_2"]

    def test_should_stop_asking_once_the_user_is_found(self, bind_directory):
        fake = bind_directory(
            {
                "group_id_1": _members("user.name1@email.com"),
                "group_id_2": _members(),
            }
        )

        handler.is_user_member_of_groups("user.name1@email.com", ["group_id_1", "group_id_2"])

        assert fake.requested_group_keys == ["group_id_1"]

    def test_should_raise_a_module_local_error_carrying_the_error_code_on_a_failed_lookup(self, bind_directory):
        bind_directory({"group_id_1": _unavailable()})

        with pytest.raises(handler.PermissionCheckError) as excinfo:
            handler.is_user_member_of_groups("user.name1@email.com", ["group_id_1"])

        assert excinfo.value.error_code == _ERROR_CODE
        assert "unavailable" in str(excinfo.value)


@pytest.mark.unit
class TestPermissionsHandlerBoundary:
    """The module owns no vendor coupling and no dead entry points."""

    def test_should_not_bind_the_google_workspace_directory_module(self):
        assert not hasattr(handler, "google_directory")

    def test_should_not_expose_the_deleted_authorizers_helper(self):
        assert not hasattr(handler, "get_authorizers_from_groups")
