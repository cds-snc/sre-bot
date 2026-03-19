"""Access Sync domain-specific result types.

Business-level result types for access sync operations. These are distinct from
OperationResult, which is reserved for external API integration outcomes.

AccessSyncResult represents the *business outcome* of applying access policy
logic, including whether human review is required for compliance or unsupported
operations.

See: docs/decisions/tier-1-foundation/06-operation-result-pattern.md
  "This pattern is used selectively at integration boundaries only"
"""

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class AccessSyncResult:
    """Domain-level result of an access sync operation.

    Represents the business outcome of applying access policy, distinct from
    the success/failure of external API calls (which OperationResult handles).

    Attributes:
        success: Whether the sync operation fully completed.
        applied_actions: List of action names successfully applied.
        requires_manual_action: True if operation completed but human review needed
            (e.g., AWS IC disable unsupported, compliance rules require review).
        message: Human-friendly summary of the result.
        error_message: Optional error details if success=False.
        error_code: Optional machine-readable error code (for compatibility with
            OperationResult in error cases).
        status: Internal status for persistence ("success", "manual_action_required",
            "failed"). Not returned externally; for internal state tracking only.
    """

    success: bool
    applied_actions: List[str]
    requires_manual_action: bool = False
    message: str = "ok"
    error_message: Optional[str] = None
    error_code: Optional[str] = None
    status: str = "success"  # "success", "manual_action_required", "failed"

    @property
    def is_complete(self) -> bool:
        """True if operation fully completed (regardless of manual action requirement).

        Returns:
            True if success or requires_manual_action; False if failed.
        """
        return self.success or self.requires_manual_action

    @property
    def is_success(self) -> bool:
        """Alias for success field for backwards compatibility with OperationResult.

        Returns:
            True if success=True, False otherwise.
        """
        return self.success
