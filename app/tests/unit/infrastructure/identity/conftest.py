"""Fixtures for infrastructure.identity tests."""

import pytest
from unittest.mock import Mock

from infrastructure.identity import (
    IdentityService,
    IdentityResolver,
    IdentitySource,
    User,
    SlackUser,
)
from infrastructure.configuration import Settings


@pytest.fixture
def mock_settings():
    """Mock Settings instance for testing."""
    return Mock(spec=Settings)


@pytest.fixture
def mock_slack_client_manager():
    """Mock SlackClientManager for testing."""
    mock_manager = Mock()
    mock_client = Mock()
    mock_manager.get_client.return_value = mock_client
    return mock_manager


@pytest.fixture
def identity_resolver(mock_slack_client_manager):
    """Create IdentityResolver with mocked Slack client."""
    return IdentityResolver(slack_client_manager=mock_slack_client_manager)


@pytest.fixture
def identity_service(mock_settings, mock_slack_client_manager):
    """Create IdentityService with mocked dependencies."""
    return IdentityService(
        settings=mock_settings, slack_client_manager=mock_slack_client_manager
    )


@pytest.fixture
def make_user():
    """Factory for creating User instances."""

    def _make(
        user_id="test@example.com",
        email="test@example.com",
        display_name="Test User",
        source=IdentitySource.SLACK,
        platform_id="U123ABC",
        permissions=None,
        metadata=None,
    ):
        return User(
            user_id=user_id,
            email=email,
            display_name=display_name,
            source=source,
            platform_id=platform_id,
            permissions=permissions or [],
            metadata=metadata or {},
        )

    return _make


@pytest.fixture
def make_slack_user():
    """Factory for creating SlackUser instances."""

    def _make(
        user_id="test@example.com",
        email="test@example.com",
        display_name="Test User",
        source=IdentitySource.SLACK,
        platform_id="U123ABC",
        slack_user_id="U123ABC",
        slack_team_id="T456DEF",
        slack_user_name="testuser",
        permissions=None,
        metadata=None,
    ):
        return SlackUser(
            user_id=user_id,
            email=email,
            display_name=display_name,
            source=source,
            platform_id=platform_id,
            slack_user_id=slack_user_id,
            slack_team_id=slack_team_id,
            slack_user_name=slack_user_name,
            permissions=permissions or [],
            metadata=metadata or {},
        )

    return _make
