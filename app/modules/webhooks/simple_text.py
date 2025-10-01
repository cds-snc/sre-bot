import re
import importlib
from typing import Optional, Dict, List, Callable, Any, Pattern, Literal
from pydantic.dataclasses import dataclass
from pydantic import field_validator

from models.webhooks import SimpleTextPayload, WebhookPayload, WebhookResult


@dataclass
class SimpleTextPattern:
    """Represents a runtime pattern for text matching in simple text payloads"""

    name: str
    pattern: str  # regex, substring, or callable import path
    handler: str  # import path like "modules.webhooks.patterns.simple_text.upptime.handle_upptime_payload"
    match_type: Literal["regex", "contains", "callable"] = "contains"
    priority: int = 0
    enabled: bool = True

    @field_validator("name")
    @classmethod
    def validate_name(cls, v):
        """Validate the name of the runtime pattern."""
        if not isinstance(v, str) or not v:
            raise ValueError("SimpleTextPattern.name must be a non-empty str")
        return v

    @field_validator("pattern")
    @classmethod
    def validate_pattern(cls, v):
        """Validate the pattern string."""
        if not isinstance(v, str) or not v:
            raise ValueError("SimpleTextPattern.pattern must be a non-empty str")
        return v

    @field_validator("handler")
    @classmethod
    def validate_handler(cls, v):
        """Validate the handler import path."""
        if not isinstance(v, str) or not v:
            raise ValueError("SimpleTextPattern.handler must be a non-empty str")
        return v

    @field_validator("match_type")
    @classmethod
    def validate_match_type(cls, v):
        """Validate the match_type of the runtime pattern."""
        if v not in {"regex", "contains", "callable"}:
            raise ValueError(
                "SimpleTextPattern.match_type must be one of 'regex', 'contains', or 'callable'"
            )
        return v

    @field_validator("enabled")
    @classmethod
    def validate_enabled(cls, v):
        """Validate the enabled status of the runtime pattern."""
        if not isinstance(v, bool):
            raise ValueError("SimpleTextPattern.enabled must be a boolean")
        return v

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, v):
        """Validate the priority of the runtime pattern. Must be int-like."""
        try:
            return int(v)
        except Exception as exc:
            raise TypeError(
                "SimpleTextPattern.priority must be an int-like value"
            ) from exc

    def get_compiled_pattern(self) -> str | Pattern | Callable[[str], bool]:
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
        else:  # contains
            return self.pattern

    def get_handler_function(self) -> Callable[[str], WebhookPayload]:
        """Dynamically import and return the handler function."""
        try:
            module_path, func_name = self.handler.rsplit(".", 1)
            module = importlib.import_module(module_path)
            return getattr(module, func_name)
        except (ImportError, AttributeError, ValueError) as exc:
            raise ValueError(f"Cannot import handler '{self.handler}': {exc}") from exc

    @classmethod
    def from_dict(cls, d: dict) -> "SimpleTextPattern":
        """Create a SimpleTextPattern from a dictionary."""
        if "name" not in d:
            raise ValueError("Missing required field 'name'")
        if "pattern" not in d:
            raise ValueError("Missing required field 'pattern'")
        if "handler" not in d:
            raise ValueError("Missing required field 'handler'")
        return cls(
            name=d["name"],
            match_type=d.get("match_type", "contains"),
            pattern=d["pattern"],
            handler=d["handler"],
            priority=d.get("priority", 0),
            enabled=d.get("enabled", True),
        )


PATTERN_HANDLERS: List[SimpleTextPattern] = []


def register_pattern(pattern: SimpleTextPattern | Dict[str, Any]):
    """Register a new pattern handler at runtime."""
    if isinstance(pattern, SimpleTextPattern):
        PATTERN_HANDLERS.append(pattern)
    else:
        PATTERN_HANDLERS.append(SimpleTextPattern.from_dict(pattern))


def handle_generic_text(text: str) -> WebhookPayload:
    """
    Fallback handler for generic text payloads.
    Returns a simple text-only webhook payload.
    """
    return WebhookPayload(text=text)


def find_matching_handler(text: str) -> Optional[SimpleTextPattern]:
    """
    Find the first matching pattern handler for the given text.
    Handlers are checked in order of priority (highest first), then registration order.

    Args:
        text: The text to match against registered patterns

    Returns:
        The first matching SimpleTextPattern, or None if no match is found
    """
    # Filter enabled handlers and sort by priority (descending)
    enabled_handlers = [h for h in PATTERN_HANDLERS if h.enabled]
    sorted_handlers = sorted(enabled_handlers, key=lambda h: h.priority, reverse=True)

    for handler in sorted_handlers:
        try:
            compiled_pattern = handler.get_compiled_pattern()

            # Handle different pattern types
            if handler.match_type == "callable" and callable(compiled_pattern):
                if compiled_pattern(text):
                    return handler
            elif handler.match_type == "regex" and isinstance(
                compiled_pattern, re.Pattern
            ):
                if compiled_pattern.search(text):
                    return handler
            elif handler.match_type == "contains" and isinstance(compiled_pattern, str):
                if compiled_pattern in text:
                    return handler
        except Exception:  # pylint: disable=broad-except
            # Skip handlers that raise exceptions during matching or compilation
            continue

    return None


def process_simple_text_payload(payload: SimpleTextPayload) -> WebhookResult:
    """
    Process a SimpleTextPayload webhook by matching against registered pattern handlers.

    This function uses a registry-based approach to match the incoming text against
    known patterns and apply appropriate formatting. New use cases can be added by:
    1. Creating a new handler function (e.g., handle_new_usecase)
    2. Adding a new SimpleTextPattern to the PATTERN_HANDLERS list

    Args:
        payload: The SimpleTextPayload containing the text to process

    Returns:
        WebhookResult with the formatted payload ready for posting to Slack
    """
    text = payload.text

    matched_handler = find_matching_handler(text)

    if matched_handler:
        try:
            handler_function = matched_handler.get_handler_function()
            formatted_payload = handler_function(text)
        except Exception:  # pylint: disable=broad-except
            # If handler import/execution fails, fall back to generic text
            formatted_payload = handle_generic_text(text)
    else:
        formatted_payload = handle_generic_text(text)

    return WebhookResult(
        status="success",
        action="post",
        payload=formatted_payload,
    )
