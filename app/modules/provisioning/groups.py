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


def get_matching_groups(source_groups, target_groups, matching_key):
    """Get the groups that match between the source and target groups.
    The function compares the groups in the source and target lists and returns the groups that match between them.

    Args:
        source_groups (list): A list containing the source groups data.
        target_groups (list): A list containing the target groups data.
        matching_key (str): The key to match between the source and target groups. For better performance, avoid using nested keys when possible.

    Returns:
        list: A list of groups that match between the source and target groups.
    """

    if not source_groups or not target_groups:
        return [], []

    source_values = {}
    for group in source_groups:
        value = filter_tools.get_nested_value(group, matching_key)
        if value is not None:
            source_values[value] = group

    target_values = {}
    for group in target_groups:
        value = filter_tools.get_nested_value(group, matching_key)
        if value is not None:
            target_values[value] = group

    if not source_values or not target_values:
        return [], []

    matching_values = set(source_values.keys()) & set(target_values.keys())

    filtered_source_groups = [source_values[value] for value in matching_values]
    filtered_target_groups = [target_values[value] for value in matching_values]

    return filtered_source_groups, filtered_target_groups