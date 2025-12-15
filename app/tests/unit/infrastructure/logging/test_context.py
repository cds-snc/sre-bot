"""Unit tests for infrastructure.logging.context module.

Tests cover:
- bind_request_context() context manager
- get_correlation_id()
- set_correlation_id()
- clear_request_context()
- Context isolation and cleanup
"""

import pytest
import structlog
import uuid
from infrastructure.logging.context import (
    bind_request_context,
    get_correlation_id,
    set_correlation_id,
    clear_request_context,
)


@pytest.mark.unit
class TestBindRequestContext:
    """Test suite for bind_request_context context manager."""

    def test_bind_request_context_auto_generates_correlation_id(self):
        """Correlation ID is auto-generated if not provided."""
        with bind_request_context(user_email="test@example.com"):
            correlation_id = get_correlation_id()
            assert correlation_id is not None
            # Should be a valid UUID
            uuid.UUID(correlation_id)

    def test_bind_request_context_uses_provided_correlation_id(self):
        """Provided correlation ID is used instead of generating one."""
        test_id = "test-correlation-123"
        with bind_request_context(correlation_id=test_id):
            assert get_correlation_id() == test_id

    def test_bind_request_context_binds_user_email(self):
        """User email is bound to context."""
        with bind_request_context(user_email="user@example.com"):
            ctx = structlog.contextvars.get_contextvars()
            assert ctx.get("user_email") == "user@example.com"

    def test_bind_request_context_binds_user_id(self):
        """User ID is bound to context."""
        with bind_request_context(user_id="user-123"):
            ctx = structlog.contextvars.get_contextvars()
            assert ctx.get("user_id") == "user-123"

    def test_bind_request_context_binds_request_path(self):
        """Request path is bound to context."""
        with bind_request_context(request_path="/api/v1/users"):
            ctx = structlog.contextvars.get_contextvars()
            assert ctx.get("request_path") == "/api/v1/users"

    def test_bind_request_context_binds_request_method(self):
        """Request method is bound to context."""
        with bind_request_context(request_method="POST"):
            ctx = structlog.contextvars.get_contextvars()
            assert ctx.get("request_method") == "POST"

    def test_bind_request_context_binds_extra_context(self):
        """Extra keyword arguments are bound to context."""
        with bind_request_context(
            channel="slack", team_id="T123", custom_field="value"
        ):
            ctx = structlog.contextvars.get_contextvars()
            assert ctx.get("channel") == "slack"
            assert ctx.get("team_id") == "T123"
            assert ctx.get("custom_field") == "value"

    def test_bind_request_context_binds_all_parameters(self):
        """All parameters can be bound simultaneously."""
        with bind_request_context(
            correlation_id="req-123",
            user_email="user@example.com",
            user_id="user-456",
            request_path="/api/v1/groups",
            request_method="GET",
            custom="data",
        ):
            ctx = structlog.contextvars.get_contextvars()
            assert ctx.get("correlation_id") == "req-123"
            assert ctx.get("user_email") == "user@example.com"
            assert ctx.get("user_id") == "user-456"
            assert ctx.get("request_path") == "/api/v1/groups"
            assert ctx.get("request_method") == "GET"
            assert ctx.get("custom") == "data"

    def test_bind_request_context_clears_after_exit(self):
        """Context is cleared after exiting the context manager."""
        with bind_request_context(
            correlation_id="test-123", user_email="test@example.com"
        ):
            assert get_correlation_id() == "test-123"

        # After exiting, context should be cleared
        assert get_correlation_id() is None
        ctx = structlog.contextvars.get_contextvars()
        assert "user_email" not in ctx

    def test_bind_request_context_restores_previous_state(self):
        """Nested contexts restore previous state on exit."""
        # Set initial context
        with bind_request_context(
            correlation_id="outer-123", user_email="outer@example.com"
        ):
            assert get_correlation_id() == "outer-123"

            # Nested context
            with bind_request_context(
                correlation_id="inner-456", user_email="inner@example.com"
            ):
                assert get_correlation_id() == "inner-456"
                ctx = structlog.contextvars.get_contextvars()
                assert ctx.get("user_email") == "inner@example.com"

            # After nested exit, outer context is restored
            assert get_correlation_id() == "outer-123"
            ctx = structlog.contextvars.get_contextvars()
            assert ctx.get("user_email") == "outer@example.com"

    def test_bind_request_context_skips_none_values(self):
        """None values are not bound to context."""
        with bind_request_context(
            correlation_id="test-123",
            user_email=None,  # Should be skipped
            user_id=None,  # Should be skipped
        ):
            ctx = structlog.contextvars.get_contextvars()
            assert ctx.get("correlation_id") == "test-123"
            assert "user_email" not in ctx
            assert "user_id" not in ctx


