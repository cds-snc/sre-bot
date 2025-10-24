import asyncio

from modules.groups.errors import IntegrationError
from modules.groups.providers.async_base import (
    AsyncGroupProvider,
    ProviderCapabilities,
    OperationResult,
    OperationStatus,
)
from modules.groups.providers.aws_identity_center import AwsIdentityCenterProvider


class AwsIdentityCenterAsyncProvider(AsyncGroupProvider):
    """Async wrapper provider for AWS Identity Center.

    This class implements the AsyncGroupProvider interface and delegates to the
    existing `AwsIdentityCenterProvider` sync helpers using `asyncio.to_thread`.

    It's intentionally not registered automatically by `register_provider` to
    avoid replacing the legacy sync provider until the registry is updated to
    accept AsyncGroupProvider instances. Register explicitly later when the
    application is ready to consume async providers.
    """

    def __init__(self):
        # reuse the sync provider's logic for now
        self._sync = AwsIdentityCenterProvider()
        self._capabilities = ProviderCapabilities(supports_member_management=True)

    @property
    def capabilities(self) -> ProviderCapabilities:
        return self._capabilities

    async def list_group_members(self, group_key: str) -> OperationResult:
        try:
            members = await asyncio.to_thread(
                self._sync.get_group_members_sync, group_key
            )
            return OperationResult(
                status=OperationStatus.SUCCESS,
                message="ok",
                data={"members": members},
            )
        except IntegrationError as ie:
            return OperationResult(
                status=OperationStatus.PERMANENT_ERROR,
                message=str(ie),
                data={"response": getattr(ie, "response", None)},
            )
        except Exception as e:
            return OperationResult(
                status=OperationStatus.TRANSIENT_ERROR, message=str(e)
            )

    async def add_group_member(
        self, group_key: str, member_id: str, **metadata
    ) -> OperationResult:
        try:
            justification = metadata.get("justification", "")
            member = await asyncio.to_thread(
                self._sync.add_member_sync,
                group_key,
                {"email": member_id},
                justification,
            )
            return OperationResult(
                status=OperationStatus.SUCCESS,
                message="ok",
                data={"member": member or {}},
            )
        except IntegrationError as ie:
            return OperationResult(
                status=OperationStatus.PERMANENT_ERROR,
                message=str(ie),
                data={"response": getattr(ie, "response", None)},
            )
        except Exception as e:
            return OperationResult(
                status=OperationStatus.TRANSIENT_ERROR, message=str(e)
            )

    async def remove_group_member(
        self, group_key: str, member_id: str, **metadata
    ) -> OperationResult:
        try:
            justification = metadata.get("justification", "")
            member = await asyncio.to_thread(
                self._sync.remove_member_sync,
                group_key,
                {"email": member_id},
                justification,
            )
            return OperationResult(
                status=OperationStatus.SUCCESS,
                message="ok",
                data={"member": member or {}},
            )
        except IntegrationError as ie:
            return OperationResult(
                status=OperationStatus.PERMANENT_ERROR,
                message=str(ie),
                data={"response": getattr(ie, "response", None)},
            )
        except Exception as e:
            return OperationResult(
                status=OperationStatus.TRANSIENT_ERROR, message=str(e)
            )

    async def validate_permissions(
        self, user_email: str, group_id: str, action: str
    ) -> OperationResult:
        try:
            ok = await asyncio.to_thread(
                self._sync.validate_permissions_sync, user_email, group_id, action
            )
            return OperationResult(
                status=OperationStatus.SUCCESS,
                message="ok",
                data={"result": bool(ok)},
            )
        except Exception as e:
            return OperationResult(
                status=OperationStatus.TRANSIENT_ERROR, message=str(e)
            )
