import os
import importlib
import json
import re
from typing import Any, Callable, Dict, List, Literal, Optional, Pattern, Union

from core.logging import get_module_logger
from models.webhooks import AwsSnsPayload
from modules.ops.notifications import log_ops_message
from pydantic import field_validator
from pydantic.dataclasses import dataclass
from slack_sdk import WebClient

logger = get_module_logger()


@dataclass
class AwsNotificationPattern:
    """Represents a runtime pattern for AWS SNS Notification message matching."""

    name: str
    pattern: str  # regex, substring, or callable import path
    handler: str  # import path like "modules.webhooks.patterns.aws_sns_notification.cloudwatch_alarm.handle_cloudwatch_alarm"
    match_type: Literal["regex", "contains", "callable", "message_structure"] = (
        "contains"
    )
    match_target: Literal["message", "subject", "topic_arn", "parsed_message"] = (
        "message"
    )
    priority: int = 0
    enabled: bool = True

    @field_validator("name")
    @classmethod
    def validate_name(cls, v):
        """Validate the name of the runtime pattern."""
        if not isinstance(v, str) or not v:
            raise ValueError("AwsNotificationPattern.name must be a non-empty str")
        return v

    @field_validator("pattern")
    @classmethod
    def validate_pattern(cls, v):
        """Validate the pattern string."""
        if not isinstance(v, str) or not v:
            raise ValueError("AwsNotificationPattern.pattern must be a non-empty str")
        return v

    @field_validator("handler")
    @classmethod
    def validate_handler(cls, v):
        """Validate the handler import path."""
        if not isinstance(v, str) or not v:
            raise ValueError("AwsNotificationPattern.handler must be a non-empty str")
        return v

    @field_validator("match_type")
    @classmethod
    def validate_match_type(cls, v):
        """Validate the match_type of the runtime pattern."""
        if v not in {"regex", "contains", "callable", "message_structure"}:
            raise ValueError(
                "AwsNotificationPattern.match_type must be one of 'regex', 'contains', 'callable', or 'message_structure'"
            )
        return v

    @field_validator("match_target")
    @classmethod
    def validate_match_target(cls, v):
        """Validate the match_target of the runtime pattern."""
        if v not in {"message", "subject", "topic_arn", "parsed_message"}:
            raise ValueError(
                "AwsNotificationPattern.match_target must be one of 'message', 'subject', 'topic_arn', or 'parsed_message'"
            )
        return v

    @field_validator("enabled")
    @classmethod
    def validate_enabled(cls, v):
        """Validate the enabled status of the runtime pattern."""
        if not isinstance(v, bool):
            raise ValueError("AwsNotificationPattern.enabled must be a boolean")
        return v

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, v):
        """Validate the priority of the runtime pattern. Must be int-like."""
        try:
            return int(v)
        except Exception as exc:
            raise TypeError(
                "AwsNotificationPattern.priority must be an int-like value"
            ) from exc

    def get_compiled_pattern(self) -> str | Pattern | Callable[[Any], bool]:
        """Get the compiled pattern based on match_type."""
        if self.match_type == "regex":
            try:
                return re.compile(self.pattern)
            except re.error as exc:
                raise ValueError(
                    f"Invalid regex pattern '{self.pattern}': {exc}"
                ) from exc
        elif self.match_type == "callable":
            try:
                module_path, func_name = self.pattern.rsplit(".", 1)
                module = importlib.import_module(module_path)
                return getattr(module, func_name)
            except (ImportError, AttributeError, ValueError) as exc:
                raise ValueError(
                    f"Cannot import callable '{self.pattern}': {exc}"
                ) from exc
        else:  # contains or message_structure
            return self.pattern

    def get_handler_function(self) -> Callable[[AwsSnsPayload, WebClient], List[Dict]]:
        """Dynamically import and return the handler function."""
        try:
            module_path, func_name = self.handler.rsplit(".", 1)
            module = importlib.import_module(module_path)
            return getattr(module, func_name)
        except (ImportError, AttributeError, ValueError) as exc:
            raise ValueError(f"Cannot import handler '{self.handler}': {exc}") from exc

    def get_match_text(
        self, payload: AwsSnsPayload, parsed_message: Union[str, dict]
    ) -> str:
        """Extract the text to match against based on match_target."""
        if self.match_target == "message":
            return payload.Message or ""
        elif self.match_target == "subject":
            return payload.Subject or ""
        elif self.match_target == "topic_arn":
            return payload.TopicArn or ""
        elif self.match_target == "parsed_message":
            if isinstance(parsed_message, dict):
                return json.dumps(parsed_message)
            return str(parsed_message)
        return ""

    @classmethod
    def from_dict(cls, d: dict) -> "AwsNotificationPattern":
        """Create an AwsNotificationPattern from a dictionary."""
        if "name" not in d:
            raise ValueError("Missing required field 'name'")
        if "pattern" not in d:
            raise ValueError("Missing required field 'pattern'")
        if "handler" not in d:
            raise ValueError("Missing required field 'handler'")
        return cls(
            name=d["name"],
            match_type=d.get("match_type", "contains"),
            match_target=d.get("match_target", "message"),
            pattern=d["pattern"],
            handler=d["handler"],
            priority=d.get("priority", 0),
            enabled=d.get("enabled", True),
        )


