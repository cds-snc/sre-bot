from integrations.google_workspace import google_directory
from integrations.aws import identity_store
from utils import filters as filter_tools


def get_groups_with_members_from_integration(integration_source, **kwargs):
    """Retrieve the users from an integration group source.
    Supported sources are:
    - Google Groups
    - AWS Identity Center (Identity Store)

    Args:
        integration_source (str): The source of the groups.
    """
    filters = kwargs.get("filters", [])
    query = kwargs.get("query", None)
    members_details = kwargs.get("members_details", True)

    groups = []
    match integration_source:
        case "google_groups":
            groups = google_directory.list_groups_with_members(
                query=query, members_details=members_details
            )
        case "aws_identity_center":
            groups = identity_store.list_groups_with_memberships(
                members_details=members_details
            )
        case _:
            return groups

    for filter in filters:
        groups = filter_tools.filter_by_condition(groups, filter)
    return groups
