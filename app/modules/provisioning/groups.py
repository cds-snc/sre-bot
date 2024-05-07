from logging import getLogger
import re
from integrations.google_workspace import google_directory
from integrations.aws import identity_store
from utils import filters as filter_tools


logger = getLogger(__name__)


def get_groups_with_members_from_integration(integration_source, **kwargs):
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
    filters = kwargs.get("filters", [])
    query = kwargs.get("query", None)
    members_details = kwargs.get("members_details", True)

    groups = []
    match integration_source:
        case "google_groups":
            logger.info("Getting Google Groups with members.")
            groups = google_directory.list_groups_with_members(
                query=query, members_details=members_details
            )
        case "aws_identity_center":
            logger.info("Getting AWS Identity Center Groups with members.")
            groups = identity_store.list_groups_with_memberships(
                members_details=members_details
            )
        case _:
            return groups

    for filter in filters:
        groups = filter_tools.filter_by_condition(groups, filter)
    return groups


def preformat_groups(groups, lookup_key, new_key, pattern="", replace=""):
    for group in groups:
        if lookup_key not in group:
            raise KeyError(f"Group {group} does not have {lookup_key} key")
        group[new_key] = re.sub(pattern, replace, group[lookup_key])

    return groups