@pytest.mark.unit
class TestGetCorrelationId:
    """Test suite for get_correlation_id function."""

    def test_get_correlation_id_returns_none_when_not_set(self):
        """Returns None when no correlation ID is set."""
        clear_request_context()
        assert get_correlation_id() is None

    def test_get_correlation_id_returns_set_value(self):
        """Returns the correlation ID after it's set."""
        set_correlation_id("test-correlation-id")
        try:
            assert get_correlation_id() == "test-correlation-id"
        finally:
            clear_request_context()

    def test_get_correlation_id_within_context(self):
        """Returns correlation ID when within bind_request_context."""
        with bind_request_context(correlation_id="ctx-123"):
            assert get_correlation_id() == "ctx-123"


@pytest.mark.unit
class TestSetCorrelationId:
    """Test suite for set_correlation_id function."""

    def test_set_correlation_id_binds_to_context(self):
        """Correlation ID is bound to logging context."""
        clear_request_context()
        set_correlation_id("manual-id-123")
        try:
            assert get_correlation_id() == "manual-id-123"
            ctx = structlog.contextvars.get_contextvars()
            assert ctx.get("correlation_id") == "manual-id-123"
        finally:
            clear_request_context()

    def test_set_correlation_id_overwrites_existing(self):
        """Setting a new correlation ID overwrites the old one."""
        set_correlation_id("first-id")
        set_correlation_id("second-id")
        try:
            assert get_correlation_id() == "second-id"
        finally:
            clear_request_context()


@pytest.mark.unit
class TestClearRequestContext:
    """Test suite for clear_request_context function."""

    def test_clear_request_context_removes_all_context(self):
        """All context variables are cleared."""
        # Set multiple context variables
        with bind_request_context(
            correlation_id="test-123",
            user_email="test@example.com",
            user_id="user-456",
            custom="data",
        ):
            pass  # Exit the context

        # Manually set some more
        set_correlation_id("another-id")

        # Clear everything
        clear_request_context()

        # Verify all cleared
        assert get_correlation_id() is None
        ctx = structlog.contextvars.get_contextvars()
        assert len(ctx) == 0

    def test_clear_request_context_idempotent(self):
        """Clearing an already clear context doesn't error."""
        clear_request_context()
        clear_request_context()  # Should not raise
        assert get_correlation_id() is None


@pytest.mark.unit
class TestContextIsolation:
    """Test context isolation between different scopes."""

    def test_sequential_contexts_are_isolated(self):
        """Sequential bind_request_context calls are isolated."""
        # First context
        with bind_request_context(
            correlation_id="first", user_email="first@example.com"
        ):
            assert get_correlation_id() == "first"

        # Second context (isolated from first)
        with bind_request_context(
            correlation_id="second", user_email="second@example.com"
        ):
            assert get_correlation_id() == "second"
            ctx = structlog.contextvars.get_contextvars()
            assert ctx.get("user_email") == "second@example.com"

    def test_context_manager_exception_still_clears_context(self):
        """Context is cleared even if exception occurs inside."""
        try:
            with bind_request_context(correlation_id="exception-test"):
                assert get_correlation_id() == "exception-test"
                raise ValueError("Test exception")
        except ValueError:
            pass

        # Context should still be cleared
        assert get_correlation_id() is None
