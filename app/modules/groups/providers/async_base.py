# Currently not used, but kept as scaffold for future async group providers
from __future__ import annotations

from enum import Enum
from typing import Optional, Dict, Any
from dataclasses import dataclass
from abc import ABC, abstractmethod


class OperationStatus(Enum):
    SUCCESS = "success"
    TRANSIENT_ERROR = "transient_error"  # Retryable
    PERMANENT_ERROR = "permanent_error"  # Do not retry
    UNAUTHORIZED = "unauthorized"
    NOT_FOUND = "not_found"


@dataclass
class OperationResult:
    """Uniform result returned from async provider operations."""

    status: OperationStatus
    message: str
    data: Optional[Dict[str, Any]] = None
    error_code: Optional[str] = None
    retry_after: Optional[int] = None  # Seconds for rate limiting


@dataclass
class ProviderCapabilities:
    supports_group_creation: bool = False
    supports_group_deletion: bool = False
    supports_member_management: bool = True
    supports_batch_operations: bool = False
    max_batch_size: int = 1


class AsyncGroupProvider(ABC):
    """Abstract Base Class for async group providers.

    All methods are async and return OperationResult.
    Implementations MUST remain stateless (no per-request mutable attrs).
    """

    @property
    @abstractmethod
    def capabilities(self) -> ProviderCapabilities:
        """Provider capability descriptor (read-only)."""
        pass

    @abstractmethod
    async def list_groups_for_user(self, user_email: str) -> OperationResult:
        """Return OperationResult with canonical group dicts the user can manage."""
        raise NotImplementedError()

    @abstractmethod
    async def add_member(
        self, group_id: str, member: dict | str, justification: str
    ) -> OperationResult:
        """Add a member and return OperationResult with canonical member dict."""
        raise NotImplementedError()

    @abstractmethod
    async def remove_member(
        self, group_id: str, member: dict | str, justification: str
    ) -> OperationResult:
        """Remove a member and return OperationResult with canonical member dict."""
        raise NotImplementedError()

    @abstractmethod
    async def get_group_members(self, group_id: str, **kwargs) -> OperationResult:
        """Return OperationResult with canonical member dicts."""
        raise NotImplementedError()

    @abstractmethod
    async def validate_permissions(
        self, user_email: str, group_id: str, action: str
    ) -> OperationResult:
        """Validate permissions and return OperationResult (data: bool)."""
        raise NotImplementedError()

    async def create_group(self, *args, **kwargs):
        """Explicitly disabled - groups managed via IaC"""
        raise NotImplementedError("Group creation disabled - managed via IaC")

    async def delete_group(self, *args, **kwargs):
        """Explicitly disabled - groups managed via IaC"""
        raise NotImplementedError("Group deletion disabled - managed via IaC")
