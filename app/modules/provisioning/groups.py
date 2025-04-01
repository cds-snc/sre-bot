from integrations.google_workspace import google_directory
from integrations.aws import identity_store
from utils import filters
from core.logging import get_module_logger


logger = get_module_logger()


def get_groups_from_integration(
    integration_source: str,
    pre_processing_filters: list = [],
    post_processing_filters: list = [],
    query: str | None = None,
    return_dataframe: bool = False,
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
        return_dataframe (bool, optional): Return the groups as a DataFrame. Defaults to False.

    Returns:
        list: A list of groups with members, empty list if no groups are found.
    """
    groups = []
    group_display_key = None
    members = None
    members_display_key = None
    integration_name = integration_source
    groups_dataframe = None
    match integration_source:
        case "google_groups":
            logger.info(
                "get_groups_from_integration_started",
                integration_source=integration_source,
                service="Google Groups",
                query=query,
            )
            groups = google_directory.list_groups_with_members(
                groups_filters=pre_processing_filters,
                query=query,
            )
            if return_dataframe:
                groups_dataframe = (
                    google_directory.convert_google_groups_members_to_dataframe(groups)
                )
            integration_name = "Google"
            group_display_key = "name"
            members = "members"
            members_display_key = "primaryEmail"
        case "aws_identity_center":
            logger.info(
                "get_groups_from_integration_started",
                integration_source=integration_source,
                service="AWS Identity Center",
            )
            groups = identity_store.list_groups_with_memberships(
                groups_filters=pre_processing_filters,
            )
            if return_dataframe:
                groups_dataframe = (
                    identity_store.convert_aws_groups_members_to_dataframe(groups)
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
    return groups_dataframe if groups_dataframe is not None else groups


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
    if not group_display_key:
        logger.warning(
            "log_groups_missing_display_key",
            integration_name=integration_name,
            missing_key="group_display_key",
        )
    if not members:
        logger.warning(
            "log_groups_missing_members_key",
            integration_name=integration_name,
            missing_key="members",
        )
    if not members_display_key:
        logger.warning(
            "log_groups_missing_display_key",
            integration_name=integration_name,
            missing_key="members_display_key",
        )

    logger.info(
        "log_groups_summary",
        integration_name=integration_name,
        groups_count=len(groups),
    )

    for group in groups:
        group_display_name = filters.get_nested_value(group, group_display_key)
        if not group_display_name:
            group_display_name = "<Group Name not found>"
        if group.get(members):
            logger.info(
                "log_group_members",
                integration_name=integration_name,
                group_name=group_display_name,
                members_count=len(group[members]),
            )
            for member in group[members]:
                members_display_name = filters.get_nested_value(
                    member, members_display_key
                )
                if not members_display_name:
                    members_display_name = "<User Name not found>"
                logger.info(
                    "log_group_member",
                    integration_name=integration_name,
                    group_name=group_display_name,
                    member_name=members_display_name,
                )
        else:
            logger.info(
                "log_group_no_members",
                integration_name=integration_name,
                group_name=group_display_name,
            )
