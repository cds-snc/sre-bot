"""Access Sync persistent run state repository.

Wraps ``StorageService`` to persist and retrieve ``SyncRunRecord`` objects.
Access Sync owns its key scheme and serialization; all DynamoDB I/O is
delegated to the infrastructure storage service.

Key scheme in ``sre_bot_access``:
    PK = ``SYNC_RUN#{platform}#{user_email}``
    SK = ``{created_at_iso}#{run_id}``

This allows efficient per-user, per-platform pagination (newest first via
``ScanIndexForward=False``).
"""

from datetime import UTC, datetime

import structlog

from infrastructure.storage.protocol import StorageService
from packages.access.sync.domain import SyncRunRecord

logger = structlog.get_logger()


class SyncRunRepository:
    """DynamoDB-backed repository for sync run records.

    Constructed once at startup in ``providers.py`` using the centralized
    ``StorageService`` singleton from ``infrastructure.storage``.

    Args:
        storage: Configured ``StorageService`` instance injected by provider.
    """

    TABLE = "sre_bot_access"

    def __init__(self, storage: StorageService) -> None:
        self._storage = storage

    def save(self, record: SyncRunRecord) -> None:
        """Persist a sync run record.  Failure is logged but not propagated."""
        sk = f"{record.created_at.isoformat()}#{record.run_id}"
        item = {
            "PK": f"SYNC_RUN#{record.platform}#{record.user_email}",
            "SK": sk,
            "run_id": record.run_id,
            "user_email": record.user_email,
            "platform": record.platform,
            "actions_applied": record.actions_applied,
            "status": record.status,
            "dry_run": record.dry_run,
            "request_id": record.request_id,
            "error_message": record.error_message,
            "created_at": record.created_at.isoformat(),
        }
        result = self._storage.put(self.TABLE, item)
        if not result.is_success:
            logger.error(
                "sync_run_save_failed",
                run_id=record.run_id,
                error=result.message,
            )

    def get_recent_runs(
        self,
        platform: str,
        user_email: str,
        limit: int = 10,
    ) -> list[SyncRunRecord]:
        """Return recent runs for the given platform + user, newest first."""
        pk = f"SYNC_RUN#{platform}#{user_email}"
        result = self._storage.query(
            self.TABLE,
            key_condition="PK = :pk",
            expression_values={":pk": pk},
            ScanIndexForward=False,
            Limit=limit,
        )
        if not result.is_success:
            logger.error(
                "sync_run_query_failed",
                platform=platform,
                user_email=user_email,
                error=result.message,
            )
            return []
        return [self._deserialize(item) for item in (result.data or [])]

    @staticmethod
    def _deserialize(item: dict) -> SyncRunRecord:
        created_raw: str | None = item.get("created_at")
        created_at = datetime.fromisoformat(created_raw) if created_raw else datetime.now(UTC)
        return SyncRunRecord(
            run_id=item.get("run_id", ""),
            user_email=item.get("user_email", ""),
            platform=item.get("platform", ""),
            actions_applied=list(item.get("actions_applied", [])),
            status=item.get("status", "success"),  # type: ignore[arg-type]
            dry_run=bool(item.get("dry_run", False)),
            request_id=item.get("request_id"),
            error_message=item.get("error_message"),
            created_at=created_at,
        )
