"""Base adapter for platform command handlers.

Platform adapters translate platform-specific events into HTTP calls
to internal FastAPI endpoints, maintaining platform-independence in business logic.

Architecture Pattern:
    1. Platform Event (Slack /command, Teams @mention, Discord /slash)
    2. Platform Provider acknowledges immediately (3-5 second rule)
    3. CommandAdapter parses event → CommandPayload
    4. CommandAdapter calls HTTP endpoint (localhost)
    5. CommandAdapter formats response for platform
    6. Platform Provider sends formatted response

This pattern ensures:
    - Business logic stays in HTTP handlers (testable via standard HTTP)
    - Platform SDKs isolated to adapters (easy to mock)
    - Consistent audit logging (all requests go through FastAPI middleware)
    - Idempotency works the same for all request sources
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from infrastructure.configuration import Settings
    from infrastructure.i18n.service import TranslationService

import structlog

from infrastructure.i18n.models import TranslationKey, Locale
from infrastructure.operations import OperationResult
from infrastructure.platforms.clients.http import InternalHttpClient
from infrastructure.platforms.models import CommandPayload, CommandResponse

logger = structlog.get_logger(__name__)


class BaseCommandAdapter(ABC):
    """Base class for platform command adapters.

    Each platform implements this to:
    1. Parse platform-specific command payloads
    2. Call internal HTTP endpoints
    3. Format responses for platform display

    Subclasses implement:
        - parse_payload(): Platform event → CommandPayload
        - format_response(): OperationResult → Platform-specific format
        - get_endpoint_mapping(): Command text → HTTP endpoint mapping

    Attributes:
        _settings: Application settings
        _http_client: Client for internal HTTP calls
        _translation_service: Optional i18n service for localized responses
    """

    def __init__(
        self,
        settings: "Settings",
        http_client: Optional[InternalHttpClient] = None,
        translation_service: Optional["TranslationService"] = None,
    ) -> None:
        """Initialize command adapter.

        Args:
            settings: Application settings
            http_client: HTTP client for internal calls (creates default if None)
            translation_service: Optional translation service for i18n
        """
        self._settings = settings
        self._http_client = http_client or InternalHttpClient()
        self._translation_service = translation_service
        self._logger = logger.bind(adapter=self.__class__.__name__)

    @abstractmethod
    def parse_payload(self, platform_event: Dict[str, Any]) -> CommandPayload:
        """Parse platform-specific event into normalized command payload.

        Args:
            platform_event: Raw event from platform (Slack event, Teams activity, etc.)

        Returns:
            Normalized CommandPayload

        Example:
            # Slack slash command
            event = {
                "command": "/sre",
                "text": "groups add user@example.com --group=eng-team",
                "user_id": "U12345",
                "channel_id": "C67890",
            }
            payload = adapter.parse_payload(event)
            # CommandPayload(text="/sre groups add ...", user_id="U12345", ...)
        """
        pass

    @abstractmethod
    def format_response(
        self,
        result: OperationResult,
        locale: Optional[str] = None,
    ) -> CommandResponse:
        """Format OperationResult for platform-specific display.

        Args:
            result: Result from HTTP endpoint call
            locale: User's locale for i18n (e.g., "en", "fr")

        Returns:
            CommandResponse with platform-specific formatting

        Example:
            result = OperationResult.success(
                data={"member": "user@example.com", "group": "eng-team"},
                message="Member added successfully"
            )

            response = adapter.format_response(result, locale="fr")
            # Slack: Block Kit blocks
            # Teams: Adaptive Card JSON
            # Discord: Embed JSON
        """
        pass

    @abstractmethod
    def get_endpoint_mapping(self, command_text: str) -> Optional[Dict[str, Any]]:
        """Map command text to HTTP endpoint and parameters.

        Args:
            command_text: Full command text from platform

        Returns:
            Dict with:
                - method: HTTP method (GET, POST, etc.)
                - path: Endpoint path
                - body: Request body (if POST/PUT)
                - query: Query parameters (if GET)

        Example:
            text = "/sre groups add user@example.com --group=eng-team"

            mapping = adapter.get_endpoint_mapping(text)
            # {
            #     "method": "POST",
            #     "path": "/api/v1/groups/add",
            #     "body": {
            #         "group_id": "eng-team",
            #         "member_email": "user@example.com",
            #         "requestor_email": "<from user_id>",
            #     }
            # }
        """
        pass

    def execute_command(self, payload: CommandPayload) -> OperationResult:
        """Execute command by calling internal HTTP endpoint.

        This is the core adapter logic:
        1. Map command text to HTTP endpoint
        2. Call endpoint via HTTP client
        3. Return result for formatting

        Args:
            payload: Parsed command payload

        Returns:
            OperationResult from HTTP endpoint

        Raises:
            ValueError: If command cannot be mapped to endpoint
        """
        log = self._logger.bind(
            command_text=payload.text,
            user_id=payload.user_id,
            correlation_id=payload.correlation_id,
        )
        log.info("executing_command_via_http")

        # Get endpoint mapping
        mapping = self.get_endpoint_mapping(payload.text)
        if not mapping:
            log.warning("command_not_mapped", text=payload.text)
            return OperationResult.permanent_error(
                message=f"Unknown command: {payload.text}",
                error_code="UNKNOWN_COMMAND",
            )

        method = mapping.get("method", "POST")
        path = mapping["path"]
        body = mapping.get("body")
        query = mapping.get("query")

        log = log.bind(method=method, path=path)
        log.debug("calling_internal_endpoint")

        # Call HTTP endpoint
        if method == "GET":
            result = self._http_client.get(path, params=query)
        elif method == "POST":
            result = self._http_client.post(path, json_data=body, params=query)
        elif method == "PUT":
            result = self._http_client.put(path, json_data=body, params=query)
        elif method == "DELETE":
            result = self._http_client.delete(path, params=query)
        else:
            log.error("unsupported_http_method", method=method)
            return OperationResult.permanent_error(
                message=f"Unsupported HTTP method: {method}",
                error_code="UNSUPPORTED_METHOD",
            )

        if result.is_success:
            log.info("command_executed_successfully")
        else:
            log.error("command_execution_failed", error=result.message)

        return result

    def handle_command(
        self,
        platform_event: Dict[str, Any],
        locale: Optional[str] = None,
    ) -> CommandResponse:
        """Handle complete command flow: parse → execute → format.

        This is the main entry point for command handling.

        Args:
            platform_event: Raw platform event
            locale: User's locale for i18n

        Returns:
            Formatted response ready for platform
        """
        log = self._logger.bind(platform=self.__class__.__name__)

        try:
            # Parse platform event
            payload = self.parse_payload(platform_event)

            log = log.bind(correlation_id=payload.correlation_id)
            log.info("command_received", text=payload.text)

            # Execute via HTTP
            result = self.execute_command(payload)

            # Format for platform
            response = self.format_response(result, locale=locale)

            log.info("command_handled")
            return response

        except Exception as e:
            log.error("command_handling_failed", error=str(e), exc_info=True)

            # Return error response
            error_result = OperationResult.permanent_error(
                message=f"Command handling failed: {str(e)}",
                error_code="HANDLER_ERROR",
            )
            return self.format_response(error_result, locale=locale)

    def translate(self, key: str, locale: Optional[str] = None, **kwargs) -> str:
        """Translate message key to user's locale.

        Args:
            key: Translation key
            locale: Target locale (uses default if None)
            **kwargs: Format parameters

        Returns:
            Translated string or key if translation unavailable
        """
        if not self._translation_service:
            # No translation service - return key with parameters
            return key.format(**kwargs) if kwargs else key

        # Convert string key to TranslationKey
        try:
            translation_key = TranslationKey.from_string(key)
            locale_obj = Locale.from_string(locale or "en-US")
            return self._translation_service.translate(
                key=translation_key,
                locale=locale_obj,
                variables=kwargs or None,
            )
        except (ValueError, KeyError):
            # Fallback to key with parameters if translation fails
            return key.format(**kwargs) if kwargs else key

    def close(self) -> None:
        """Close adapter resources."""
        if self._http_client:
            self._http_client.close()


__all__ = ["BaseCommandAdapter"]
