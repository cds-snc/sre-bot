from integrations.google_workspace import google_directory


def is_user_member_of_groups(user_key, groups_keys):
    """Check if a user is in the groups authorized to perform an action.

    Args:
        user_key (str): The user email.
        group_key (list): The list of group IDs. This can be the group email, group alias, or group ID.
    Returns:
        bool: True if the user is in the groups, False otherwise.
    """
    users = []
    for group_key in groups_keys:
        group_members = google_directory.list_group_members(group_key)
        if not group_members:
            continue
        users.extend(group_members)
    return any(user["email"] == user_key for user in users)


def get_authorizers_from_groups(groups_keys):
    """Get the list of authorizers from the groups.

    Args:
        group_key (list): The list of group IDs. This can be the group email, group alias, or group ID.
    Returns:
        list: The list of authorizers.
    """
    authorizers = []
    for group_key in groups_keys:
        group_members = google_directory.list_group_members(group_key)
        if not group_members:
            continue
        authorizers.extend(group_members)
    return [authorizer["email"] for authorizer in authorizers]
