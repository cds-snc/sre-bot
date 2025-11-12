"""Core business logic - service and orchestration.

Note: imports are lazy to avoid circular dependencies.
"""

__all__ = [
    "add_member",
    "remove_member",
    "bulk_operations",
    "add_member_to_group",
    "remove_member_from_group",
    "list_groups_for_user",
]


def __getattr__(name: str):
    """Lazy import to avoid circular dependencies."""
    if name == "add_member":
        from modules.groups.core.service import add_member

        return add_member
    elif name == "remove_member":
        from modules.groups.core.service import remove_member

        return remove_member
    elif name == "bulk_operations":
        from modules.groups.core.service import bulk_operations

        return bulk_operations
    elif name == "add_member_to_group":
        from modules.groups.core.orchestration import add_member_to_group

        return add_member_to_group
    elif name == "remove_member_from_group":
        from modules.groups.core.orchestration import remove_member_from_group

        return remove_member_from_group
    elif name == "list_groups_for_user":
        from modules.groups.core.orchestration import list_groups_for_user

        return list_groups_for_user
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
