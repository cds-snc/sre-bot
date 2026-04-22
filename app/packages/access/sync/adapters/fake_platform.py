"""In-memory fake Access Sync adapter for local and unit testing.

Provides deterministic sample responses for a non-AWS platform to validate
cross-provider orchestration paths (registry wiring, plan/apply flows, and
batch membership reads) without external API dependencies.
"""

from typing import Dict, Set

from infrastructure.operations import OperationResult, OperationStatus
from packages.access.sync.domain import AdapterAssessment, DesiredUserState
from packages.access.sync.policies import AdapterCapabilities


class FakePlatformAdapter:
    """Simple fake platform adapter with sample users and group memberships."""

    def __init__(self) -> None:
        self._users: Set[str] = {
            "alice@example.com",
            "bob@example.com",
            "carol@example.com",
        }
        self._disabled: Set[str] = set()
        self._members_by_group: Dict[str, Set[str]] = {
            "fake-group-admin": {"alice@example.com", "carol@example.com"},
            "fake-group-read": {"bob@example.com"},
        }

    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            supports_disable=True,
            supports_delete=True,
            supported_entitlement_types={"group"},
            supports_bulk_user_delta=True,
        )

    def ensure_user(self, user_email: str) -> OperationResult:
        normalized = user_email.lower()
        self._users.add(normalized)
        self._disabled.discard(normalized)
        return OperationResult.success(data={"user_id": f"fake-{normalized}"})

    def disable_user(self, user_email: str) -> OperationResult:
        normalized = user_email.lower()
        if normalized not in self._users:
            return OperationResult.success(message="user_already_absent")
        self._disabled.add(normalized)
        return OperationResult.success(message="user_disabled")

    def remove_user(self, user_email: str) -> OperationResult:
        normalized = user_email.lower()
        self._users.discard(normalized)
        self._disabled.discard(normalized)
        for members in self._members_by_group.values():
            members.discard(normalized)
        return OperationResult.success(message="user_removed")

    def apply_entitlement(
        self,
        user_email: str,
        entitlement_type: str,
        entitlement_id: str,
    ) -> OperationResult:
        normalized = user_email.lower()
        if entitlement_type != "group":
            return OperationResult.error(
                OperationStatus.PERMANENT_ERROR,
                message=f"Unsupported entitlement_type: {entitlement_type}",
                error_code="UNSUPPORTED_ENTITLEMENT_TYPE",
            )
        self._users.add(normalized)
        members = self._members_by_group.setdefault(entitlement_id, set())
        members.add(normalized)
        return OperationResult.success(message="entitlement_applied")

    def remove_entitlement(
        self,
        user_email: str,
        entitlement_type: str,
        entitlement_id: str,
    ) -> OperationResult:
        normalized = user_email.lower()
        if entitlement_type != "group":
            return OperationResult.error(
                OperationStatus.PERMANENT_ERROR,
                message=f"Unsupported entitlement_type: {entitlement_type}",
                error_code="UNSUPPORTED_ENTITLEMENT_TYPE",
            )
        members = self._members_by_group.get(entitlement_id, set())
        members.discard(normalized)
        return OperationResult.success(message="entitlement_removed")

    def _fetch_current_state(self, user_email: str) -> OperationResult:
        normalized = user_email.lower()
        if normalized not in self._users:
            return OperationResult.error(
                OperationStatus.NOT_FOUND,
                message=f"User not found: {normalized}",
                error_code="USER_NOT_FOUND",
            )
        group_ids = sorted(
            group_id
            for group_id, members in self._members_by_group.items()
            if normalized in members
        )
        return OperationResult.success(
            data={
                "user_id": f"fake-{normalized}",
                "group_ids": group_ids,
            }
        )

    def get_current_entitlement_ids(self, user_email: str) -> OperationResult:
        state = self._fetch_current_state(user_email)
        if not state.is_success:
            return state
        group_ids = state.data.get("group_ids", []) if state.data else []
        return OperationResult.success(data=set(group_ids))

    def list_all_provisioned_users(self) -> OperationResult:
        return OperationResult.success(data=set(self._users))

    def list_group_members(self, group_id: str) -> OperationResult:
        members = self._members_by_group.get(group_id, set())
        return OperationResult.success(data=set(members))

    def list_members_for_groups(self, group_ids: Set[str]) -> OperationResult:
        mapping = {
            group_id: set(self._members_by_group.get(group_id, set()))
            for group_id in group_ids
        }
        return OperationResult.success(data=mapping)

    def assess(
        self,
        user_email: str,
        desired_state: DesiredUserState,
    ) -> OperationResult:
        """Assess current platform state for the user.

        Uses pre-fetched state when available (batch sync path); otherwise
        performs a live platform read.
        """
        if desired_state.current_entitlement_ids is not None:
            current_ids: Set[str] = {
                v for v in desired_state.current_entitlement_ids if isinstance(v, str)
            }
            if desired_state.platform_user_exists is not None:
                platform_user_exists = desired_state.platform_user_exists
            else:
                platform_user_exists = bool(current_ids)
            return OperationResult.success(
                data=AdapterAssessment(
                    platform_user_exists=platform_user_exists,
                    current_entitlement_ids=current_ids,
                )
            )

        state = self._fetch_current_state(user_email)
        if not state.is_success:
            if state.status == OperationStatus.NOT_FOUND:
                return OperationResult.success(
                    data=AdapterAssessment(
                        platform_user_exists=False,
                        current_entitlement_ids=set(),
                    )
                )
            return state

        group_ids: Set[str] = set((state.data or {}).get("group_ids", []))
        return OperationResult.success(
            data=AdapterAssessment(
                platform_user_exists=True,
                current_entitlement_ids=group_ids,
            )
        )
