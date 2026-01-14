"""Platform Service for coordinating provider interactions.

Provides a unified service layer for sending messages, formatting responses,
and managing platform providers through the registry.

This service:
- Manages provider discovery and registration
- Routes messages to appropriate platform providers
- Formats responses using platform-specific formatters
- Validates platform capabilities
- Provides health checking for active platforms

Usage:
    # Via dependency injection
    from infrastructure.services import PlatformServiceDep

    @router.post("/send")
    def send_message(
        platform_service: PlatformServiceDep,
        message: MessageRequest
    ):
        result = platform_service.send(
            platform="slack",
            channel="C123456",
            message={"text": "Hello"}
        )
        return {"success": result.is_success}

    # Direct instantiation
    from infrastructure.platforms import PlatformService
    from infrastructure.services import get_settings

    service = PlatformService(settings=get_settings())
    service.load_providers()  # Discover and register providers
"""

from typing import Any, Dict, List, Optional

import structlog

from infrastructure.configuration import Settings
from infrastructure.operations import OperationResult
from infrastructure.platforms.capabilities.models import PlatformCapability
from infrastructure.platforms.exceptions import (
    CapabilityNotSupportedError,
    ProviderNotFoundError,
)
from infrastructure.platforms.providers.base import BasePlatformProvider
from infrastructure.platforms.registry import PlatformRegistry

logger = structlog.get_logger()


