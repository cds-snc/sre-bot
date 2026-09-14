"""Platform-neutral contracts for the on-call sync feature.

The core sync orchestrator depends only on these protocols, not on any
concrete vendor SDK. Concrete adapters live under ``adapters/`` and are
selected by ``providers.py``. Adding a new on-call source (e.g. JSM) or a
new messaging target (e.g. MS Teams) means implementing one of these
protocols and wiring it in the provider — no changes to ``service.py``.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from packages.oncall_sync.settings import OnCallRotation
from packages.user_rotations.service import CurrentUserRotation


class OnCallScheduleProvider(Protocol):
    """Source of truth for the current on-call user of a rotation."""

    def get_current_on_call_email(self, rotation: OnCallRotation) -> str | None:
        """Return the email of the user currently on-call for ``rotation``.

        Return ``None`` when the rotation has no current participant
        (gap in coverage, or rotation not found). Raise ``OnCallSyncError``
        on transport/parse failures.
        """
        ...


class UserGroupSyncTarget(Protocol):
    """Messaging-platform user group that should mirror on-call membership."""

    def sync_user_group(
        self,
        handle: str,
        name: str,
        description: str,
        emails: Sequence[str],
    ) -> None:
        """Ensure the user group identified by ``handle`` contains exactly ``emails``.

        Implementations should be idempotent. Raise ``OnCallSyncError`` to
        signal a transport/permission failure that should be reported but
        should not abort the remaining syncs.
        """
        ...

    def sync_user_group_ids(
        self,
        handle: str,
        name: str,
        description: str,
        user_ids: Sequence[str],
    ) -> None:
        """Ensure a user group contains exactly the supplied Slack user IDs."""
        ...


class UserRotationsProvider(Protocol):
    """Source of current assignments from self-managed user rotations."""

    def get_current_rotations(self) -> Sequence[CurrentUserRotation]:
        """Return each self-managed rotation with its current Slack user ID."""
        ...


class OnCallSyncError(Exception):
    """Raised by adapters and the service when a rotation fails to sync."""