NOTIFICATION_HANDLERS: List[AwsNotificationPattern] = []


def register_notification_pattern(pattern: AwsNotificationPattern | Dict[str, Any]):
    """Register a new notification pattern handler at runtime."""
    if isinstance(pattern, AwsNotificationPattern):
        NOTIFICATION_HANDLERS.append(pattern)
    else:
        NOTIFICATION_HANDLERS.append(AwsNotificationPattern.from_dict(pattern))


def handle_generic_notification(
    payload: AwsSnsPayload, client: WebClient
) -> List[Dict]:
    """
    Fallback handler for unrecognized AWS SNS notifications.
    Logs the unidentified event for manual review.
    """

    if payload.Message is None:
        log_ops_message(f"Payload Message is empty ```{payload}```")
    else:
        log_ops_message(f"Unidentified AWS event received ```{payload.Message}```")

    return []


def parse_message_content(payload: AwsSnsPayload) -> Union[str, dict]:
    """
    Parse the AWS SNS message content, attempting to decode JSON if possible.

    Returns:
        dict: If the message is valid JSON
        str: If the message is a plain string or invalid JSON
    """
    message = payload.Message
    if message is None:
        return ""

    try:
        return json.loads(message)
    except (json.JSONDecodeError, TypeError):
        return message


def find_matching_handler(
    payload: AwsSnsPayload, parsed_message: Union[str, dict]
) -> Optional[AwsNotificationPattern]:
    """
    Find the first matching pattern handler for the given AWS SNS notification.
    Handlers are checked in order of priority (highest first), then registration order.

    Args:
        payload: The AwsSnsPayload to match against
        parsed_message: The parsed message content (dict if JSON, str otherwise)

    Returns:
        The first matching AwsNotificationPattern, or None if no match is found
    """
    # Filter enabled handlers and sort by priority (descending)
    enabled_handlers = [h for h in NOTIFICATION_HANDLERS if h.enabled]
    sorted_handlers = sorted(enabled_handlers, key=lambda h: h.priority, reverse=True)

    for handler in sorted_handlers:
        try:
            compiled_pattern = handler.get_compiled_pattern()
            match_text = handler.get_match_text(payload, parsed_message)

            # Handle different pattern types
            if handler.match_type == "callable" and callable(compiled_pattern):
                if compiled_pattern(payload, parsed_message):
                    return handler
            elif handler.match_type == "regex" and isinstance(
                compiled_pattern, re.Pattern
            ):
                if compiled_pattern.search(match_text):
                    return handler
            elif handler.match_type == "contains" and isinstance(compiled_pattern, str):
                if compiled_pattern in match_text:
                    return handler
            elif handler.match_type == "message_structure" and isinstance(
                parsed_message, dict
            ):
                # For message_structure, pattern should be a key that exists in the parsed message
                if compiled_pattern in parsed_message:
                    return handler
        except Exception:  # pylint: disable=broad-except
            # Skip handlers that raise exceptions during matching or compilation
            continue

    return None


def process_aws_notification_payload(
    payload: AwsSnsPayload, client: WebClient
) -> List[Dict]:
    """
    Process an AWS SNS Notification payload by matching against registered pattern handlers.

    This function uses a registry-based approach to match the incoming notification against
    known patterns and apply appropriate formatting. New use cases can be added by:
    1. Creating a new handler function in the patterns/aws_sns_notification/ directory
    2. Adding a new AwsNotificationPattern to the registry

    Args:
        payload: The AwsSnsPayload containing the notification to process
        client: The Slack WebClient instance

    Returns:
        List[Dict]: Slack blocks ready for posting, or empty list if no match/error
    """
    parsed_message = parse_message_content(payload)
    matched_handler = find_matching_handler(payload, parsed_message)

    if matched_handler:
        try:
            handler_function = matched_handler.get_handler_function()
            blocks = handler_function(payload, client)
            return blocks if blocks else []
        except Exception:  # pylint: disable=broad-except
            # If handler import/execution fails, fall back to generic handling
            return handle_generic_notification(payload, client)
    else:
        return handle_generic_notification(payload, client)


def init_notification_handlers():
    """Initialize and register default notification pattern handlers."""
    # Auto-discover and register all pattern handlers in the patterns/aws_sns_notification directory
    patterns_dir = os.path.join(
        os.path.dirname(__file__), "patterns", "aws_sns_notification"
    )
    if patterns_dir and os.path.isdir(patterns_dir):
        for fname in os.listdir(patterns_dir):
            if fname.endswith(".py") and not fname.startswith("__"):
                mod_name = (
                    f"modules.webhooks.patterns.aws_sns_notification.{fname[:-3]}"
                )
                try:
                    mod = importlib.import_module(mod_name)
                    # Register any variable ending with _HANDLER
                    for attr in dir(mod):
                        if attr.endswith("_HANDLER"):
                            register_notification_pattern(getattr(mod, attr))
                            logger.info(f"registered_notification_pattern: {attr}")
                except Exception as e:
                    logger.warning(
                        f"failed_to_register_notification_pattern_module: {mod_name}",
                        error=str(e),
                    )


# Initialize default patterns on module load
init_notification_handlers()
