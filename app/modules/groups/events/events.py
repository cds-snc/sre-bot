"""Groups module specific events.

Defines group-specific event types that extend the infrastructure Event class.
"""

from dataclasses import dataclass, field

from infrastructure.events import Event


@dataclass
class GroupMemberEvent(Event):
    """Base class for group member events."""

    event_type: str = ""
    group_id: str = ""
    member_email: str = ""


@dataclass
class GroupMemberAddedEvent(GroupMemberEvent):
    """Event fired when a member is added to a group."""

    event_type: str = field(default="group.member.added", init=False)


@dataclass
class GroupMemberRemovedEvent(GroupMemberEvent):
    """Event fired when a member is removed from a group."""

    event_type: str = field(default="group.member.removed", init=False)
