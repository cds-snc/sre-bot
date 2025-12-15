"""Request context binding for structured logging.

This module provides utilities for binding request-scoped context
to logs, enabling correlation IDs and request metadata to flow
through all log entries during a request lifecycle.

Usage:
    from infrastructure.logging import bind_request_context

    # In middleware or request handler
    with bind_request_context(correlation_id="req-123", user_email="user@example.com"):
        # All logs within this block will include the context
        logger.info("processing_request")

Dependencies:
    - structlog.contextvars
"""

import uuid
from contextlib import contextmanager
from typing import Optional, Any, Generator
import structlog


@contextmanager
def bind_request_context(
    correlation_id: Optional[str] = None,
    user_email: Optional[str] = None,
    user_id: Optional[str] = None,
    request_path: Optional[str] = None,
    request_method: Optional[str] = None,
    **extra_context: Any,
) -> Generator[None, None, None]:
    """Bind request-scoped context to all logs within the context manager.

    Creates a context that automatically adds metadata to all log entries
    made within the context block. Useful for request tracing and debugging.

    Args:
        correlation_id: Unique request identifier. Auto-generated if not provided.
        user_email: Email of the authenticated user (if available).
        user_id: ID of the authenticated user (if available).
        request_path: HTTP request path (e.g., "/api/v1/groups").
        request_method: HTTP method (e.g., "GET", "POST").
        **extra_context: Additional key-value pairs to include in logs.

    Yields:
        None - context is automatically bound to structlog's context vars.

    Example:
        # In a FastAPI middleware
        @app.middleware("http")
        async def logging_middleware(request: Request, call_next):
            with bind_request_context(
                correlation_id=request.headers.get("X-Correlation-ID"),
                request_path=request.url.path,
                request_method=request.method,
            ):
                response = await call_next(request)
                return response

        # In a Slack command handler
        with bind_request_context(
            correlation_id=command.get("trigger_id"),
            user_id=command.get("user_id"),
            channel="slack",
        ):
            process_command(command)
    """
    # Build context dict with only non-None values
    context: dict[str, Any] = {}

    # Use provided correlation_id or generate one
    context["correlation_id"] = correlation_id or str(uuid.uuid4())

    if user_email is not None:
        context["user_email"] = user_email

    if user_id is not None:
        context["user_id"] = user_id

    if request_path is not None:
        context["request_path"] = request_path

    if request_method is not None:
        context["request_method"] = request_method

    # Add any extra context
    context.update(extra_context)

    # Bind context for the duration of the block
    token = structlog.contextvars.bind_contextvars(**context)
    try:
        yield
    finally:
        # Clear the bound context
        structlog.contextvars.unbind_contextvars(*context.keys())


def get_correlation_id() -> Optional[str]:
    """Get the current correlation ID from the logging context.

    Returns:
        The correlation ID if set, None otherwise.

    Example:
        correlation_id = get_correlation_id()
        if correlation_id:
            response.headers["X-Correlation-ID"] = correlation_id
    """
    ctx = structlog.contextvars.get_contextvars()
    return ctx.get("correlation_id")


def set_correlation_id(correlation_id: str) -> None:
    """Set the correlation ID in the current logging context.

    Args:
        correlation_id: The correlation ID to set.

    Example:
        # When receiving a request with existing correlation ID
        set_correlation_id(request.headers.get("X-Correlation-ID"))
    """
    structlog.contextvars.bind_contextvars(correlation_id=correlation_id)


def clear_request_context() -> None:
    """Clear all request-scoped context from the logging context.

    Should be called at the end of request processing to prevent
    context leakage between requests.

    Example:
        try:
            process_request()
        finally:
            clear_request_context()
    """
    structlog.contextvars.clear_contextvars()
