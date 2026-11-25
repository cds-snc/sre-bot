"""The attendee directory over the incident conversation's platform accounts.

Reads each account's profile email through ``IncidentConversation.account_emails``,
tolerated until the people capability links accounts (decisions/people-and-accounts.md).

TODO(TASK-83.10): resolve attendees through the people capability, keeping this adapter
as the explicit fallback.
"""

from collections.abc import Mapping, Sequence

from contracts.operations.result import OperationResult
from features.incident.core.api import ConversationReference, IncidentConversation


class ConversationAttendeeDirectory:
    """``AttendeeDirectory`` answering from the conversation platform's account profiles."""

    def __init__(self, conversations: IncidentConversation) -> None:
        self._conversations = conversations

    async def emails_for(
        self, conversation: ConversationReference, account_ids: Sequence[str]
    ) -> OperationResult[Mapping[str, str | None]]:
        """Return the platform's email of each account; ``None`` for an account without one."""
        return await self._conversations.account_emails(conversation, account_ids)
