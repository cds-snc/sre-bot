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

from packages.oncall_sync.settings import OnCallRotation, OnCallScheduleConfig


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
    """Messaging-platform user groups that should mirror on-call membership."""

    def sync_user_group(
        self,
        rotation: OnCallRotation,
        on_call_email: str,
    ) -> None:
        """Ensure the rotation user group contains exactly ``on_call_email``.

        Implementations should be idempotent. Raise ``OnCallSyncError`` to
        signal a transport/permission failure that should be reported but
        should not abort the remaining rotations.
        """
        ...

    def sync_schedule_user_group(
        self,
        schedule: OnCallScheduleConfig,
        on_call_emails: Sequence[str],
    ) -> None:
        """Ensure the schedule aggregate group contains all ``on_call_emails``.

        Called once per schedule after all rotation groups have been
        successfully synced. Implementations should be idempotent. Raise
        ``OnCallSyncError`` to signal a transport/permission failure.
        """
        ...


class OnCallSyncError(Exception):
    """Raised by adapters and the service when a rotation fails to sync."""
