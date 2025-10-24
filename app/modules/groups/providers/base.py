from __future__ import annotations

from enum import Enum
from typing import Optional, Dict, Any
from dataclasses import dataclass
from abc import ABC, abstractmethod
from core.config import settings


class OperationStatus(Enum):
    SUCCESS = "success"
    TRANSIENT_ERROR = "transient_error"  # Retryable
    PERMANENT_ERROR = "permanent_error"  # Do not retry
    UNAUTHORIZED = "unauthorized"
    NOT_FOUND = "not_found"


@dataclass
class OperationResult:
    """Uniform result returned from provider operations.

    status: OperationStatus -- high-level outcome
    message: str -- human-friendly message (for logs/troubleshooting)
    data: Optional[Dict[str, Any]] -- optional payload
    error_code: Optional[str] -- optional machine error code
    retry_after: Optional[int] -- seconds until retry when rate-limited
    """

    status: OperationStatus
    message: str
    data: Optional[Dict[str, Any]] = None
    error_code: Optional[str] = None
    retry_after: Optional[int] = None  # Seconds for rate limiting


@dataclass
class ProviderCapabilities:
    supports_user_creation: bool = False
    supports_user_deletion: bool = False
    supports_group_creation: bool = False  # Should always be False
    supports_group_deletion: bool = False  # Should always be False
    supports_member_management: bool = True
    # Whether the provider exposes role information (e.g., Google can indicate MANAGER)
    provides_role_info: bool = False
    supports_batch_operations: bool = False
    max_batch_size: int = 1

    @classmethod
    def from_config(cls, provider_name: str) -> "ProviderCapabilities":
        cfg = getattr(settings, "groups", None)
        if not cfg:
            return cls()
        provider_cfg = (
            cfg.providers.get(provider_name, {})
            if isinstance(cfg.providers, dict)
            else {}
        )
        return cls(
            supports_user_creation=provider_cfg.get("capabilities", {}).get(
                "supports_user_creation", False
            ),
            supports_user_deletion=provider_cfg.get("capabilities", {}).get(
                "supports_user_deletion", False
            ),
            supports_group_creation=provider_cfg.get("capabilities", {}).get(
                "supports_group_creation", False
            ),
            supports_group_deletion=provider_cfg.get("capabilities", {}).get(
                "supports_group_deletion", False
            ),
            supports_member_management=provider_cfg.get("capabilities", {}).get(
                "supports_member_management", True
            ),
            provides_role_info=provider_cfg.get("capabilities", {}).get(
                "provides_role_info", False
            ),
            supports_batch_operations=provider_cfg.get("capabilities", {}).get(
                "supports_batch_operations", False
            ),
            max_batch_size=provider_cfg.get("capabilities", {}).get(
                "max_batch_size", 1
            ),
        )


def opresult_wrapper(data_key=None):
    """Decorator to wrap a method call in an OperationResult."""

    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                result = func(*args, **kwargs)
                data = {data_key: result} if data_key else result
                return OperationResult(
                    status=OperationStatus.SUCCESS, message="ok", data=data
                )
            except Exception as e:
                return OperationResult(
                    status=OperationStatus.TRANSIENT_ERROR, message=str(e)
                )

        return wrapper

    return decorator


class GroupProvider(ABC):
    """Abstract Base Class for group providers.

    Providers are required to implement synchronous (sync) methods.
    All operations should be stateless and thread-safe.
    Implementations MUST remain stateless (no per-request mutable attributes).
    """

    # Required: capabilities property
    @property
    @abstractmethod
    def capabilities(self) -> ProviderCapabilities:
        """Provider capability descriptor (read-only).

        Providers should instantiate from `ProviderCapabilities.from_config(name)`
        or return a constant describing supported features.
        """

    @abstractmethod
    def get_user_managed_groups(self, user_key: str) -> OperationResult:
        """Return a list of canonical group dicts the user can manage (sync).

        Implementors must provide this synchronous method.
        """
        raise NotImplementedError()

    @abstractmethod
    def add_member(
        self, group_key: str, member_data: dict | str, justification: str
    ) -> OperationResult:
        """Add a member synchronously and return a canonical member dict.

        Args:
            group_key: The group identifier (normalized string).
            member_data: Member dict or string identifier (generic, normalized).
            justification: Reason for adding the member.

        Returns:
            Canonical member dict.
        """
        raise NotImplementedError()

    @abstractmethod
    def remove_member(
        self, group_key: str, member_data: dict | str, justification: str
    ) -> OperationResult:
        """Remove a member synchronously and return canonical member dict.

        Args:
            group_key: The group identifier (normalized string).
            member_data: Member dict or string identifier (generic, normalized).
            justification: Reason for removing the member.

        Returns:
            Canonical member dict.
        """
        raise NotImplementedError()

    @abstractmethod
    def get_group_members(self, group_key: str, **kwargs) -> OperationResult:
        """Return list of canonical member dicts (sync)."""
        raise NotImplementedError()

    @abstractmethod
    def validate_permissions(self, user_key: str, group_key: str, action: str) -> OperationResult:
        """Validate permissions synchronously."""
        raise NotImplementedError()

    def create_group(self, *args, **kwargs):
        """Explicitly disabled - groups managed via IaC"""
        raise NotImplementedError("Group creation disabled - managed via IaC")

    def delete_group(self, *args, **kwargs):
        """Explicitly disabled - groups managed via IaC"""
        raise NotImplementedError("Group deletion disabled - managed via IaC")

    def create_user(self, user_data: dict) -> OperationResult:
        """Create a user synchronously and return canonical user dict."""
        raise NotImplementedError("User creation not implemented in this provider.")

    def delete_user(self, user_key: str) -> OperationResult:
        """Delete a user synchronously and return canonical user dict."""
        raise NotImplementedError("User deletion not implemented in this provider.")
