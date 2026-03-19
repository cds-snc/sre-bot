"""Access Sync persistent run state store.

Stores sync run records and reconciliation checkpoints for audit trails and
drift detection.  This is a v1 stub — a production implementation would
persist to DynamoDB via the centralized AWSClients service.

Each sync operation should write a SyncRunRecord so operators can review
what actions were taken, when, and with what result.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Literal, Optional, Protocol


@dataclass
class SyncRunRecord:
    """Record of a single sync operation for one user + platform."""

    run_id: str
    user_email: str
    platform: str
    actions_applied: List[str]
    status: Literal["success", "partial", "failed", "manual_action_required"]
    dry_run: bool = False
    request_id: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class SyncRunStore(Protocol):
    """Contract for sync run persistence backends."""

    def save_run(self, record: SyncRunRecord) -> None:
        """Persist a sync run record."""
        ...

    def get_recent_runs(
        self,
        platform: str,
        user_email: str,
        limit: int = 10,
    ) -> List[SyncRunRecord]:
        """Return recent runs for the given platform + user, newest first."""
        ...


class InMemorySyncRunStore:
    """In-memory SyncRunStore for local development and testing.

    Not suitable for production — data is lost on restart.
    """

    def __init__(self) -> None:
        self._records: List[SyncRunRecord] = []

    def save_run(self, record: SyncRunRecord) -> None:
        self._records.append(record)

    def get_recent_runs(
        self,
        platform: str,
        user_email: str,
        limit: int = 10,
    ) -> List[SyncRunRecord]:
        matching = [
            r
            for r in reversed(self._records)
            if r.platform == platform and r.user_email == user_email
        ]
        return matching[:limit]
