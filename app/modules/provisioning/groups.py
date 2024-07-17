from logging import getLogger
from integrations.google_workspace import google_directory
from integrations.aws import identity_store
from utils import filters


logger = getLogger(__name__)


def get_groups_from_integration(
    integration_source: str,
    pre_processing_filters: list = [],
    post_processing_filters: list = [],
    query: str | None = None,
    members_details: bool = True,
) -> list:
    """Retrieve the users from an integration group source.
    Supported sources are:
    - Google Groups
    - AWS Identity Center (Identity Store)

    Args:
        integration_source (str): The source of the groups.
        pre_processing_filters (list): List of filters to apply directly after the groups are retrieved, before processing members.
        post_processing_filters (list): List of filters to apply to the groups after processing members (optional).
        query (str): The query to search for groups (only supported by Google Groups).
        members_details (bool): Include the members details in the groups.

    Returns:
        list: A list of groups with members, empty list if no groups are found.
    """
    groups = []
    group_display_key = None
    members = None
    members_display_key = None
    integration_name = integration_source
    match integration_source:
        case "google_groups":
            logger.info("Getting Google Groups with members.")
            groups = google_directory.list_groups_with_members(
                query=query,
                members_details=members_details,
                groups_filters=pre_processing_filters,
            )
            integration_name = "Google:"
            group_display_key = "name"
            members = "members"
            members_display_key = "primaryEmail"
        case "aws_identity_center":
            logger.info("Getting AWS Identity Center Groups with members.")
            groups = identity_store.list_groups_with_memberships(
                members_details=members_details,
                groups_filters=pre_processing_filters,
            )
            integration_name = "AWS:"
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
    integration_name="",
):
    """Log the groups information.

    Args:
        groups (list): The list of groups to log.
        group_display_key (str, optional): The key to display in the logs. Defaults to None.
    """
    if not group_display_key:
        logger.warning(f"{integration_name}No group display key provided.")
    if not members:
        logger.warning(f"{integration_name}No members key provided.")
    if not members_display_key:
        logger.warning(f"{integration_name}No members display key provided.")

    logger.info(f"{integration_name}Found {len(groups)} groups")
    for group in groups:
        group_display_name = filters.get_nested_value(group, group_display_key)
        if not group_display_name:
            group_display_name = "<Group Name not found>"
        if group.get(members):
            logger.info(
                f"{integration_name}Group: {group_display_name} has {len(group[members])} members"
            )
            for member in group[members]:
                members_display_name = filters.get_nested_value(
                    member, members_display_key
                )
                if not members_display_name:
                    members_display_name = "<User Name not found>"
                logger.info(f"{integration_name}Group:Member: {members_display_name}")
        else:
            logger.info(
                f"{integration_name}Group: {group_display_name} has no members."
            )
