"""Provider abstract classes and operation decorators.

This module defines the GroupProvider and PrimaryGroupProvider abstract base
classes, operation decorators, and helper functions for provider lifecycle
management.

Key separation of concerns:
  - contracts.py: Pure data structures (OperationResult, HealthCheckResult, etc.)
  - capabilities.py: Capability loading from config
  - base.py: Abstract classes and operation decorators
"""

from __future__ import annotations

from typing import Optional
from abc import ABC, abstractmethod
from email_validator import validate_email, EmailNotValidError
from core.config import settings
from core.logging import get_module_logger
from modules.groups.domain.models import NormalizedMember
from modules.groups.infrastructure.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerOpenError,
    register_circuit_breaker,
)
from modules.groups.providers.contracts import (
    OperationResult,
    OperationStatus,
    HealthCheckResult,
    CircuitBreakerStats,
    ProviderCapabilities,
)

logger = get_module_logger()


def validate_member_email(email: str) -> str:
    """Validate and normalize an email address for group membership operations.

    Uses RFC 5321/5322 compliant validation via email-validator library.
    Normalization includes case folding and standardization of the address format.

    Args:
        email: Email address to validate

    Returns:
        Validated and normalized email address (lowercase)

    Raises:
        ValueError: If email is invalid or not a string
    """
    if not email or not isinstance(email, str):
        raise ValueError(
            f"Email must be a non-empty string, got {type(email).__name__}"
        )

    try:
        # email-validator with check_deliverability=False avoids DNS lookups
        # while still providing RFC-compliant validation
        validated = validate_email(email, check_deliverability=False)
        return validated.normalized
    except EmailNotValidError as e:
        raise ValueError(f"Invalid email format: {str(e)}") from e


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

    def add_member(self, group_key: str, member_email: str) -> OperationResult:
        """Add a member to a group by email.

        The email address is the universal identifier for group members across
        all providers. Each provider is responsible for resolving the email to
        its internal user ID representation.

        Args:
            group_key: Provider-specific group identifier
            member_email: Email address of the member to add

        Returns:
            OperationResult with status indicating success or failure.
            For successful operations, data contains the added member details.

        This method is wrapped by circuit breaker. Subclasses should implement
        _add_member_impl instead of this method.
        """
        if self._circuit_breaker:
            try:
                return self._circuit_breaker.call(
                    self._add_member_impl, group_key, member_email
                )
            except CircuitBreakerOpenError as e:
                logger.warning(
                    "circuit_breaker_rejected_add_member",
                    provider=self.__class__.__name__,
                    group_key=group_key,
                    member_email=member_email,
                )
                return OperationResult.transient_error(
                    message=str(e), error_code="CIRCUIT_BREAKER_OPEN"
                )
        else:
            return self._add_member_impl(group_key, member_email)

    @abstractmethod
    def _add_member_impl(self, group_key: str, member_email: str) -> OperationResult:
        """Implementation of add_member (no circuit breaker wrapper).

        Args:
            group_key: Provider-specific group identifier
            member_email: Email address of the member to add

        Returns:
            OperationResult with operation outcome

        Subclasses should implement this method instead of add_member.
        Each provider is responsible for:
        1. Validating the email format
        2. Resolving email to internal user ID
        3. Performing the group membership operation
        """

    def remove_member(self, group_key: str, member_email: str) -> OperationResult:
        """Remove a member from a group by email.

        The email address is the universal identifier for group members across
        all providers. Each provider is responsible for resolving the email to
        its internal user ID representation.

        Args:
            group_key: Provider-specific group identifier
            member_email: Email address of the member to remove

        Returns:
            OperationResult with status indicating success or failure.
            For successful operations, data contains the removed member details.

        This method is wrapped by circuit breaker. Subclasses should implement
        _remove_member_impl instead of this method.
        """
        if self._circuit_breaker:
            try:
                return self._circuit_breaker.call(
                    self._remove_member_impl, group_key, member_email
                )
            except CircuitBreakerOpenError as e:
                logger.warning(
                    "circuit_breaker_rejected_remove_member",
                    provider=self.__class__.__name__,
                    group_key=group_key,
                    member_email=member_email,
                )
                return OperationResult.transient_error(
                    message=str(e), error_code="CIRCUIT_BREAKER_OPEN"
                )
        else:
            return self._remove_member_impl(group_key, member_email)

    @abstractmethod
    def _remove_member_impl(self, group_key: str, member_email: str) -> OperationResult:
        """Implementation of remove_member (no circuit breaker wrapper).

        Args:
            group_key: Provider-specific group identifier
            member_email: Email address of the member to remove

        Returns:
            OperationResult with operation outcome

        Subclasses should implement this method instead of remove_member.
        Each provider is responsible for:
        1. Validating the email format
        2. Resolving email to internal user ID
        3. Performing the group membership operation
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

    def create_user(self, user_data: NormalizedMember) -> OperationResult:
        """Create a user and return the result."""
        raise NotImplementedError("User creation not implemented in this provider.")

    def delete_user(self, user_key: str) -> OperationResult:
        """Delete a user and return the result."""
        raise NotImplementedError("User deletion not implemented in this provider.")

    def get_circuit_breaker_stats(self) -> CircuitBreakerStats:
        """Get circuit breaker statistics for this provider.

        Returns:
            CircuitBreakerStats with current state and statistics.
            If disabled, returns a stats object with enabled=False.
        """
        if self._circuit_breaker:
            stats_dict = self._circuit_breaker.get_stats()
            return CircuitBreakerStats(
                enabled=True,
                state=stats_dict.get("state", "UNKNOWN"),
                failure_count=stats_dict.get("failure_count", 0),
                success_count=stats_dict.get("success_count", 0),
                last_failure_time=stats_dict.get("last_failure_time"),
                message=stats_dict.get("message"),
            )
        return CircuitBreakerStats(
            enabled=False, state="CLOSED", message="Circuit breaker disabled"
        )

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

    def health_check(self) -> HealthCheckResult:
        """Perform a lightweight health check with circuit breaker protection.

        Health checks should be minimal API calls (e.g., authenticate or get
        basic provider info) to verify the provider is working. They should
        not consume significant quota or resources.

        This method is wrapped by circuit breaker. Subclasses should implement
        _health_check_impl instead of this method.

        Returns:
            HealthCheckResult with health status and optional provider-specific details
        """
        if self._circuit_breaker:
            try:
                return self._circuit_breaker.call(self._health_check_impl)
            except CircuitBreakerOpenError as e:
                logger.warning(
                    "circuit_breaker_rejected_health_check",
                    provider=self.__class__.__name__,
                )
                return HealthCheckResult(
                    healthy=False,
                    status="unhealthy",
                    details={"error": str(e), "error_code": "CIRCUIT_BREAKER_OPEN"},
                )
        else:
            return self._health_check_impl()

    @abstractmethod
    def _health_check_impl(self) -> HealthCheckResult:
        """Implementation of health_check (no circuit breaker wrapper).

        Each provider should implement a minimal health check that verifies
        connectivity and basic functionality without consuming significant
        resources or quota. This should be a lightweight operation such as:
        - Authenticating with the provider API
        - Retrieving a simple piece of information (e.g., org domain)
        - Testing connectivity without listing large datasets

        Returns:
            HealthCheckResult indicating provider health status

        Subclasses should implement this method instead of health_check.
        """


class PrimaryGroupProvider(GroupProvider):
    """Abstract subclass for primary/canonical group providers.

    The primary provider (typically Google Workspace) is the authoritative source
    of truth for group membership and metadata. It provides additional methods
    beyond the base GroupProvider contract:

    Additional Methods:
        validate_permissions(): Check if a user has permission to perform an action
        is_manager(): Check if a user is a manager of a group
        list_groups_for_user(): Get all groups a specific user belongs to

    Source of Truth Role:
        - All group membership data is read from and verified against the primary provider
        - Secondary providers synchronize their state from the primary provider
        - Email addresses are the universal identifier across all providers
        - Primary provider is consulted for canonical group and user information

    Subclasses should implement:
        - Standard GroupProvider abstract methods (add_member, remove_member, etc.)
        - Permission validation methods (validate_permissions, is_manager)
        - Any primary-provider-specific operations
    """

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
