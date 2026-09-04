from structlog import get_logger

from infrastructure.directory import get_directory_provider

logger = get_logger()


class PermissionCheckError(Exception):
    """Raised when the directory cannot answer a membership question.

    The gate fails loud: an infrastructure failure must not be reported to the
    caller as "not authorized".
    """

    def __init__(self, group_key: str, message: str, error_code: str | None = None) -> None:
        super().__init__(message)
        self.group_key = group_key
        self.message = message
        self.error_code = error_code


def is_user_member_of_groups(user_key: str, groups_keys: list[str]) -> bool:
    """Check if a user is in the groups authorized to perform an action.

    Args:
        user_key: The user email. Compared case-insensitively.
        groups_keys: The group keys. Each can be a group email, alias, or ID.

    Returns:
        True if the user is a member of any of the groups, False otherwise.

    Raises:
        PermissionCheckError: when a group membership lookup fails.
    """
    log = logger.bind(operation="is_user_member_of_groups")
    directory = get_directory_provider()
    normalised_user_key = user_key.lower()

    for group_key in groups_keys:
        result = directory.get_group_members(group_key)
        if not result.is_success:
            log.error(
                "group_members_lookup_failed",
                group_key=group_key,
                error_code=result.error_code,
                error=result.message,
            )
            raise PermissionCheckError(group_key, result.message, result.error_code)
        if any(member.email == normalised_user_key for member in result.data or []):
            return True

    return False
