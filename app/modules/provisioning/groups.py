from structlog import get_logger

from infrastructure.directory import get_directory_provider
from infrastructure.directory.models import DirectoryGroupWithMembers, DirectoryUser
from integrations.aws import identity_store
from modules.provisioning import users
from utils import filters

logger = get_logger()


class DirectoryGroupsUnavailableError(Exception):
    """Raised when a directory provider cannot supply the group list."""

    def __init__(self, message: str, error_code: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.error_code = error_code


def _google_groups_to_legacy_shape(
    provider_groups: tuple[DirectoryGroupWithMembers, ...],
    directory_users: list[DirectoryUser],
    log,
) -> list[dict]:
    user_by_email = {user.email.lower(): user for user in directory_users}
    legacy_groups: list[dict] = []

    for provider_group in provider_groups:
        resolved_members: list[dict] = []
        for member in provider_group.members:
            member_email = (member.email or "").lower()
            matched_user = user_by_email.get(member_email)
            if matched_user is None:
                log.warning(
                    "google_group_member_unresolved",
                    group_email=provider_group.group.group_email,
                    member_email=member_email,
                )
                continue
            resolved_members.append(
                {
                    "primaryEmail": matched_user.email,
                    "email": matched_user.email,
                    "name": {
                        "givenName": matched_user.given_name or "",
                        "familyName": matched_user.family_name or "",
                    },
                }
            )

        if not resolved_members:
            log.warning(
                "google_group_dropped_no_resolvable_members",
                group_email=provider_group.group.group_email,
            )
            continue

        legacy_groups.append(
            {
                "email": provider_group.group.group_email,
                "name": provider_group.group.name or "",
                "members": resolved_members,
            }
        )

    return legacy_groups


def get_groups_from_integration(
    integration_source: str,
    pre_processing_filters: list | None = None,
    post_processing_filters: list | None = None,
    query: str | None = None,
) -> list:
    """Retrieve the users from an integration group source.
    Supported sources are:
    - Google Groups
    - AWS Identity Center (Identity Store)

    Args:
        integration_source (str): The integration source to get the groups from.
        pre_processing_filters (list, optional): A list of filters to apply before processing the groups. Defaults to [].
        post_processing_filters (list, optional): A list of filters to apply after processing the groups. Defaults to [].
        query (str, optional): A query to filter the groups. Defaults to None.

    Returns:
        list: A list of groups with members, empty list if no groups are found.
    """
    log = logger.bind(
        integration=integration_source,
        operation="get_groups_from_integration",
    )
    if pre_processing_filters is None:
        pre_processing_filters = []
    if post_processing_filters is None:
        post_processing_filters = []
    groups = []
    group_display_key = None
    members = None
    members_display_key = None
    integration_name = integration_source
    match integration_source:
        case "google_groups":
            log.info(
                "get_groups_from_integration_started",
                service="Google Groups",
                query=query,
            )
            result = get_directory_provider().list_groups_with_members(query=query or "")
            if not result.is_success:
                log.error(
                    "list_groups_with_members_failed",
                    error_code=result.error_code,
                    error=result.message,
                )
                raise DirectoryGroupsUnavailableError(result.message, result.error_code)

            if result.data is not None:
                for failure in result.data.failures:
                    log.warning(
                        "google_group_list_failed",
                        group_email=failure.group_email,
                        status=failure.status.name,
                        error_code=failure.error_code,
                        message=failure.message,
                    )

                directory_users = users.get_users_from_integration("google_directory")
                groups = _google_groups_to_legacy_shape(result.data.groups, directory_users, log)
                for filter in pre_processing_filters:
                    groups = filters.filter_by_condition(groups, filter)
            integration_name = "Google"
            group_display_key = "name"
            members = "members"
            members_display_key = "primaryEmail"
        case "aws_identity_center":
            log.info(
                "get_groups_from_integration_started",
                service="AWS Identity Center",
            )
            groups = identity_store.list_groups_with_memberships(
                groups_filters=pre_processing_filters,
            )
            integration_name = "AWS"
            group_display_key = "DisplayName"
            members = "GroupMemberships"
            members_display_key = "MemberId.UserName"
        case _:
            return groups

    for filter in post_processing_filters:
        groups = filters.filter_by_condition(groups, filter)

    log_groups(
        groups,
        group_display_key=group_display_key,
        members=members,
        members_display_key=members_display_key,
        integration_name=integration_name,
    )
    return groups


def log_groups(
    groups,
    group_display_key=None,
    members=None,
    members_display_key=None,
    integration_name="No Integration Name Provided",
):
    """Log the groups information.

    Args:
        groups (list): The list of groups to log.
        group_display_key (str, optional): The key to display in the logs. Defaults to None.
    """
    log = logger.bind(
        integration=integration_name,
        operation="log_groups",
    )
    if not group_display_key:
        log.warning(
            "log_groups_missing_display_key",
            missing_key="group_display_key",
        )
    if not members:
        log.warning(
            "log_groups_missing_members_key",
            missing_key="members",
        )
    if not members_display_key:
        log.warning(
            "log_groups_missing_display_key",
            missing_key="members_display_key",
        )

    log.info(
        "log_groups_summary",
        groups_count=len(groups),
    )

    for group in groups:
        group_display_name = filters.get_nested_value(group, group_display_key)
        if not group_display_name:
            group_display_name = "<Group Name not found>"
        if group.get(members):
            log.info(
                "log_group_members",
                group_name=group_display_name,
                members_count=len(group[members]),
            )
            for member in group[members]:
                members_display_name = filters.get_nested_value(member, members_display_key)
                if not members_display_name:
                    members_display_name = "<User Name not found>"
                log.info(
                    "log_group_member",
                    group_name=group_display_name,
                    member_name=members_display_name,
                )
        else:
            log.info(
                "log_group_no_members",
                group_name=group_display_name,
            )
