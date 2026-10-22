"""Test that app.state is properly initialized during lifespan.

This integration test ensures that all required app.state attributes
are set during the FastAPI lifespan context, preventing KeyError/AttributeError
at runtime when routes try to access app.state values.

This test catches issues like:
- app.state.bot not being set
- Settings not initialized
- Providers not loaded
- Logger not configured
"""

import pytest


@pytest.mark.integration
def test_app_state_has_all_required_attributes(app_with_lifespan):
    """Validate that lifespan sets all required app.state attributes.

    The app.state object must contain critical attributes that routes
    depend on. Missing attributes cause KeyError/AttributeError crashes
    at request time.
    """
    required_attrs = [
        "host_info",
        "logger",
        "bot",  # Can be None if Slack not configured, but must exist
        "directory_provider",
        "socket_mode_handler",
        "scheduled_stop_event",
    ]

    for attr in required_attrs:
        assert hasattr(app_with_lifespan.app.state, attr), (
            f"app.state.{attr} not set during lifespan initialization. "
            f"Routes will crash with KeyError when trying to access this."
        )


@pytest.mark.integration
def test_app_state_host_info_is_valid(app_with_lifespan):
    """Validate that the host facts are stored on app.state.

    The lifespan should store the HostInfo the app factory built.
    """
    host = app_with_lifespan.app.state.host_info

    assert host is not None, "host_info must not be None"
    assert host.environment in {"local", "ci", "production"}
    assert host.git_sha


@pytest.mark.integration
def test_contract_app_state_host_info_has_no_legacy_production_property(
    app_with_lifespan,
):
    """Contract: app.state.host_info should not expose the legacy production shim."""
    settings = app_with_lifespan.app.state.host_info
    legacy_attr = "is" + "_production"

    assert hasattr(settings, "environment"), "settings missing environment"
    assert not hasattr(settings, legacy_attr)


@pytest.mark.integration
def test_app_state_logger_is_valid(app_with_lifespan):
    """Validate that logger is properly initialized.

    Logger should be a bound logger instance ready for structured logging.
    """
    logger = app_with_lifespan.app.state.logger

    assert logger is not None, "logger must not be None"
    assert hasattr(logger, "info"), "logger missing info method"
    assert hasattr(logger, "error"), "logger missing error method"
    assert hasattr(logger, "bind"), "logger missing bind method"


@pytest.mark.integration
def test_app_state_directory_provider_is_initialized(app_with_lifespan):
    """Validate that directory_provider is initialized on app.state."""
    directory_provider = app_with_lifespan.app.state.directory_provider

    assert directory_provider is not None, "directory_provider must not be None"
    assert hasattr(directory_provider, "warmup"), "directory_provider missing warmup"
    assert hasattr(directory_provider, "health_check"), "directory_provider missing health_check"
    assert hasattr(directory_provider, "get_user"), "directory_provider missing get_user"
    assert hasattr(directory_provider, "list_users"), "directory_provider missing list_users"
    assert hasattr(directory_provider, "get_group_members"), "directory_provider missing get_group_members"
    assert hasattr(directory_provider, "get_group"), "directory_provider missing get_group"
    assert hasattr(directory_provider, "add_group_member"), "directory_provider missing add_group_member"
    assert hasattr(directory_provider, "remove_group_member"), "directory_provider missing remove_group_member"
    assert hasattr(directory_provider, "check_membership"), "directory_provider missing check_membership"
    assert hasattr(directory_provider, "list_groups"), "directory_provider missing list_groups"


@pytest.mark.integration
def test_app_state_bot_may_be_none_but_exists(app_with_lifespan):
    """Validate that bot attribute exists (may be None if Slack not configured).

    The bot attribute must exist on app.state even if Slack is not configured.
    This prevents KeyError crashes when routes try to check if bot exists.
    """
    # bot can be None when SLACK_ENABLED is off, but the attribute must exist
    assert hasattr(app_with_lifespan.app.state, "bot"), (
        "app.state.bot attribute missing. Routes cannot safely check getattr(app.state, 'bot', None) if attribute doesn't exist."
    )


@pytest.mark.integration
def test_app_routes_respond_without_crashes(app_with_lifespan):
    """Validate that basic app routes respond without ASGI crashes.

    Even if specific routes fail, they should return HTTP errors,
    not ASGI 500 crashes due to missing app.state attributes.
    """
    # Try a health check or docs endpoint that should exist
    response = app_with_lifespan.get("/docs", follow_redirects=False)

    # Should not be a 500 ASGI crash
    assert response.status_code != 500, "Got 500 ASGI crash, indicating app.state initialization failed"