class PlatformService:
    """Service for coordinating platform provider interactions.

    This service acts as a facade for the platform system, providing
    simplified access to multiple platform providers through a single
    interface. It handles provider registration, message routing, and
    response formatting.

    Attributes:
        _settings: Application settings
        _registry: Platform registry containing all providers
    """

    def __init__(self, settings: Settings) -> None:
        """Initialize platform service with settings.

        Args:
            settings: Application settings from infrastructure.configuration
        """
        self._settings = settings
        self._registry = PlatformRegistry()
        self._logger = logger.bind(component="platform_service")

    def load_providers(self) -> Dict[str, BasePlatformProvider]:
        """Discover and register all available platform providers.

        Imports provider modules to trigger registration via decorators,
        then returns all registered providers from the registry.

        Returns:
            Dict mapping provider names to provider instances

        Example:
            >>> service = PlatformService(settings)
            >>> providers = service.load_providers()
            >>> print(f"Loaded {len(providers)} providers")
        """
        import importlib
        import pkgutil

        # Import all provider modules to enable provider imports
        import infrastructure.platforms.providers as providers_package

        for module_info in pkgutil.iter_modules(providers_package.__path__):
            module_name = module_info.name
            if module_name.startswith("_") or module_name == "base":
                continue  # Skip private modules and base class

            full_module_name = f"{providers_package.__name__}.{module_name}"
            try:
                importlib.import_module(full_module_name)
                self._logger.debug("provider_module_imported", module=full_module_name)
            except Exception as e:
                self._logger.warning(
                    "provider_module_import_failed",
                    module=full_module_name,
                    error=str(e),
                )

        provider_list = self._registry.list_providers()
        # Convert list to dict keyed by platform_id
        providers = {p.get_capabilities().platform_id: p for p in provider_list}
        self._logger.info(
            "providers_loaded",
            count=len(providers),
            providers=list(providers.keys()),
        )
        return providers

    def get_provider(self, name: str) -> BasePlatformProvider:
        """Get platform provider by name.

        Args:
            name: Provider name (e.g., 'slack', 'teams')

        Returns:
            BasePlatformProvider instance

        Raises:
            ProviderNotFoundError: If provider not registered

        Example:
            >>> slack = service.get_provider("slack")
            >>> caps = slack.get_capabilities()
        """
        provider = self._registry.get_provider(name)
        if provider is None:
            raise ProviderNotFoundError(f"No provider registered with name '{name}'")
        return provider

    def get_enabled_providers(self) -> List[BasePlatformProvider]:
        """Get all enabled platform providers.

        Returns:
            List of enabled provider instances

        Example:
            >>> enabled = service.get_enabled_providers()
            >>> for provider in enabled:
            ...     print(f"{provider.name}: {provider.enabled}")
        """
        return [p for p in self._registry.list_providers() if p.enabled]

    def send(
        self,
        platform: str,
        channel: str,
        message: Dict[str, Any],
        **kwargs: Any,
    ) -> OperationResult:
        """Send a message through a platform provider.

        Args:
            platform: Platform name ('slack', 'teams', etc.)
            channel: Target channel/conversation ID
            message: Message content (format depends on platform)
            **kwargs: Additional platform-specific parameters

        Returns:
            OperationResult with send status

        Raises:
            ProviderNotFoundError: If platform provider not found

        Example:
            >>> result = service.send(
            ...     platform="slack",
            ...     channel="C123456",
            ...     message={"text": "Hello!"}
            ... )
            >>> if result.is_success:
            ...     print("Message sent!")
        """
        log = self._logger.bind(platform=platform, channel=channel)

        try:
            provider = self.get_provider(platform)
        except ProviderNotFoundError as e:
            log.error("provider_not_found", error=str(e))
            return OperationResult.permanent_error(
                message=f"Platform provider not found: {platform}",
                error_code="PROVIDER_NOT_FOUND",
            )

        if not provider.enabled:
            log.warning("provider_disabled")
            return OperationResult.permanent_error(
                message=f"Platform provider disabled: {platform}",
                error_code="PROVIDER_DISABLED",
            )

        log.debug("sending_message_via_provider")
        result = provider.send_message(channel=channel, message=message, **kwargs)

        if result.is_success:
            log.info("message_sent_successfully")
        else:
            log.error(
                "message_send_failed",
                status=result.status,
                error_code=result.error_code,
            )

        return result

    def format_response(
        self,
        platform: str,
        data: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Format a response using platform-specific formatter.

        Args:
            platform: Platform name ('slack', 'teams', etc.)
            data: Optional success data to format
            error: Optional error message to format

        Returns:
            Platform-specific formatted response

        Raises:
            ProviderNotFoundError: If platform provider not found

        Example:
            >>> response = service.format_response(
            ...     platform="slack",
            ...     data={"user_id": "U123"}
            ... )
            >>> print(response["blocks"])
        """
        provider = self.get_provider(platform)
        message_type = "error" if error else "success"
        response_data = data or {}
        if error:
            response_data["error"] = error
        return provider.format_response(data=response_data, message_type=message_type)

    def supports_capability(
        self, platform: str, capability: PlatformCapability
    ) -> bool:
        """Check if a platform supports a specific capability.

        Args:
            platform: Platform name ('slack', 'teams', etc.)
            capability: Capability to check

        Returns:
            True if platform supports the capability

        Raises:
            ProviderNotFoundError: If platform provider not found

        Example:
            >>> if service.supports_capability("slack", PlatformCapability.THREADS):
            ...     print("Slack supports threads")
        """
        try:
            provider = self.get_provider(platform)
            return provider.supports_capability(capability)
        except ProviderNotFoundError:
            return False

    def require_capability(self, platform: str, capability: PlatformCapability) -> None:
        """Require a platform to support a specific capability.

        Args:
            platform: Platform name ('slack', 'teams', etc.)
            capability: Required capability

        Raises:
            ProviderNotFoundError: If platform provider not found
            CapabilityNotSupportedError: If capability not supported

        Example:
            >>> try:
            ...     service.require_capability("slack", PlatformCapability.THREADS)
            ...     # Proceed with thread operations
            ... except CapabilityNotSupportedError:
            ...     # Handle lack of thread support
        """
        provider = self.get_provider(platform)
        if not provider.supports_capability(capability):
            raise CapabilityNotSupportedError(
                f"Platform {platform} does not support {capability.value}"
            )

    def initialize_provider(self, platform: str) -> OperationResult:
        """Initialize a platform provider's connection/app.

        Args:
            platform: Platform name ('slack', 'teams', etc.)

        Returns:
            OperationResult indicating initialization status

        Raises:
            ProviderNotFoundError: If platform provider not found

        Example:
            >>> result = service.initialize_provider("slack")
            >>> if result.is_success:
            ...     print("Slack app initialized")
        """
        log = self._logger.bind(platform=platform)

        provider = self.get_provider(platform)

        if not provider.enabled:
            log.warning("provider_disabled")
            return OperationResult.permanent_error(
                message=f"Platform provider disabled: {platform}",
                error_code="PROVIDER_DISABLED",
            )

        log.debug("initializing_provider")

        # Check if provider has initialize_app method
        if not hasattr(provider, "initialize_app"):
            log.warning("provider_no_initialize_method")
            return OperationResult.success(
                message=f"Platform provider {platform} does not require initialization",
            )

        result = provider.initialize_app()

        if result.is_success:
            log.info("provider_initialized")
        else:
            log.error(
                "provider_initialization_failed",
                error_code=result.error_code,
            )

        return result

    def initialize_all_providers(self) -> Dict[str, OperationResult]:
        """Initialize all enabled platform providers.

        Returns:
            Dict mapping provider names to initialization results

        Example:
            >>> results = service.initialize_all_providers()
            >>> failed = [p for p, r in results.items() if not r.is_success]
            >>> if failed:
            ...     print(f"Failed to initialize: {', '.join(failed)}")
        """
        results: Dict[str, OperationResult] = {}
        providers = self.get_enabled_providers()

        self._logger.info("initializing_all_providers", count=len(providers))

        for provider in providers:
            result = self.initialize_provider(provider.name)
            results[provider.name] = result

        success_count = sum(1 for r in results.values() if r.is_success)
        self._logger.info(
            "provider_initialization_complete",
            total=len(results),
            successful=success_count,
            failed=len(results) - success_count,
        )

        return results

    def health_check(self, platform: str) -> OperationResult:
        """Perform health check on a platform provider.

        Args:
            platform: Platform name ('slack', 'teams', etc.)

        Returns:
            OperationResult indicating health status

        Raises:
            ProviderNotFoundError: If platform provider not found

        Example:
            >>> result = service.health_check("slack")
            >>> if result.is_success:
            ...     print(f"Slack is healthy: {result.data}")
        """
        provider = self.get_provider(platform)

        if not provider.enabled:
            return OperationResult.permanent_error(
                message=f"Provider {platform} is disabled",
                error_code="PROVIDER_DISABLED",
            )

        return OperationResult.success(
            data={
                "platform": platform,
                "enabled": provider.enabled,
                "capabilities": len(provider.get_capabilities().capabilities),
            },
            message=f"Provider {platform} is healthy",
        )

    def get_platform_info(self, platform: str) -> Dict[str, Any]:
        """Get comprehensive information about a platform provider.

        Args:
            platform: Platform name ('slack', 'teams', etc.)

        Returns:
            Dict with provider info (name, version, enabled, capabilities, etc.)

        Raises:
            ProviderNotFoundError: If platform provider not found

        Example:
            >>> info = service.get_platform_info("slack")
            >>> print(f"{info['name']} v{info['version']}")
            >>> print(f"Capabilities: {info['capabilities']}")
        """
        provider = self.get_provider(platform)
        caps = provider.get_capabilities()

        return {
            "name": provider.name,
            "version": provider.version,
            "enabled": provider.enabled,
            "capabilities": [cap.value for cap in caps.capabilities],
            "metadata": caps.metadata,
        }

    @property
    def registry(self) -> PlatformRegistry:
        """Access the underlying platform registry.

        Returns:
            PlatformRegistry instance
        """
        return self._registry
