"""Custom exceptions for the platform system.

Provides specialized exceptions for platform provider errors,
capability issues, and registration problems.
"""

from typing import Optional


class PlatformError(Exception):
    """Base exception for all platform-related errors.

    All platform system exceptions inherit from this base class
    for easier exception handling in application code.

    Example:
        try:
            service.send(...)
        except PlatformError as e:
            logger.error("platform_error", error=str(e))
    """

    pass


class ProviderNotFoundError(PlatformError):
    """Raised when a requested platform provider is not found in the registry.

    Example:
        >>> service.get_provider("nonexistent")
        Traceback (most recent call last):
        ...
        ProviderNotFoundError: Provider 'nonexistent' not found
    """

    pass


class ProviderAlreadyRegisteredError(PlatformError):
    """Raised when attempting to register a provider with a duplicate name.

    Example:
        >>> registry.register(slack_provider)
        >>> registry.register(another_slack_provider)  # Same name
        Traceback (most recent call last):
        ...
        ProviderAlreadyRegisteredError: Provider 'slack' already registered
    """

    pass


class CapabilityNotSupportedError(PlatformError):
    """Raised when a platform does not support a required capability.

    Example:
        >>> service.require_capability("teams", PlatformCapability.THREADS)
        Traceback (most recent call last):
        ...
        CapabilityNotSupportedError: Platform teams does not support THREADS
    """

    pass


class ProviderInitializationError(PlatformError):
    """Raised when a provider fails to initialize properly.

    Example:
        >>> result = provider.initialize_app()
        >>> if not result.is_success:
        ...     raise ProviderInitializationError(result.message)
    """

    pass


class InvalidMessageFormatError(PlatformError):
    """Raised when a message format is invalid for the target platform.

    Example:
        >>> provider.send_message(channel="C123", message=None)
        Traceback (most recent call last):
        ...
        InvalidMessageFormatError: Message cannot be None or empty
    """

    pass


class ConnectionError(PlatformError):
    """Raised when a platform connection fails or times out.

    Example:
        >>> provider.send_message(...)
        Traceback (most recent call last):
        ...
        ConnectionError: Failed to connect to Slack API
    """

    pass


class AuthenticationError(PlatformError):
    """Raised when platform authentication fails.

    Example:
        >>> provider.initialize_app()
        Traceback (most recent call last):
        ...
        AuthenticationError: Invalid Slack bot token
    """

    pass


class RateLimitExceededError(PlatformError):
    """Raised when platform rate limits are exceeded.

    Attributes:
        retry_after: Seconds to wait before retrying (if provided by platform)

    Example:
        >>> try:
        ...     provider.send_message(...)
        ... except RateLimitExceededError as e:
        ...     time.sleep(e.retry_after)
    """

    def __init__(self, message: str, retry_after: Optional[int] = None):
        """Initialize with message and optional retry_after.

        Args:
            message: Error message
            retry_after: Seconds to wait before retry
        """
        super().__init__(message)
        self.retry_after = retry_after


class FormatterError(PlatformError):
    """Raised when response formatting fails.

    Example:
        >>> formatter.format_success(invalid_data)
        Traceback (most recent call last):
        ...
        FormatterError: Failed to format response
    """

    pass
