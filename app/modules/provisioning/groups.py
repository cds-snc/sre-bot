from logging import getLogger
from integrations.google_workspace import google_directory
from integrations.aws import identity_store
from utils import filters


logger = getLogger(__name__)


def get_groups_from_integration(integration_source, **kwargs):
    """Retrieve the users from an integration group source.
    Supported sources are:
    - Google Groups
    - AWS Identity Center (Identity Store)

    Args:
        integration_source (str): The source of the groups.
        **kwargs: Additional keyword arguments. Supported arguments are:

            - `filters` (list): List of filters to apply to the groups.
            - `query` (str): The query to search for groups.
            - `members_details` (bool): Include the members details in the groups.

    Returns:
        list: A list of groups with members, empty list if no groups are found.
    """
    processing_filters = kwargs.get("processing_filters", [])
    query = kwargs.get("query", None)
    members_details = kwargs.get("members_details", True)

    groups = []
    group_display_key = None
    members = None
    members_display_key = None
    integration_name = integration_source
    match integration_source:
        case "google_groups":
            logger.info("Getting Google Groups with members.")
            groups = google_directory.list_groups_with_members(
                query=query, members_details=members_details
            )
            integration_name = "Google"
            group_display_key = "name"
            members = "members"
            members_display_key = "primaryEmail"
        case "aws_identity_center":
            logger.info("Getting AWS Identity Center Groups with members.")
            groups = identity_store.list_groups_with_memberships(
                members_details=members_details
            )
            integration_name = "AWS"
            group_display_key = "DisplayName"
            members = "GroupMemberships"
            members_display_key = "MemberId.UserName"
        case _:
            return groups

    for filter in processing_filters:
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
    integration_name="Unspecified",
):
    """Log the groups information.

    Args:
        groups (list): The list of groups to log.
        group_display_key (str, optional): The key to display in the logs. Defaults to None.
    """
    logger.info(f"{integration_name}:Found {len(groups)} groups")
    for group in groups:
        group_display_name = filters.get_nested_value(group, group_display_key)
        if group.get(members):
            logger.info(
                f"{integration_name}:Group: {group_display_name} has {len(group[members])} members"
            )
            for member in group[members]:
                members_display_name = filters.get_nested_value(
                    member, members_display_key
                )
                logger.info(f"{integration_name}:Group:Member: {members_display_name}")
        else:
            logger.info(
                f"{integration_name}:Group: {group_display_name} has no members"
            )


def list_groups_with_members(
    list_groups_function,
    list_group_members_function,
    get_member_details_function,
    **kwargs,
):
    """Get the groups and their members from the integration.

    Args:
        list_groups_function (function): The function to list the groups.
        list_groups_members_function (function): The function to list the groups members.
        get_member_details_function (function): The function to get the member details.
        **kwargs: Additional keyword arguments. Supported arguments are:

            - `filters` (list): List of filters to apply to the groups.
            - `query` (str): The query to search for groups.
            - `members_details` (bool): Include the members details in the groups.

    Returns:
        list: A list of groups with members, empty list if no groups are found.
    """
    get_members_details = kwargs.pop("get_members_details", True)
    groups_filters = kwargs.pop("groups_filters", [])
    list_group_members_params = kwargs.pop("list_group_members_params", {})
    members_filters = kwargs.pop("members_filters", [])
    get_member_details_params = kwargs.pop("get_member_details_params", {})
    groups = list_groups_function(**kwargs)
    if not groups or list_group_members_params is False:
        return []

    for group_filter in groups_filters:
        groups = filters.filter_by_condition(groups, group_filter)

    for group in range(len(groups)):
        members = list_group_members_function(group, list_group_members_params)
        for member_filter in members_filters:
            members = filters.filter_by_condition(members, member_filter)

        if members and get_members_details:
            for member in range(len(members)):
                members[member] = get_member_details_function(get_member_details_params)
            groups[group]["members"] = members
        else:
            groups[group]["members"] = []
