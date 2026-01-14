"""Microsoft Teams client facade.

Wraps the Bot Framework SDK with OperationResult-based APIs
for consistent error handling across the platform.
"""

import structlog
from typing import Any, Dict, Optional

try:
    from botbuilder.core import TurnContext, BotAdapter  # type: ignore[import-not-found]
    from botbuilder.schema import Activity, ActivityTypes, Attachment  # type: ignore[import-not-found]

    TEAMS_SDK_AVAILABLE = True
except ImportError:
    TEAMS_SDK_AVAILABLE = False
    TurnContext = Any
    BotAdapter = Any
    Activity = Any

from infrastructure.operations import OperationResult, OperationStatus

logger = structlog.get_logger()


class TeamsClientFacade:
    """Facade for Microsoft Teams Bot Framework SDK.

    Wraps Bot Framework SDK operations to provide consistent error handling
    and response formatting across the platform infrastructure.

    Note:
        Requires botbuilder-core package to be installed.
        Set TEAMS_SDK_AVAILABLE=False if SDK is not available.

    Args:
        adapter: Bot Framework adapter for sending activities
        app_id: Microsoft App ID
        app_password: Microsoft App Password

    Example:
        >>> from infrastructure.platforms.clients import TeamsClientFacade
        >>> client = TeamsClientFacade(adapter=adapter, app_id="...", app_password="...")
        >>> result = client.send_activity(context, text="Hello Teams")
        >>> if result.is_success:
        ...     print(f"Activity sent: {result.data['id']}")
    """

    def __init__(
        self,
        adapter: Optional[BotAdapter] = None,
        app_id: Optional[str] = None,
        app_password: Optional[str] = None,
    ):
        """Initialize Teams client facade.

        Args:
            adapter: Bot Framework adapter (optional for testing)
            app_id: Microsoft App ID
            app_password: Microsoft App Password

        Raises:
            ImportError: If botbuilder-core is not installed
        """
        if not TEAMS_SDK_AVAILABLE:
            logger.warning(
                "teams_sdk_unavailable",
                message="botbuilder-core not installed, TeamsClientFacade disabled",
            )

        self._adapter = adapter
        self._app_id = app_id
        self._app_password = app_password
        self._log = logger.bind(component="teams_client_facade")

    def send_activity(
        self,
        turn_context: TurnContext,
        text: Optional[str] = None,
        attachments: Optional[list] = None,
        **kwargs,
    ) -> OperationResult:
        """Send an activity (message) to Microsoft Teams.

        Args:
            turn_context: Bot Framework turn context
            text: Plain text message
            attachments: List of Adaptive Card attachments
            **kwargs: Additional activity properties

        Returns:
            OperationResult with activity response data
        """
        if not TEAMS_SDK_AVAILABLE:
            return OperationResult.permanent_error(
                message="Teams SDK not available (botbuilder-core not installed)",
                error_code="TEAMS_SDK_UNAVAILABLE",
            )

        log = self._log.bind(
            has_text=text is not None, has_attachments=attachments is not None
        )

        try:
            activity = Activity(
                type=ActivityTypes.message, text=text, attachments=attachments, **kwargs
            )

            # Send the activity
            response = turn_context.send_activity(activity)

            log.info(
                "teams_activity_sent",
                activity_id=response.id if hasattr(response, "id") else None,
            )
            return OperationResult.success(
                data={"id": response.id if hasattr(response, "id") else None},
                message="Activity sent successfully",
            )

        except Exception as e:
            log.exception("teams_send_error", error=str(e))

            # Categorize error
            error_str = str(e).lower()
            if any(x in error_str for x in ["timeout", "network", "connection"]):
                return OperationResult.transient_error(
                    message=f"Teams API transient error: {str(e)}",
                    error_code="TEAMS_NETWORK_ERROR",
                    retry_after=30,
                )

            if "unauthorized" in error_str or "403" in error_str:
                return OperationResult(
                    status=OperationStatus.UNAUTHORIZED,
                    message=f"Teams authorization error: {str(e)}",
                    error_code="TEAMS_UNAUTHORIZED",
                )

            return OperationResult.permanent_error(
                message=f"Unexpected error sending activity: {str(e)}",
                error_code="TEAMS_CLIENT_ERROR",
            )

    def update_activity(
        self, turn_context: TurnContext, activity: Activity
    ) -> OperationResult:
        """Update an existing activity in Teams.

        Args:
            turn_context: Bot Framework turn context
            activity: Updated activity with id set

        Returns:
            OperationResult with update confirmation
        """
        if not TEAMS_SDK_AVAILABLE:
            return OperationResult.permanent_error(
                message="Teams SDK not available (botbuilder-core not installed)",
                error_code="TEAMS_SDK_UNAVAILABLE",
            )

        log = self._log.bind(
            activity_id=activity.id if hasattr(activity, "id") else None
        )

        try:
            response = turn_context.update_activity(activity)

            log.info("teams_activity_updated")
            return OperationResult.success(
                data={"id": response.id if hasattr(response, "id") else None},
                message="Activity updated successfully",
            )

        except Exception as e:
            log.exception("teams_update_error", error=str(e))

            error_str = str(e).lower()
            if any(x in error_str for x in ["timeout", "network", "connection"]):
                return OperationResult.transient_error(
                    message=f"Teams API transient error: {str(e)}",
                    error_code="TEAMS_NETWORK_ERROR",
                    retry_after=30,
                )

            return OperationResult.permanent_error(
                message=f"Unexpected error updating activity: {str(e)}",
                error_code="TEAMS_CLIENT_ERROR",
            )

    def delete_activity(
        self, turn_context: TurnContext, activity_id: str
    ) -> OperationResult:
        """Delete an activity from Teams.

        Args:
            turn_context: Bot Framework turn context
            activity_id: ID of activity to delete

        Returns:
            OperationResult with deletion confirmation
        """
        if not TEAMS_SDK_AVAILABLE:
            return OperationResult.permanent_error(
                message="Teams SDK not available (botbuilder-core not installed)",
                error_code="TEAMS_SDK_UNAVAILABLE",
            )

        log = self._log.bind(activity_id=activity_id)

        try:
            turn_context.delete_activity(activity_id)

            log.info("teams_activity_deleted")
            return OperationResult.success(
                data={"deleted": activity_id}, message="Activity deleted successfully"
            )

        except Exception as e:
            log.exception("teams_delete_error", error=str(e))

            error_str = str(e).lower()
            if any(x in error_str for x in ["timeout", "network", "connection"]):
                return OperationResult.transient_error(
                    message=f"Teams API transient error: {str(e)}",
                    error_code="TEAMS_NETWORK_ERROR",
                    retry_after=30,
                )

            return OperationResult.permanent_error(
                message=f"Unexpected error deleting activity: {str(e)}",
                error_code="TEAMS_CLIENT_ERROR",
            )

    def send_adaptive_card(
        self,
        turn_context: TurnContext,
        card_content: Dict[str, Any],
        text: Optional[str] = None,
    ) -> OperationResult:
        """Send an Adaptive Card to Teams.

        Args:
            turn_context: Bot Framework turn context
            card_content: Adaptive Card JSON content
            text: Optional fallback text

        Returns:
            OperationResult with activity response data
        """
        if not TEAMS_SDK_AVAILABLE:
            return OperationResult.permanent_error(
                message="Teams SDK not available (botbuilder-core not installed)",
                error_code="TEAMS_SDK_UNAVAILABLE",
            )

        log = self._log.bind(has_card=True)

        try:
            attachment = Attachment(
                content_type="application/vnd.microsoft.card.adaptive",
                content=card_content,
            )

            return self.send_activity(
                turn_context=turn_context, text=text, attachments=[attachment]
            )

        except Exception as e:
            log.exception("teams_card_error", error=str(e))
            return OperationResult.permanent_error(
                message=f"Unexpected error sending adaptive card: {str(e)}",
                error_code="TEAMS_CARD_ERROR",
            )

    @property
    def is_available(self) -> bool:
        """Check if Teams SDK is available.

        Returns:
            True if botbuilder-core is installed
        """
        return TEAMS_SDK_AVAILABLE

    @property
    def adapter(self) -> Optional[BotAdapter]:
        """Access underlying Bot Framework adapter.

        Returns:
            BotAdapter instance or None

        Warning:
            Direct adapter access bypasses OperationResult wrapping.
            Use only when facade methods are insufficient.
        """
        return self._adapter
