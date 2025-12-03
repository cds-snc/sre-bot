"""Test factories for groups command tests."""

from typing import Any, Dict, List, Optional
from infrastructure.commands import CommandContext


def make_groups_list_context(
    user_email: str = "test@example.com",
    user_id: str = "U12345",
    channel_id: str = "C12345",
    locale: str = "en-US",
    metadata: Optional[Dict[str, Any]] = None,
) -> CommandContext:
    """Create mock CommandContext for groups list command."""
    base_metadata = {
        "user_email": user_email,
        "user_id": user_id,
        "channel_id": channel_id,
    }
    if metadata:
        base_metadata.update(metadata)

    ctx = CommandContext(
        platform="slack",
        user_id=user_id,
        user_email=user_email,
        channel_id=channel_id,
        locale=locale,
        metadata=base_metadata,
    )
    return ctx


def make_groups_add_context(
    user_email: str = "requestor@example.com",
    user_id: str = "U12345",
    channel_id: str = "C12345",
    locale: str = "en-US",
) -> CommandContext:
    """Create mock CommandContext for groups add command."""
    return make_groups_list_context(
        user_email=user_email,
        user_id=user_id,
        channel_id=channel_id,
        locale=locale,
    )


def make_group_dict(
    group_id: str = "group-123",
    name: str = "Test Group",
    email: str = "test-group@example.com",
    members: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Create mock group dictionary."""
    return {
        "id": group_id,
        "name": name,
        "email": email,
        "members": members or [],
        "description": f"Test group {name}",
    }


def make_member_dict(
    email: str = "member@example.com",
    role: str = "MEMBER",
    user_id: str = "U67890",
) -> Dict[str, Any]:
    """Create mock member dictionary."""
    return {
        "email": email,
        "role": role,
        "id": user_id,
        "status": "ACTIVE",
    }


def make_add_member_request(
    group_id: str = "group-123",
    member_email: str = "member@example.com",
    provider: str = "google",
    requestor: str = "requestor@example.com",
    justification: str = "Test justification",
) -> Dict[str, Any]:
    """Create mock AddMemberRequest payload."""
    return {
        "group_id": group_id,
        "member_email": member_email,
        "provider": provider,
        "requestor": requestor,
        "justification": justification,
    }


def make_remove_member_request(
    group_id: str = "group-123",
    member_email: str = "member@example.com",
    provider: str = "google",
    requestor: str = "requestor@example.com",
    justification: str = "Test justification",
) -> Dict[str, Any]:
    """Create mock RemoveMemberRequest payload."""
    return {
        "group_id": group_id,
        "member_email": member_email,
        "provider": provider,
        "requestor": requestor,
        "justification": justification,
    }


def make_groups_list_with_members(
    count: int = 2,
    members_per_group: int = 3,
) -> List[Dict[str, Any]]:
    """Create mock list of groups with members."""
    groups = []
    for i in range(count):
        members = [
            make_member_dict(
                email=f"member{j}@example.com",
                role="MEMBER" if j > 0 else "MANAGER",
            )
            for j in range(members_per_group)
        ]
        groups.append(
            make_group_dict(
                group_id=f"group-{i}",
                name=f"Test Group {i}",
                members=members,
            )
        )
    return groups
