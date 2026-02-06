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
        "settings",
        "logger",
        "bot",  # Can be None if Slack not configured, but must exist
        "providers",
        "command_providers",
        "socket_mode_handler",
        "scheduled_stop_event",
    ]

    for attr in required_attrs:
        assert hasattr(app_with_lifespan.app.state, attr), (
            f"app.state.{attr} not set during lifespan initialization. "
            f"Routes will crash with KeyError when trying to access this."
        )


@pytest.mark.integration
def test_app_state_settings_is_valid(app_with_lifespan):
    """Validate that settings object is properly initialized.

    Settings should be a valid Settings instance with all required
    configuration loaded from environment.
    """
    settings = app_with_lifespan.app.state.settings

    assert settings is not None, "settings must not be None"
    # Verify it's a Settings instance by checking it has expected attributes
    assert hasattr(settings, "is_production"), "settings missing is_production"
    assert hasattr(settings, "slack"), "settings missing slack"
    assert hasattr(settings, "aws"), "settings missing aws"
    assert hasattr(settings, "LOG_LEVEL"), "settings missing LOG_LEVEL"
    # Verify is_production is a boolean
    assert isinstance(settings.is_production, bool), "is_production must be a boolean"


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
def test_app_state_providers_is_initialized(app_with_lifespan):
    """Validate that providers dict is initialized (may be empty).

    Providers dict should exist even if no providers are loaded.
    This prevents KeyError when routes check for providers.
    """
    providers = app_with_lifespan.app.state.providers

    assert providers is not None, "providers must not be None"
    assert isinstance(providers, dict), "providers must be a dict"


@pytest.mark.integration
def test_app_state_bot_may_be_none_but_exists(app_with_lifespan):
    """Validate that bot attribute exists (may be None if Slack not configured).

    The bot attribute must exist on app.state even if Slack is not configured.
    This prevents KeyError crashes when routes try to check if bot exists.
    """
    # bot can be None if SLACK_TOKEN is not set, but the attribute must exist
    assert hasattr(app_with_lifespan.app.state, "bot"), (
        "app.state.bot attribute missing. Routes cannot safely check "
        "getattr(app.state, 'bot', None) if attribute doesn't exist."
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
    assert (
        response.status_code != 500
    ), "Got 500 ASGI crash, indicating app.state initialization failed"
