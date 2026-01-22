"""Test platform provider accessor functions.

Tests the ergonomic accessor pattern that provides one-step access to
platform providers instead of the two-step get_platform_service().get_provider() pattern.

Pattern tested:
- Ergonomic accessors (get_slack_provider, get_teams_provider, get_discord_provider)
- Type safety (returns specific provider types)
- Error handling (KeyError when provider not registered)
"""

import pytest
from unittest.mock import Mock

from infrastructure.platforms import (
    SlackPlatformProvider,
    TeamsPlatformProvider,
    DiscordPlatformProvider,
    PlatformService,
)
from infrastructure.services import (
    get_slack_provider,
    get_teams_provider,
    get_discord_provider,
)


@pytest.fixture
def mock_platform_service(monkeypatch):
    """Mock platform service for testing accessors."""
    mock_service = Mock(spec=PlatformService)

    # Patch at the module where it's imported (infrastructure.services)
    monkeypatch.setattr(
        "infrastructure.services.get_platform_service", lambda: mock_service
    )

    return mock_service


def test_get_slack_provider_returns_slack_provider(mock_platform_service):
    """Test get_slack_provider returns SlackPlatformProvider instance."""
    # Arrange
    mock_slack_provider = Mock(spec=SlackPlatformProvider)
    mock_platform_service.get_provider.return_value = mock_slack_provider

    # Act
    provider = get_slack_provider()

    # Assert
    assert provider == mock_slack_provider
    mock_platform_service.get_provider.assert_called_once_with("slack")


def test_get_teams_provider_returns_teams_provider(mock_platform_service):
    """Test get_teams_provider returns TeamsPlatformProvider instance."""
    # Arrange
    mock_teams_provider = Mock(spec=TeamsPlatformProvider)
    mock_platform_service.get_provider.return_value = mock_teams_provider

    # Act
    provider = get_teams_provider()

    # Assert
    assert provider == mock_teams_provider
    mock_platform_service.get_provider.assert_called_once_with("teams")


def test_get_discord_provider_returns_discord_provider(mock_platform_service):
    """Test get_discord_provider returns DiscordPlatformProvider instance."""
    # Arrange
    mock_discord_provider = Mock(spec=DiscordPlatformProvider)
    mock_platform_service.get_provider.return_value = mock_discord_provider

    # Act
    provider = get_discord_provider()

    # Assert
    assert provider == mock_discord_provider
    mock_platform_service.get_provider.assert_called_once_with("discord")


def test_get_slack_provider_raises_key_error_when_not_registered(mock_platform_service):
    """Test get_slack_provider raises KeyError when Slack not registered."""
    # Arrange - platform service raises KeyError
    mock_platform_service.get_provider.side_effect = KeyError(
        "Platform 'slack' not registered"
    )

    # Act & Assert
    with pytest.raises(KeyError, match="Platform 'slack' not registered"):
        get_slack_provider()


def test_provider_accessors_are_ergonomic_improvement():
    """Accessor pattern is more ergonomic than two-step pattern.

    OLD PATTERN (verbose):
        service = get_platform_service()
        slack_provider = service.get_provider("slack")

    NEW PATTERN (ergonomic):
        slack_provider = get_slack_provider()

    Benefits:
    - One line instead of two
    - Type-safe (returns specific provider type)
    - No intermediate variable
    - Maintains explicit pattern (still called explicitly from code)
    """
    pass


def test_accessors_maintain_explicit_registration_pattern():
    """Accessors maintain explicit registration pattern.

    CORRECT PATTERN (what we have):
        # Feature registration function
        def register_slack_commands():
            slack_provider = get_slack_provider()
            slack_provider.register_command(...)

        # main.py (explicit registration)
        register_slack_commands()

    ANTI-PATTERN (what we avoid):
        # Module-level side-effect
        slack_provider = get_slack_provider()  # Runs at import time
        slack_provider.register_command(...)   # Side-effect on import

        # main.py (implicit registration)
        import packages.geolocate.slack  # Triggers registration as side-effect

    The accessor functions are an ergonomic improvement that maintains
    the explicit registration pattern.
    """
    pass
