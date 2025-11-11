"""Provider contracts and capability logic for group providers."""

from __future__ import annotations

from enum import Enum
from typing import Optional, Dict, Any
from dataclasses import dataclass
from abc import ABC, abstractmethod
from core.config import settings
from core.logging import get_module_logger
from modules.groups.models import NormalizedMember
from modules.groups.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerOpenError,
    register_circuit_breaker,
)

logger = get_module_logger()


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


def provider_operation(data_key=None):
    """Decorator for provider operations with error classification.

    Handles:
    - OperationResult pass-through (avoid double-wrapping)
    - Success data wrapping via data_key
    - Exception classification via provider's classify_error() method
    - Graceful fallback to generic transient error

    Args:
        data_key: Optional key to wrap result data under (e.g., "members" wraps as {"members": [...]})

    Returns:
        Decorated function that returns OperationResult
    """

    def decorator(func):
        def wrapper(self, *args, **kwargs):
            try:
                result = func(self, *args, **kwargs)
                # If the provider already returned an OperationResult, pass it
                # through unchanged (avoid double-wrapping).
                if isinstance(result, OperationResult):
                    return result
                data = {data_key: result} if data_key else result
                return OperationResult(
                    status=OperationStatus.SUCCESS, message="ok", data=data
                )
            except Exception as e:
                # Use provider's error classification method
                return self.classify_error(e)

        return wrapper

    return decorator


