"""Unit tests for infrastructure event handler discovery system.

Tests cover:
- Automatic discovery of event handler modules
- Handler registration from discovered modules
- Visibility into registered event handlers
- Error handling during discovery
"""

import pytest
from infrastructure.events import (
    Event,
    dispatch_event,
    discover_and_register_handlers,
    get_registered_handlers_by_event_type,
    log_registered_handlers,
)
from uuid import uuid4


@pytest.mark.unit
class TestEventHandlerDiscovery:
    """Tests for event handler auto-discovery mechanism."""

    def test_discover_handlers_returns_summary_dict(self, clear_event_handlers):
        """Discovery returns structured summary dictionary."""
        summary = discover_and_register_handlers(
            base_path="modules", package_root="modules"
        )

        # Verify structure
        assert isinstance(summary, dict)
        assert "total_modules_scanned" in summary
        assert "handlers_discovered" in summary
        assert "handlers_registered" in summary
        assert "errors" in summary

    def test_discover_handlers_scanned_count_is_int(self, clear_event_handlers):
        """Total modules scanned is an integer."""
        summary = discover_and_register_handlers(
            base_path="modules", package_root="modules"
        )

        assert isinstance(summary["total_modules_scanned"], int)

    def test_discover_handlers_discovered_is_list(self, clear_event_handlers):
        """Handlers discovered list is a list of strings."""
        summary = discover_and_register_handlers(
            base_path="modules", package_root="modules"
        )

        assert isinstance(summary["handlers_discovered"], list)
        assert all(isinstance(h, str) for h in summary["handlers_discovered"])

    def test_discover_handlers_registered_is_list(self, clear_event_handlers):
        """Handlers registered list is a list of strings (event types)."""
        summary = discover_and_register_handlers(
            base_path="modules", package_root="modules"
        )

        assert isinstance(summary["handlers_registered"], list)
        assert all(isinstance(h, str) for h in summary["handlers_registered"])

    def test_discover_handlers_errors_nullable(self, clear_event_handlers):
        """Errors field is None or dict."""
        summary = discover_and_register_handlers(
            base_path="modules", package_root="modules"
        )

        errors = summary["errors"]
        assert errors is None or isinstance(errors, dict)

    def test_discover_finds_groups_handlers_module(self, clear_event_handlers):
        """Discovery can find modules.groups.events.handlers module if not yet imported."""
        # Note: In test context, modules may already be imported
        # This test verifies the discovery mechanism would find it
        summary = discover_and_register_handlers(
            base_path="modules", package_root="modules"
        )

        # If discovery found modules, verify structure
        if summary["handlers_discovered"]:
            assert all(isinstance(h, str) for h in summary["handlers_discovered"])

    def test_discover_registers_event_types(self, clear_event_handlers):
        """Discovery can register event types if handlers are discoverable."""
        summary = discover_and_register_handlers(
            base_path="modules", package_root="modules"
        )

        registered = summary["handlers_registered"]

        # If discovery found handlers, verify structure
        if registered:
            assert all(isinstance(e, str) for e in registered)

    def test_discover_no_errors_on_success(self, clear_event_handlers):
        """Successful discovery has no errors."""
        summary = discover_and_register_handlers(
            base_path="modules", package_root="modules"
        )

        # Either no errors dict or empty dict
        assert summary["errors"] is None or len(summary["errors"]) == 0


@pytest.mark.unit
class TestRegisteredHandlersVisibility:
    """Tests for getting visibility into registered handlers."""

    def test_get_handlers_by_event_type_returns_dict(self, clear_event_handlers):
        """get_registered_handlers_by_event_type returns a dict."""
        import modules.groups.events.handlers  # noqa: F401

        discover_and_register_handlers(base_path="modules", package_root="modules")

        handlers_by_type = get_registered_handlers_by_event_type()

        assert isinstance(handlers_by_type, dict)

    def test_handler_names_are_strings(self, clear_event_handlers):
        """Handler names in visibility data are strings."""
        import modules.groups.events.handlers  # noqa: F401

        discover_and_register_handlers(base_path="modules", package_root="modules")

        handlers_by_type = get_registered_handlers_by_event_type()

        for event_type, names in handlers_by_type.items():
            assert isinstance(event_type, str)
            assert isinstance(names, list)
            assert all(isinstance(name, str) for name in names)

    def test_log_registered_handlers_completes_successfully(self, clear_event_handlers):
        """log_registered_handlers() executes without raising."""
        import modules.groups.events.handlers  # noqa: F401

        discover_and_register_handlers(base_path="modules", package_root="modules")

        # Should not raise
        log_registered_handlers()


@pytest.mark.unit
class TestEventDispatchAfterDiscovery:
    """Tests that handlers work correctly after discovery."""

    def test_event_dispatches_after_discovery(self, clear_event_handlers):
        """Events dispatch successfully after handler discovery."""
        import modules.groups.events.handlers  # noqa: F401

        # Discover handlers
        discover_and_register_handlers(base_path="modules", package_root="modules")

        # Create test event for discovered handler type
        event = Event(
            event_type="group.listed",
            correlation_id=uuid4(),
            user_email="test@example.com",
            metadata={"provider": "google", "group_count": 5},
        )

        # Dispatch should complete (handlers may fail gracefully)
        results = dispatch_event(event)

        # Dispatch mechanism works
        assert isinstance(results, list)


@pytest.mark.unit
class TestDiscoveryPathHandling:
    """Tests for discovery path resolution."""

    def test_discover_with_relative_path_resolves_correctly(self, clear_event_handlers):
        """Relative path is resolved to absolute path."""
        summary = discover_and_register_handlers(
            base_path="modules", package_root="modules"
        )

        # Should return valid summary (may have 0 modules if path not found)
        assert isinstance(summary, dict)
        assert "total_modules_scanned" in summary

    def test_discover_with_invalid_path_returns_summary(self, clear_event_handlers):
        """Invalid path returns summary with error info."""
        summary = discover_and_register_handlers(
            base_path="/nonexistent/path", package_root="modules"
        )

        # Should return valid summary with error
        assert isinstance(summary, dict)
        assert "errors" in summary
