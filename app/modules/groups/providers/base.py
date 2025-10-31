"""Provider contracts and capability logic for group providers."""

from __future__ import annotations

from enum import Enum
from typing import Optional, Dict, Any
from dataclasses import dataclass
from abc import ABC, abstractmethod
from core.config import settings
from modules.groups.models import NormalizedMember


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

    @classmethod
    def success(
        cls, data: Optional[Dict[str, Any]] = None, message: str = "ok"
    ) -> "OperationResult":
        """Create a SUCCESS OperationResult with optional data."""
        return cls(status=OperationStatus.SUCCESS, message=message, data=data)

    @classmethod
    def error(
        cls,
        status: OperationStatus,
        message: str,
        error_code: Optional[str] = None,
        retry_after: Optional[int] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> "OperationResult":
        """Create an error OperationResult with optional metadata."""
        return cls(
            status=status,
            message=message,
            data=data,
            error_code=error_code,
            retry_after=retry_after,
        )

    @classmethod
    def transient_error(
        cls, message: str, error_code: Optional[str] = None
    ) -> "OperationResult":
        return cls.error(
            OperationStatus.TRANSIENT_ERROR, message, error_code=error_code
        )

    @classmethod
    def permanent_error(
        cls, message: str, error_code: Optional[str] = None
    ) -> "OperationResult":
        return cls.error(
            OperationStatus.PERMANENT_ERROR, message, error_code=error_code
        )


@dataclass
class ProviderCapabilities:
    supports_user_creation: bool = False
    supports_user_deletion: bool = False
    supports_group_creation: bool = False  # Should always be False
    supports_group_deletion: bool = False  # Should always be False
    supports_member_management: bool = True
    is_primary: bool = False
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
        caps = (
            provider_cfg.get("capabilities", {})
            if isinstance(provider_cfg, dict)
            else {}
        )
        return cls(
            supports_user_creation=caps.get("supports_user_creation", False),
            supports_user_deletion=caps.get("supports_user_deletion", False),
            supports_group_creation=caps.get("supports_group_creation", False),
            supports_group_deletion=caps.get("supports_group_deletion", False),
            supports_member_management=caps.get("supports_member_management", True),
            provides_role_info=caps.get("provides_role_info", False),
            supports_batch_operations=caps.get("supports_batch_operations", False),
            max_batch_size=caps.get("max_batch_size", 1),
        )


def provider_supports(provider_name: str, capability: str) -> bool:
    """Return whether the named provider advertises a given capability."""
    try:
        caps = ProviderCapabilities.from_config(provider_name)
        return bool(getattr(caps, capability, False))
    except Exception:
        return False


def provider_provides_role_info(provider_name: str) -> bool:
    """Convenience wrapper for the common 'provides_role_info' check."""
    return provider_supports(provider_name, "provides_role_info")


def opresult_wrapper(data_key=None):
    """Decorator to wrap a method call in an OperationResult."""

    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                result = func(*args, **kwargs)
                # If the provider already returned an OperationResult, pass it
                # through unchanged (avoid double-wrapping).
                if isinstance(result, OperationResult):
                    return result
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
    """Abstract Base Class for group providers."""

    @property
    def prefix(self) -> str:
        """Provider prefix used for composing/parsing primary-style group names.

        Default behavior: use the provider registration `name` attribute when
        present on the instance. Providers may override this property to
        return a different prefix. The provider registry will also apply any
        configured overrides (settings) to the instance at activation time.
        """
        # Activation-time override (set by registry when applying config)
        override = getattr(self, "_prefix", None)
        if override:
            return str(override)
        # Prefer an explicit registration name attribute when available.
        name = getattr(self, "name", None)
        if name:
            return str(name)
        # Fallback to a deterministic class-derived name.
        return self.__class__.__name__.lower()

    @property
    @abstractmethod
    def capabilities(self) -> ProviderCapabilities:
        """Provider capability descriptor."""

    @abstractmethod
    def add_member(
        self, group_key: str, member_data: NormalizedMember
    ) -> OperationResult:
        """Add a member synchronously and return a canonical member dict."""

    @abstractmethod
    def remove_member(
        self, group_key: str, member_data: NormalizedMember
    ) -> OperationResult:
        """Remove a member synchronously and return canonical member dict."""

    @abstractmethod
    def get_group_members(self, group_key: str, **kwargs) -> OperationResult:
        """Return list of canonical member dicts."""

    @abstractmethod
    def list_groups(self, **kwargs) -> OperationResult:
        """Return list of canonical group dicts from the provider."""

    @abstractmethod
    def list_groups_with_members(self, **kwargs) -> OperationResult:
        """Return list of canonical group dicts with members from the provider."""

    def create_group(self, *args, **kwargs) -> OperationResult:
        """Group creation is disabled; managed via IaC."""
        return OperationResult.permanent_error(
            "Group creation disabled - managed via IaC", error_code="NOT_IMPLEMENTED"
        )

    def delete_group(self, *args, **kwargs) -> OperationResult:
        """Group deletion is disabled; managed via IaC."""
        return OperationResult.permanent_error(
            "Group deletion disabled - managed via IaC", error_code="NOT_IMPLEMENTED"
        )

    def create_user(self, user_data: NormalizedMember) -> OperationResult:
        """Create a user and return the result."""
        raise NotImplementedError("User creation not implemented in this provider.")

    def delete_user(self, user_key: str) -> OperationResult:
        """Delete a user and return the result."""
        raise NotImplementedError("User deletion not implemented in this provider.")

    def list_groups_for_user(
        self, user_key: str, provider_name: Optional[str], **kwargs
    ) -> OperationResult:
        """Return a list of canonical group dicts the user can manage."""
        raise NotImplementedError()


class PrimaryGroupProvider(GroupProvider):
    """Abstract subclass for primary/canonical providers."""

    @abstractmethod
    def validate_permissions(
        self, user_key: str, group_key: str, action: str
    ) -> OperationResult:
        """Validate permissions for a user on a group."""

    @abstractmethod
    def is_manager(self, user_key: str, group_key: str) -> OperationResult:
        """Direct role-check for whether the user is manager for the group."""