class GroupProvider(ABC):
    """Abstract Base Class for group providers."""

    def __init__(self):
        """Initialize provider with circuit breaker."""
        # Create circuit breaker for this provider
        provider_name = self.__class__.__name__

        if settings.groups.circuit_breaker_enabled:
            self._circuit_breaker = CircuitBreaker(
                name=provider_name,
                failure_threshold=settings.groups.circuit_breaker_failure_threshold,
                timeout_seconds=settings.groups.circuit_breaker_timeout_seconds,
                half_open_max_calls=settings.groups.circuit_breaker_half_open_max_calls,
            )
            # Register in global registry for monitoring
            register_circuit_breaker(self._circuit_breaker)
        else:
            self._circuit_breaker = None

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
        """Provider capability descriptor.

        Subclasses must implement this to return their default capabilities.
        The activation system may override these with config-driven values.
        """

    def get_capabilities(self) -> ProviderCapabilities:
        """Get effective capabilities, respecting config overrides.

        Returns:
            ProviderCapabilities instance, either the config-overridden version
            (if _capability_override is set) or the provider's default capabilities.
        """
        override = getattr(self, "_capability_override", None)
        return override if override is not None else self.capabilities

    def classify_error(self, exc: Exception) -> OperationResult:
        """Classify provider-specific exceptions into OperationResult.

        Providers should override to classify:
        - Rate limit errors (with retry_after)
        - Transient errors (network, timeout)
        - Permanent errors (auth, not found, invalid input)
        - Circuit breaker state

        Args:
            exc: Exception raised by provider operation

        Returns:
            OperationResult with appropriate status, error_code, and retry_after

        Default implementation: treat all as transient errors.
        """
        return OperationResult.transient_error(str(exc))

    def get_mapping_prefix(self) -> Optional[str]:
        """Return the prefix used for this provider in cross-provider mapping.

        This prefix is prepended to canonical group names when mapping FROM
        this secondary provider TO the primary provider.

        Primary providers return None (no prefix in mappings).
        Secondary providers return their configured prefix.

        Examples:
            Google provider (primary): None
            AWS provider (secondary): "aws"
            Custom provider (secondary): "custom"

        Returns:
            Prefix string for secondary providers, None for primary provider
        """
        # Primary providers don't use prefixes in mappings
        if self.get_capabilities().is_primary:
            return None

        # Use configured prefix (set during activation)
        configured = getattr(self, "_prefix", None)
        if configured:
            return configured

        # Fallback to prefix property or class name
        return self.prefix

    def add_member(
        self, group_key: str, member_data: NormalizedMember
    ) -> OperationResult:
        """Add a member synchronously and return a canonical member dict.

        This method is wrapped by circuit breaker. Subclasses should implement
        _add_member_impl instead of this method.
        """
        if self._circuit_breaker:
            try:
                return self._circuit_breaker.call(
                    self._add_member_impl, group_key, member_data
                )
            except CircuitBreakerOpenError as e:
                logger.warning(
                    "circuit_breaker_rejected_add_member",
                    provider=self.__class__.__name__,
                    group_key=group_key,
                )
                return OperationResult.transient_error(
                    message=str(e), error_code="CIRCUIT_BREAKER_OPEN"
                )
        else:
            return self._add_member_impl(group_key, member_data)

    @abstractmethod
    def _add_member_impl(
        self, group_key: str, member_data: NormalizedMember
    ) -> OperationResult:
        """Implementation of add_member (no circuit breaker wrapper).

        Subclasses should implement this method instead of add_member.
        """

    def remove_member(
        self, group_key: str, member_data: NormalizedMember
    ) -> OperationResult:
        """Remove a member synchronously and return canonical member dict.

        This method is wrapped by circuit breaker. Subclasses should implement
        _remove_member_impl instead of this method.
        """
        if self._circuit_breaker:
            try:
                return self._circuit_breaker.call(
                    self._remove_member_impl, group_key, member_data
                )
            except CircuitBreakerOpenError as e:
                logger.warning(
                    "circuit_breaker_rejected_remove_member",
                    provider=self.__class__.__name__,
                    group_key=group_key,
                )
                return OperationResult.transient_error(
                    message=str(e), error_code="CIRCUIT_BREAKER_OPEN"
                )
        else:
            return self._remove_member_impl(group_key, member_data)

    @abstractmethod
    def _remove_member_impl(
        self, group_key: str, member_data: NormalizedMember
    ) -> OperationResult:
        """Implementation of remove_member (no circuit breaker wrapper).

        Subclasses should implement this method instead of remove_member.
        """

    def get_group_members(self, group_key: str, **kwargs) -> OperationResult:
        """Return list of canonical member dicts.

        This method is wrapped by circuit breaker. Subclasses should implement
        _get_group_members_impl instead of this method.
        """
        if self._circuit_breaker:
            try:
                return self._circuit_breaker.call(
                    self._get_group_members_impl, group_key, **kwargs
                )
            except CircuitBreakerOpenError as e:
                logger.warning(
                    "circuit_breaker_rejected_get_group_members",
                    provider=self.__class__.__name__,
                    group_key=group_key,
                )
                return OperationResult.transient_error(
                    message=str(e), error_code="CIRCUIT_BREAKER_OPEN"
                )
        else:
            return self._get_group_members_impl(group_key, **kwargs)

    @abstractmethod
    def _get_group_members_impl(self, group_key: str, **kwargs) -> OperationResult:
        """Implementation of get_group_members (no circuit breaker wrapper).

        Subclasses should implement this method instead of get_group_members.
        """

    def list_groups(self, **kwargs) -> OperationResult:
        """Return list of canonical group dicts from the provider.

        This method is wrapped by circuit breaker. Subclasses should implement
        _list_groups_impl instead of this method.
        """
        if self._circuit_breaker:
            try:
                return self._circuit_breaker.call(self._list_groups_impl, **kwargs)
            except CircuitBreakerOpenError as e:
                logger.warning(
                    "circuit_breaker_rejected_list_groups",
                    provider=self.__class__.__name__,
                )
                return OperationResult.transient_error(
                    message=str(e), error_code="CIRCUIT_BREAKER_OPEN"
                )
        else:
            return self._list_groups_impl(**kwargs)

    @abstractmethod
    def _list_groups_impl(self, **kwargs) -> OperationResult:
        """Implementation of list_groups (no circuit breaker wrapper).

        Subclasses should implement this method instead of list_groups.
        """

    def list_groups_with_members(self, **kwargs) -> OperationResult:
        """Return list of canonical group dicts with members from the provider.

        This method is wrapped by circuit breaker. Subclasses should implement
        _list_groups_with_members_impl instead of this method.
        """
        if self._circuit_breaker:
            try:
                return self._circuit_breaker.call(
                    self._list_groups_with_members_impl, **kwargs
                )
            except CircuitBreakerOpenError as e:
                logger.warning(
                    "circuit_breaker_rejected_list_groups_with_members",
                    provider=self.__class__.__name__,
                )
                return OperationResult.transient_error(
                    message=str(e), error_code="CIRCUIT_BREAKER_OPEN"
                )
        else:
            return self._list_groups_with_members_impl(**kwargs)

    @abstractmethod
    def _list_groups_with_members_impl(self, **kwargs) -> OperationResult:
        """Implementation of list_groups_with_members (no circuit breaker wrapper).

        Subclasses should implement this method instead of list_groups_with_members.
        """

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

    def get_circuit_breaker_stats(self) -> dict:
        """Get circuit breaker statistics for this provider.

        Returns:
            Dictionary with circuit breaker state and statistics, or empty dict if disabled.
        """
        if self._circuit_breaker:
            return self._circuit_breaker.get_stats()
        return {"enabled": False, "message": "Circuit breaker disabled"}

    def reset_circuit_breaker(self) -> None:
        """Manually reset circuit breaker to CLOSED state.

        Use this for admin operations when you know a provider has recovered
        but the circuit is still open.
        """
        if self._circuit_breaker:
            self._circuit_breaker.reset()
            logger.info(
                "provider_circuit_breaker_manually_reset",
                provider=self.__class__.__name__,
            )

    def health_check(self) -> OperationResult:
        """Perform a lightweight health check with circuit breaker protection.

        Health checks should be minimal API calls (e.g., authenticate or get
        basic provider info) to verify the provider is working. They should
        not consume significant quota or resources.

        This method is wrapped by circuit breaker. Subclasses should implement
        _health_check_impl instead of this method.

        Returns:
            OperationResult with status and optional health details
        """
        if self._circuit_breaker:
            try:
                return self._circuit_breaker.call(self._health_check_impl)
            except CircuitBreakerOpenError as e:
                logger.warning(
                    "circuit_breaker_rejected_health_check",
                    provider=self.__class__.__name__,
                )
                return OperationResult.transient_error(
                    message=str(e), error_code="CIRCUIT_BREAKER_OPEN"
                )
        else:
            return self._health_check_impl()

    @abstractmethod
    def _health_check_impl(self) -> OperationResult:
        """Implementation of health_check (no circuit breaker wrapper).

        Subclasses should implement this method instead of health_check.

        This should be a lightweight operation that verifies the provider
        is accessible and functional, such as:
        - Authenticating with the provider API
        - Retrieving a simple piece of information (e.g., org domain)
        - Testing connectivity without listing large datasets

        Returns:
            OperationResult.success() if healthy, error result otherwise
        """


class PrimaryGroupProvider(GroupProvider):
    """Abstract subclass for primary/canonical providers."""

    def validate_permissions(
        self, user_key: str, group_key: str, action: str
    ) -> OperationResult:
        """Validate permissions for a user on a group with circuit breaker protection.

        This method is wrapped by circuit breaker. Subclasses should implement
        _validate_permissions_impl instead of this method.
        """
        if self._circuit_breaker:
            try:
                return self._circuit_breaker.call(
                    self._validate_permissions_impl, user_key, group_key, action
                )
            except CircuitBreakerOpenError as e:
                logger.warning(
                    "circuit_breaker_rejected_validate_permissions",
                    provider=self.__class__.__name__,
                    user_key=user_key,
                    group_key=group_key,
                )
                return OperationResult.transient_error(
                    message=str(e), error_code="CIRCUIT_BREAKER_OPEN"
                )
        else:
            return self._validate_permissions_impl(user_key, group_key, action)

    @abstractmethod
    def _validate_permissions_impl(
        self, user_key: str, group_key: str, action: str
    ) -> OperationResult:
        """Implementation of validate_permissions (no circuit breaker wrapper).

        Subclasses should implement this method instead of validate_permissions.
        """

    def is_manager(self, user_key: str, group_key: str) -> OperationResult:
        """Check if user is manager with circuit breaker protection.

        This method is wrapped by circuit breaker. Subclasses should implement
        _is_manager_impl instead of this method.
        """
        if self._circuit_breaker:
            try:
                return self._circuit_breaker.call(
                    self._is_manager_impl, user_key, group_key
                )
            except CircuitBreakerOpenError as e:
                logger.warning(
                    "circuit_breaker_rejected_is_manager",
                    provider=self.__class__.__name__,
                    user_key=user_key,
                    group_key=group_key,
                )
                return OperationResult.transient_error(
                    message=str(e), error_code="CIRCUIT_BREAKER_OPEN"
                )
        else:
            return self._is_manager_impl(user_key, group_key)

    @abstractmethod
    def _is_manager_impl(self, user_key: str, group_key: str) -> OperationResult:
        """Implementation of is_manager (no circuit breaker wrapper).

        Subclasses should implement this method instead of is_manager.
        """

    def list_groups_for_user(
        self, user_key: str, provider_name: Optional[str], **kwargs
    ) -> OperationResult:
        """Return a list of canonical group dicts the user is a member of with circuit breaker protection.

        This method is wrapped by circuit breaker. Subclasses should implement
        _list_groups_for_user_impl instead of this method.
        """
        if self._circuit_breaker:
            try:
                return self._circuit_breaker.call(
                    self._list_groups_for_user_impl, user_key, provider_name, **kwargs
                )
            except CircuitBreakerOpenError as e:
                logger.warning(
                    "circuit_breaker_rejected_list_groups_for_user",
                    provider=self.__class__.__name__,
                    user_key=user_key,
                )
                return OperationResult.transient_error(
                    message=str(e), error_code="CIRCUIT_BREAKER_OPEN"
                )
        else:
            return self._list_groups_for_user_impl(user_key, provider_name, **kwargs)

    @abstractmethod
    def _list_groups_for_user_impl(
        self, user_key: str, provider_name: Optional[str], **kwargs
    ) -> OperationResult:
        """Implementation of list_groups_for_user (no circuit breaker wrapper).

        Subclasses should implement this method instead of list_groups_for_user.
        """

    def list_groups_managed_by_user(
        self, user_key: str, provider_name: Optional[str], **kwargs
    ) -> OperationResult:
        """Return a list of canonical group dicts the user manages with circuit breaker protection.

        This method is wrapped by circuit breaker. Subclasses should implement
        _list_groups_managed_by_user_impl instead of this method.
        """
        if self._circuit_breaker:
            try:
                return self._circuit_breaker.call(
                    self._list_groups_managed_by_user_impl,
                    user_key,
                    provider_name,
                    **kwargs,
                )
            except CircuitBreakerOpenError as e:
                logger.warning(
                    "circuit_breaker_rejected_list_groups_managed_by_user",
                    provider=self.__class__.__name__,
                    user_key=user_key,
                )
                return OperationResult.transient_error(
                    message=str(e), error_code="CIRCUIT_BREAKER_OPEN"
                )
        else:
            return self._list_groups_managed_by_user_impl(
                user_key, provider_name, **kwargs
            )

    @abstractmethod
    def _list_groups_managed_by_user_impl(
        self, user_key: str, provider_name: Optional[str], **kwargs
    ) -> OperationResult:
        """Implementation of list_groups_managed_by_user (no circuit breaker wrapper).

        Subclasses should implement this method instead of list_groups_managed_by_user.
        """
